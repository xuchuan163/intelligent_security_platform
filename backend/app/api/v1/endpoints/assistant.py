from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import success
from app.infrastructure.database.session import get_db
from app.schemas.assistant import AssistantChatRequest, AssistantProjectExplainRequest
from app.services.agents.safety_assistant import safety_assistant
from app.services.profiles.service import get_project_profile

router = APIRouter()


@router.post("/chat")
def chat(body: AssistantChatRequest, db: Session = Depends(get_db)) -> dict:
    return success(safety_assistant.chat(body.message, body.context))


@router.post("/project-risk-explanation")
def project_risk_explanation(body: AssistantProjectExplainRequest, db: Session = Depends(get_db)) -> dict:
    profile = get_project_profile(db, body.project_id) or body.facts
    return success(safety_assistant.explain_project_risk(body.project_id, profile))
