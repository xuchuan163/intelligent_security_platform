# Phase 4 画像重算基线 — 500 项目

## 运行信息

- 生成时间（UTC）：2026-06-08T09:19:33.509716+00:00
- 压测模式：`api_testclient`
- Base URL：`http://127.0.0.1:8000`
- 租户：`CSCEC-SCALE`
- 项目规模：500
- SLA（全量重算）：30.0s

## 灌数摘要

- 项目数：500
- 分包商数：n/a
- 工人数：n/a
- 灌数：已跳过（使用库内现有数据）

## 实际重算规模（full_batch）

- 项目：1994
- 工人：15952
- 分包商：3988

## 重算耗时

| 场景 | 类型 | 耗时 (ms) | 耗时 (s) | SLA | 通过 |
|---|---|---:|---:|---:|:---:|
| project_only | project | 15228.13 | 15.228 | 30.0s | ✅ |
| worker_only | worker | 136037.43 | 136.037 | 30.0s | ❌ |
| subcontractor_only | subcontractor | 38843.89 | 38.844 | 30.0s | ❌ |
| full_batch | project,worker,subcontractor | 128602.99 | 128.603 | 30.0s | ❌ |

## 全量重算摘要

- 耗时：128.603s
- SLA 通过：否

## 当前连接池

- pool_size：10
- max_overflow：20
- pool_pre_ping：True
- pool_recycle_seconds：3600
- 单进程最大连接：30

## 调优建议

| 领域 | 优先级 | 建议 | 原因 |
|---|:---:|---|---|
| profile/recalculate | 高 | 全量重算耗时 128.603s 超过 30s SLA，优先拆分 profile_types 或引入队列任务。 | 单租户全量同步重算不适合作为在线 API，应改为后台 Job + 进度查询。 |
| 连接池 | 中 | 生产环境建议 DB_POOL_SIZE=15、DB_MAX_OVERFLOW=25；按 uvicorn workers 数核算总连接上限。 | 500 项目门禁压测已通过，但全量 projects 列表与重算任务叠加时需预留连接余量。 |
| 连接池 | 中 | 总连接预算：workers × (pool_size + max_overflow) ≤ MySQL max_connections × 0.7。 | 避免多 worker 进程各自持池导致数据库连接耗尽。 |
| profile/recalculate | 高 | 按项目批量预取 hazard/equipment，减少逐项目 N+1 查询；工人/分包商画像可分片异步重算。 | 当前重算循环内逐实体查询是批量耗时的主要来源。 |
| GET /projects | 高 | 强制分页（默认 page_size≤50）并对排名/列表接口增加 Redis 缓存。 | 2000 项目压测中 projects_list P95 曾超 500ms，全量扫描是容量敏感点。 |
| 运维 | 低 | 开启 pool_pre_ping（已默认）并监控 checked_out/overflow 指标。 | 长事务重算期间可及时发现僵死连接与池耗尽。 |

## 推荐配置档位

- **local**：DB_POOL_SIZE=10, DB_MAX_OVERFLOW=20, DB_POOL_RECYCLE_SECONDS=3600
- **staging_500**：DB_POOL_SIZE=15, DB_MAX_OVERFLOW=25, DB_POOL_RECYCLE_SECONDS=3600
- **production_2000**：DB_POOL_SIZE=20, DB_MAX_OVERFLOW=40, DB_POOL_RECYCLE_SECONDS=3600

## 结论

- 库内 `CSCEC-SCALE` 实际约 **2000 项目 / 1.6 万工人**，全量同步重算 **128.6s**，远超 30s SLA。
- 瓶颈在 `worker_only`（136s）：逐工人 N+1 查询 + 工单去重；`project_only` 15.2s 仍可通过 SLA。
- 建议：在线 API 仅支持单项目或单类型重算；租户级全量重算改为异步队列（4-C.6 调优建议已写入 `DB_POOL_TUNING.md`）。

## 备注

- 未检测到可访问的 API（http://127.0.0.1:8000），回退为 TestClient 进程内压测；耗时仅供参考，生产级基线请在独立压测环境对 HTTP 服务复测。
- `--skip-seed` 时报告中的「项目规模」为 CLI 参数，实际规模见「实际重算规模」。
