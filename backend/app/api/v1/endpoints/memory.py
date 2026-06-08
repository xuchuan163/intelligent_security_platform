from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.infrastructure.redis_client import RedisLike, build_redis_client
from app.schemas.memory import MemorySessionUpsertRequest
from app.services.memory.service import append_session_memory, get_session_memory

router = APIRouter()


def get_redis_client() -> RedisLike:
    try:
        return build_redis_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc


@router.post("/session")
def upsert_memory_session(
    body: MemorySessionUpsertRequest,
    db: Session = Depends(get_db),
    redis_client: RedisLike = Depends(get_redis_client),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    try:
        return success(
            append_session_memory(
                db,
                redis_client,
                current_user=current_user,
                session_id=body.session_id,
                message=body.message.model_dump(exclude_none=True),
                context=body.context,
                summary=body.summary,
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc


@router.get("/session")
def read_memory_session(
    session_id: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    redis_client: RedisLike = Depends(get_redis_client),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    try:
        data = get_session_memory(db, redis_client, current_user=current_user, session_id=session_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc
    if data is None:
        raise HTTPException(status_code=404, detail="Memory session not found")
    return success(data)
