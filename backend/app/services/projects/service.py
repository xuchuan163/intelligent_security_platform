from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import Project


def list_accessible_projects(db: Session, current_user: MockUser | None = None) -> list[dict]:
    query = db.query(Project.project_id, Project.project_name).filter(Project.status == "active")
    if current_user:
        query = apply_data_scope(query, Project, current_user)
    rows = query.order_by(Project.project_name).all()
    return [{"project_id": row.project_id, "project_name": row.project_name} for row in rows]
