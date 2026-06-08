from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.bayesian import AttributionRequest
from app.services.bayesian.service import BayesianGateError, analyze_attribution

router = APIRouter()


@router.post("/attribution")
def attribution_analysis(
    body: AttributionRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.ANALYSIS_ATTRIBUTION)),
):
    try:
        return success(analyze_attribution(db, body, current_user=current_user))
    except BayesianGateError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
