# 数据库连接池调优建议（Phase 4-C.6）

> 本文档由 `run_profile_recalculate_benchmark.py` 生成/更新，供运维与容量规划参考。

## 当前运行时配置

- `DB_POOL_SIZE`：10
- `DB_MAX_OVERFLOW`：20
- `DB_POOL_PRE_PING`：True
- `DB_POOL_RECYCLE_SECONDS`：3600
- 单进程最大连接数：30

## 环境变量

```env
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_PRE_PING=true
DB_POOL_RECYCLE_SECONDS=3600
```

## 推荐档位

### local

- DB_POOL_SIZE=10
- DB_MAX_OVERFLOW=20
- DB_POOL_RECYCLE_SECONDS=3600

### staging_500

- DB_POOL_SIZE=15
- DB_MAX_OVERFLOW=25
- DB_POOL_RECYCLE_SECONDS=3600

### production_2000

- DB_POOL_SIZE=20
- DB_MAX_OVERFLOW=40
- DB_POOL_RECYCLE_SECONDS=3600

## 核算公式

```text
总连接上限 ≈ uvicorn_workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
建议 ≤ MySQL max_connections × 0.7
```

## 行动项

| 领域 | 优先级 | 建议 | 原因 |
|---|:---:|---|---|
| profile/recalculate | 高 | 全量重算耗时 128.603s 超过 30s SLA，优先拆分 profile_types 或引入队列任务。 | 单租户全量同步重算不适合作为在线 API，应改为后台 Job + 进度查询。 |
| 连接池 | 中 | 生产环境建议 DB_POOL_SIZE=15、DB_MAX_OVERFLOW=25；按 uvicorn workers 数核算总连接上限。 | 500 项目门禁压测已通过，但全量 projects 列表与重算任务叠加时需预留连接余量。 |
| 连接池 | 中 | 总连接预算：workers × (pool_size + max_overflow) ≤ MySQL max_connections × 0.7。 | 避免多 worker 进程各自持池导致数据库连接耗尽。 |
| profile/recalculate | 高 | 按项目批量预取 hazard/equipment，减少逐项目 N+1 查询；工人/分包商画像可分片异步重算。 | 当前重算循环内逐实体查询是批量耗时的主要来源。 |
| GET /projects | 高 | 强制分页（默认 page_size≤50）并对排名/列表接口增加 Redis 缓存。 | 2000 项目压测中 projects_list P95 曾超 500ms，全量扫描是容量敏感点。 |
| 运维 | 低 | 开启 pool_pre_ping（已默认）并监控 checked_out/overflow 指标。 | 长事务重算期间可及时发现僵死连接与池耗尽。 |
