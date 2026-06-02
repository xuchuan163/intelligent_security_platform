# MVP API Design

## Scope

Implement the backend MVP API set from `技术参考文档/接口设计文档.md` as a stable FastAPI surface under `/api/v1`.

Included endpoints:

- `GET /health`
- `GET /dashboard/overview`
- `GET /profile/project/{project_id}`
- `GET /profile/worker/{worker_id}`
- `GET /profile/subcontractor/{subcontractor_id}`
- `GET /profile/ranking/projects`
- `POST /profile/recalculate`
- `GET /rules/triggers`
- `GET /work-orders`
- `POST /work-orders`
- `PATCH /work-orders/{work_order_id}/status`
- `POST /assistant/chat`
- `POST /assistant/project-risk-explanation`

## Architecture

Keep the existing layered structure:

- API routers live in `backend/app/api/v1/endpoints/`.
- Request and response contracts live in `backend/app/schemas/`.
- Business logic stays in `backend/app/services/`.
- SQLAlchemy models remain in `backend/app/infrastructure/database/models.py`.

The implementation should repair route wiring and schema clarity without a broad refactor.

## API Behavior

All successful business responses use:

```json
{"code": "SUCCESS", "message": "ok", "data": {}}
```

Database failures return HTTP 503. Missing profiles and work orders return HTTP 404. Invalid work-order transitions return HTTP 409.

## Data Rules

`POST /profile/recalculate` recalculates project risk profiles only. Worker and subcontractor profiles remain populated by the demo seed script for the MVP.

`GET /rules/triggers` returns the latest 50 rule trigger rows from `RuleTriggerLog`, using fields that exist in the current model.

`POST /assistant/project-risk-explanation` accepts `project_id` and optional `facts`; stored profile data is preferred over user-supplied facts when present.

## Testing

Add API tests that assert:

- the rules router is mounted at `/api/v1/rules/triggers`;
- work-order create and status update use typed request bodies;
- project profile recalculation route exists and returns the documented response shape when the database layer is available;
- assistant project explanation accepts optional facts.

