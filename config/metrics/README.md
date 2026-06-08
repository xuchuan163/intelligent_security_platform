# Metrics Config

本目录用于 P1 阶段承载指标语义层配置。

当前状态：

- 运行时指标事实来源是 MySQL 表 `metric_catalog`；
- API 为 `GET /api/v1/metrics/catalog` 和 `GET /api/v1/metrics/{metric_code}`；
- 本目录暂不参与运行时加载。

计划文件：

- `catalog.yaml`

指标配置化完成前，不要把此目录作为生产指标来源。

