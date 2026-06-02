from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.services.dashboard.service import get_dashboard_overview
from app.core.responses import success

router = APIRouter()


@router.get("/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    try:
        data = get_dashboard_overview(db)
        return success(data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
