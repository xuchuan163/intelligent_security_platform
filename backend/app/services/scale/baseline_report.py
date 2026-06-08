"""Markdown report builder for scale performance baselines (Phase 4-C.3)."""

from __future__ import annotations

from typing import Any


def render_baseline_markdown(
    *,
    title: str,
    seed_summary: dict[str, Any],
    load_report: dict[str, Any],
    notes: list[str] | None = None,
) -> str:
    meta = load_report.get("meta", {})
    summary = load_report.get("summary", {})
    endpoints = load_report.get("endpoints", [])
    totals = seed_summary.get("totals", {})

    lines = [
        f"# {title}",
        "",
        "## 运行信息",
        "",
        f"- 生成时间（UTC）：{meta.get('generated_at', 'n/a')}",
        f"- 压测模式：`{meta.get('mode', 'http')}`",
        f"- Base URL：`{meta.get('base_url', 'n/a')}`",
        f"- 租户：`{meta.get('tenant_id', 'n/a')}`",
        f"- 每端点请求数：{meta.get('iterations', 'n/a')}",
        f"- 并发：{meta.get('concurrency', 'n/a')}",
        "",
        "## 灌数摘要",
        "",
        f"- 项目数：{totals.get('projects', 'n/a')}",
        f"- 分包商数：{totals.get('subcontractors', 'n/a')}",
        f"- 工人数：{totals.get('workers', 'n/a')}",
        f"- 项目画像：{seed_summary.get('project_profiles_upserted', 0)}",
        f"- 工人画像：{seed_summary.get('worker_profiles_upserted', 0)}",
        f"- 分包商画像：{seed_summary.get('subcontractor_profiles_upserted', 0)}",
        "",
        "## 总体结果",
        "",
        f"- 总请求数：{summary.get('total_requests', 0)}",
        f"- 错误数：{summary.get('total_errors', 0)}",
        f"- 错误率：{summary.get('error_rate', 0):.4f}",
        f"- SLA 通过：{'是' if summary.get('sla_passed') else '否'}",
        "",
        "## 端点延迟（毫秒）",
        "",
        "| 端点 | P50 | P95 | P99 | Max | 错误率 | SLA P95 | 通过 |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]

    for endpoint in endpoints:
        latency = endpoint.get("latency_ms", {})
        lines.append(
            "| {name} | {p50} | {p95} | {p99} | {max} | {error_rate:.4f} | {sla} | {passed} |".format(
                name=endpoint.get("name", ""),
                p50=latency.get("p50", 0),
                p95=latency.get("p95", 0),
                p99=latency.get("p99", 0),
                max=latency.get("max", 0),
                error_rate=endpoint.get("error_rate", 0),
                sla=endpoint.get("sla_p95_ms", "-"),
                passed="✅" if endpoint.get("sla_passed") else "❌",
            )
        )

    if summary.get("sla_failures"):
        lines.extend(["", "## SLA 未通过项", ""])
        for item in summary["sla_failures"]:
            lines.append(f"- {item}")

    if notes:
        lines.extend(["", "## 备注", ""])
        for note in notes:
            lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)
