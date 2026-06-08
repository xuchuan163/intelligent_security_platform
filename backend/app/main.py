from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.responses import success
from app.core.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.infrastructure.milvus_client import probe_milvus_status
from app.infrastructure.neo4j_client import probe_neo4j_status
from app.infrastructure.redis_client import probe_redis_status

app = FastAPI(title="中建智慧安全平台 MVP", version="0.1.0")

register_exception_handlers(app)

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
    redis_status = probe_redis_status()
    overall = "healthy" if redis_status.status == "ready" else "degraded"
    return success(
        {
            "status": overall,
            "redis": redis_status.as_dict(),
            "milvus": probe_milvus_status().as_dict(),
            "neo4j": probe_neo4j_status().as_dict(),
        }
    )
