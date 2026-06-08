from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.rag import RagSearchRequest
from app.services.rag.service import search_rag

router = APIRouter()


@router.post("/search")
def rag_search(
    body: RagSearchRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    return success(
        search_rag(
            db,
            tenant_id=current_user.tenant_id,
            query=body.query,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
        )
    )
