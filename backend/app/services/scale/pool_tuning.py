"""DB connection pool tuning helpers and recommendations (Phase 4-C.6)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.infrastructure.database.session import engine


def _pool_metric(pool: object, name: str) -> int | None:
    value = getattr(pool, name, None)
    if callable(value):
        try:
            return int(value())
        except (TypeError, ValueError):
            return None
    return None


def get_current_pool_config() -> dict[str, Any]:
    pool = engine.pool
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": settings.db_pool_pre_ping,
        "pool_recycle_seconds": settings.db_pool_recycle_seconds,
        "max_connections_per_process": settings.db_pool_size + settings.db_max_overflow,
        "checked_in": _pool_metric(pool, "checkedin"),
        "checked_out": _pool_metric(pool, "checkedout"),
        "overflow": _pool_metric(pool, "overflow"),
    }


def build_pool_tuning_recommendations(benchmark: dict[str, Any] | None = None) -> dict[str, Any]:
    current = get_current_pool_config()
    projects = benchmark.get("meta", {}).get("projects", 500) if benchmark else 500
    full_batch_seconds = None
    if benchmark:
        full_batch_seconds = benchmark.get("summary", {}).get("full_batch_elapsed_seconds")

    recommendations: list[dict[str, str]] = []

    if projects >= 2000:
        recommendations.append(
            {
                "area": "连接池",
                "priority": "高",
                "action": "将 DB_POOL_SIZE 提升至 20、DB_MAX_OVERFLOW 提升至 40，并设置 DB_POOL_RECYCLE_SECONDS=3600。",
                "reason": "2000 项目规模下并发读接口与批量重算并存，默认 10+20 易在高峰出现连接等待。",
            }
        )
    elif projects >= 500:
        recommendations.append(
            {
                "area": "连接池",
                "priority": "中",
                "action": "生产环境建议 DB_POOL_SIZE=15、DB_MAX_OVERFLOW=25；按 uvicorn workers 数核算总连接上限。",
                "reason": "500 项目门禁压测已通过，但全量 projects 列表与重算任务叠加时需预留连接余量。",
            }
        )

    recommendations.extend(
        [
            {
                "area": "连接池",
                "priority": "中",
                "action": "总连接预算：workers × (pool_size + max_overflow) ≤ MySQL max_connections × 0.7。",
                "reason": "避免多 worker 进程各自持池导致数据库连接耗尽。",
            },
            {
                "area": "profile/recalculate",
                "priority": "高",
                "action": "按项目批量预取 hazard/equipment，减少逐项目 N+1 查询；工人/分包商画像可分片异步重算。",
                "reason": "当前重算循环内逐实体查询是批量耗时的主要来源。",
            },
            {
                "area": "GET /projects",
                "priority": "高",
                "action": "强制分页（默认 page_size≤50）并对排名/列表接口增加 Redis 缓存。",
                "reason": "2000 项目压测中 projects_list P95 曾超 500ms，全量扫描是容量敏感点。",
            },
            {
                "area": "运维",
                "priority": "低",
                "action": "开启 pool_pre_ping（已默认）并监控 checked_out/overflow 指标。",
                "reason": "长事务重算期间可及时发现僵死连接与池耗尽。",
            },
        ]
    )

    if full_batch_seconds is not None and full_batch_seconds > 30:
        recommendations.insert(
            0,
            {
                "area": "profile/recalculate",
                "priority": "高",
                "action": f"全量重算耗时 {full_batch_seconds}s 超过 30s SLA，优先拆分 profile_types 或引入队列任务。",
                "reason": "单租户全量同步重算不适合作为在线 API，应改为后台 Job + 进度查询。",
            },
        )

    suggested = {
        "local": {
            "db_pool_size": current["pool_size"],
            "db_max_overflow": current["max_overflow"],
            "db_pool_recycle_seconds": current["pool_recycle_seconds"],
        },
        "staging_500": {
            "db_pool_size": 15,
            "db_max_overflow": 25,
            "db_pool_recycle_seconds": 3600,
        },
        "production_2000": {
            "db_pool_size": 20,
            "db_max_overflow": 40,
            "db_pool_recycle_seconds": 3600,
        },
    }

    return {
        "current": current,
        "suggested_profiles": suggested,
        "recommendations": recommendations,
    }


def render_recalculate_benchmark_markdown(
    *,
    title: str,
    benchmark: dict[str, Any],
    pool_tuning: dict[str, Any],
    extra_notes: list[str] | None = None,
) -> str:
    meta = benchmark.get("meta", {})
    seed = benchmark.get("seed", {})
    summary = benchmark.get("summary", {})
    totals = seed.get("totals", {})
    full_batch = next(
        (item for item in benchmark.get("scenarios", []) if item.get("name") == "full_batch"),
        {},
    )
    actual_counts = full_batch.get("counts", {})
    current = pool_tuning.get("current", {})

    lines = [
        f"# {title}",
        "",
        "## 运行信息",
        "",
        f"- 生成时间（UTC）：{meta.get('generated_at', 'n/a')}",
        f"- 压测模式：`{meta.get('mode', 'n/a')}`",
        f"- Base URL：`{meta.get('base_url', 'n/a')}`",
        f"- 租户：`{meta.get('tenant_id', 'n/a')}`",
        f"- 项目规模：{meta.get('projects', 'n/a')}",
        f"- SLA（全量重算）：{meta.get('sla_seconds', 30)}s",
        "",
        "## 灌数摘要",
        "",
        f"- 项目数：{totals.get('projects', 'n/a')}",
        f"- 分包商数：{totals.get('subcontractors', 'n/a')}",
        f"- 工人数：{totals.get('workers', 'n/a')}",
    ]
    if seed.get("skipped"):
        lines.append("- 灌数：已跳过（使用库内现有数据）")
    if actual_counts:
        lines.extend(
            [
                "",
                "## 实际重算规模（full_batch）",
                "",
                f"- 项目：{actual_counts.get('recalculated_projects', 0)}",
                f"- 工人：{actual_counts.get('recalculated_workers', 0)}",
                f"- 分包商：{actual_counts.get('recalculated_subcontractors', 0)}",
            ]
        )
    lines.extend(
        [
        "",
        "## 重算耗时",
        "",
        "| 场景 | 类型 | 耗时 (ms) | 耗时 (s) | SLA | 通过 |",
        "|---|---|---:|---:|---:|:---:|",
        ]
    )

    for scenario in benchmark.get("scenarios", []):
        lines.append(
            "| {name} | {types} | {elapsed_ms} | {elapsed_s} | {sla}s | {passed} |".format(
                name=scenario.get("name", ""),
                types=",".join(scenario.get("profile_types", [])),
                elapsed_ms=scenario.get("elapsed_ms", 0),
                elapsed_s=scenario.get("elapsed_seconds", 0),
                sla=scenario.get("sla_seconds", 30),
                passed="✅" if scenario.get("sla_passed") else "❌",
            )
        )

    lines.extend(
        [
            "",
            "## 全量重算摘要",
            "",
            f"- 耗时：{summary.get('full_batch_elapsed_seconds', 0)}s",
            f"- SLA 通过：{'是' if summary.get('sla_passed') else '否'}",
            "",
            "## 当前连接池",
            "",
            f"- pool_size：{current.get('pool_size', 'n/a')}",
            f"- max_overflow：{current.get('max_overflow', 'n/a')}",
            f"- pool_pre_ping：{current.get('pool_pre_ping', 'n/a')}",
            f"- pool_recycle_seconds：{current.get('pool_recycle_seconds', 'n/a')}",
            f"- 单进程最大连接：{current.get('max_connections_per_process', 'n/a')}",
            "",
            "## 调优建议",
            "",
            "| 领域 | 优先级 | 建议 | 原因 |",
            "|---|:---:|---|---|",
        ]
    )

    for item in pool_tuning.get("recommendations", []):
        lines.append(
            f"| {item.get('area', '')} | {item.get('priority', '')} | {item.get('action', '')} | {item.get('reason', '')} |"
        )

    suggested = pool_tuning.get("suggested_profiles", {})
    if suggested:
        lines.extend(["", "## 推荐配置档位", ""])
        for profile_name, profile_values in suggested.items():
            lines.append(
                f"- **{profile_name}**："
                f"DB_POOL_SIZE={profile_values.get('db_pool_size')}, "
                f"DB_MAX_OVERFLOW={profile_values.get('db_max_overflow')}, "
                f"DB_POOL_RECYCLE_SECONDS={profile_values.get('db_pool_recycle_seconds')}"
            )

    notes = list(benchmark.get("notes", []))
    if extra_notes:
        notes.extend(extra_notes)
    if notes:
        lines.extend(["", "## 备注", ""])
        for note in notes:
            lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)


def render_pool_tuning_markdown(pool_tuning: dict[str, Any]) -> str:
    current = pool_tuning.get("current", {})
    lines = [
        "# 数据库连接池调优建议（Phase 4-C.6）",
        "",
        "> 本文档由 `run_profile_recalculate_benchmark.py` 生成/更新，供运维与容量规划参考。",
        "",
        "## 当前运行时配置",
        "",
        f"- `DB_POOL_SIZE`：{current.get('pool_size')}",
        f"- `DB_MAX_OVERFLOW`：{current.get('max_overflow')}",
        f"- `DB_POOL_PRE_PING`：{current.get('pool_pre_ping')}",
        f"- `DB_POOL_RECYCLE_SECONDS`：{current.get('pool_recycle_seconds')}",
        f"- 单进程最大连接数：{current.get('max_connections_per_process')}",
        "",
        "## 环境变量",
        "",
        "```env",
        "DB_POOL_SIZE=10",
        "DB_MAX_OVERFLOW=20",
        "DB_POOL_PRE_PING=true",
        "DB_POOL_RECYCLE_SECONDS=3600",
        "```",
        "",
        "## 推荐档位",
        "",
    ]

    for profile_name, profile_values in pool_tuning.get("suggested_profiles", {}).items():
        lines.extend(
            [
                f"### {profile_name}",
                "",
                f"- DB_POOL_SIZE={profile_values.get('db_pool_size')}",
                f"- DB_MAX_OVERFLOW={profile_values.get('db_max_overflow')}",
                f"- DB_POOL_RECYCLE_SECONDS={profile_values.get('db_pool_recycle_seconds')}",
                "",
            ]
        )

    lines.extend(
        [
            "## 核算公式",
            "",
            "```text",
            "总连接上限 ≈ uvicorn_workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)",
            "建议 ≤ MySQL max_connections × 0.7",
            "```",
            "",
            "## 行动项",
            "",
            "| 领域 | 优先级 | 建议 | 原因 |",
            "|---|:---:|---|---|",
        ]
    )

    for item in pool_tuning.get("recommendations", []):
        lines.append(
            f"| {item.get('area', '')} | {item.get('priority', '')} | {item.get('action', '')} | {item.get('reason', '')} |"
        )

    lines.append("")
    return "\n".join(lines)
