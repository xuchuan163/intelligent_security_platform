# PR: Phase 5 贝叶斯 L3 + 平台能力合并

**源分支：** `feature/phase5-bayesian-l3`  
**目标分支：** `master`  
**状态：** 已在本地 `master` 完成 merge；待 push 到 GitHub 后可在远端关闭 PR 或同步

---

## Summary

- 重新立项 Phase 5 贝叶斯 L3：DAG 结构、CPT 冷启动/训练、200 案例种子、L3 推理与传播路径
- 扩展 `POST /api/v1/analysis/attribution` 支持 `model_level=auto|L2|L3`，新增 `GET /api/v1/config/bayesian-versions`
- Neo4j 邻居低权重补充 evidence（`NEO4J_ENABLED=false` 时不影响 L3）
- 同步合并认证、规则引擎、Agent、四库等 Phase 2–4 能力（commit `594a54a`）
- 文档：`PHASE5_BAYESIAN_L3_ACCEPTANCE.md`、`docs/api/openapi.yaml`、路线图与收口说明更新

## Commits (feature → master)

| Commit | 说明 |
|---|---|
| `f42a873` | Sprint 1：L3-0/A/B（门禁、DAG、标注、200 种子） |
| `8247697` | L3-C：CPT 训练 + 校准回测 |
| `3d4233c` | L3-D/E/F：推理、API 路由、验收 |
| `594a54a` | 认证、规则引擎与多业务 API |
| `5ba228d` | Neo4j 补充 evidence + OpenAPI |
| `b3dc731` | Git Toolbox 项目配置 |

## Test plan

- [ ] `cd backend && py -3.12 -m pytest tests/domain/test_bayesian_*.py tests/services/test_bayesian_*.py -q`
- [ ] `py -3.12 scripts/check_bayesian_l3_gate.py --tenant-id CSCEC`（需 seed）
- [ ] `py -3.12 scripts/train_bayesian_l3.py --from-seeds`
- [ ] `py -3.12 scripts/run_bayesian_l3_backtest.py`
- [ ] `curl POST /api/v1/analysis/attribution` with `model_level=L3`
- [ ] `curl GET /api/v1/config/bayesian-versions`
- [ ] 确认 L3 响应 `need_human_review: true`

## 推送到 GitHub（网络可用时）

```powershell
git push intelligent_security_platform master
git push intelligent_security_platform feature/phase5-bayesian-l3
```

### 使用 gh 创建 PR（需安装 GitHub CLI）

```powershell
gh pr create --base master --head feature/phase5-bayesian-l3 --title "feat(phase5): Bayesian L3 attribution and platform merge" --body-file docs/PR_PHASE5_BAYESIAN_L3.md
```

若已在本地 merge `master`，也可直接 push `master` 完成远端合并。
