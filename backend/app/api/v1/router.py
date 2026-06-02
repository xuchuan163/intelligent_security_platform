from fastapi import APIRouter
from app.api.v1.endpoints import assistant, dashboard, profiles, rules, work_orders

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(profiles.router, prefix="/profile", tags=["profiles"])
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work_orders"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
