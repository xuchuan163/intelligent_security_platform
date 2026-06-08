from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints._errors import db_guard
from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.infrastructure.neo4j_client import Neo4jClient, build_neo4j_client_optional
from app.services.graph.neighbors import get_graph_neighbors
from sqlalchemy.orm import Session

router = APIRouter()


def get_neo4j_client_optional() -> Neo4jClient | None:
    return build_neo4j_client_optional()


@router.get("/neighbors")
def graph_neighbors(
    node_type: str = Query(..., description="project | subcontractor | worker | hazard"),
    node_id: str = Query(..., description="Business node id"),
    depth: int = Query(1, ge=1, le=1),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.DASHBOARD_READ)),
    neo4j_client: Neo4jClient | None = Depends(get_neo4j_client_optional),
) -> dict:
    _ = db

    def query() -> dict:
        if neo4j_client is None:
            raise HTTPException(status_code=503, detail="Neo4j is not available")
        report = get_graph_neighbors(
            neo4j_client,
            node_type=node_type,
            node_id=node_id,
            depth=depth,
            current_user=current_user,
        )
        if report is None:
            raise HTTPException(status_code=404, detail="Graph node not found or not accessible")
        return report

    return success(db_guard(query))
