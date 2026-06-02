# 中建智慧安全平台 MVP

面向中建集团项目工地安全管理的智能平台一期全栈 MVP：FastAPI 后端、Vue3 前端、MySQL 主库、三类风险画像、强规则预警、工单闭环和 Qwen 安全助手。

## 安全提醒

.env 不提交。阿里云 Key 和数据库密码从环境变量读取。

## 本地启动

1. copy .env.example .env 并填写 DASHSCOPE_API_KEY
2. docker compose -f deploy/docker-compose.yml up -d
3. cd backend && pip install -e . && alembic upgrade head && python scripts/seed_demo_data.py
4. python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
5. cd frontend && npm install && npm run dev

- 后端 API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- 前端: http://127.0.0.1:5173
