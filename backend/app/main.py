from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.responses import success
from app.api.v1.router import api_router

app = FastAPI(title="中建智慧安全平台 MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict:
    return success({"status": "healthy"})
