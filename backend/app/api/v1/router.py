from fastapi import APIRouter
from app.api.v1.endpoints import (
    agent,
    analysis,
    auth,
    assistant,
    cases,
    config,
    dashboard,
    files,
    graph,
    hazards,
    memory,
    metrics,
    profiles,
    projects,
    rag,
    reports,
    rules,
    webhooks,
    work_orders,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/case", tags=["cases"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(profiles.router, prefix="/profile", tags=["profiles"])
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(hazards.router, prefix="/projects", tags=["hazards"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work_orders"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
