from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.database.models import Hazard, Project, Subcontractor, Worker
from app.infrastructure.neo4j_client import Neo4jClient


def sync_graph_from_mysql(db: Session, client: Neo4jClient) -> dict[str, int]:
    projects = db.query(Project).filter(Project.status == "active").all()
    subcontractors = db.query(Subcontractor).filter(Subcontractor.status == "active").all()
    workers = db.query(Worker).filter(Worker.status == "active").all()
    hazards = db.query(Hazard).all()

    for project in projects:
        client.run_query(
            """
            MERGE (p:Project {project_id: $project_id})
            SET p.tenant_id = $tenant_id,
                p.org_path = $org_path,
                p.project_name = $project_name,
                p.status = $status
            """,
            {
                "project_id": project.project_id,
                "tenant_id": project.tenant_id,
                "org_path": project.org_path,
                "project_name": project.project_name,
                "status": project.status,
            },
        )

    for subcontractor in subcontractors:
        client.run_query(
            """
            MERGE (s:Subcontractor {subcontractor_id: $subcontractor_id})
            SET s.tenant_id = $tenant_id,
                s.org_path = $org_path,
                s.subcontractor_name = $subcontractor_name,
                s.status = $status
            """,
            {
                "subcontractor_id": subcontractor.subcontractor_id,
                "tenant_id": subcontractor.tenant_id,
                "org_path": subcontractor.org_path,
                "subcontractor_name": subcontractor.subcontractor_name,
                "status": subcontractor.status,
            },
        )

    for worker in workers:
        client.run_query(
            """
            MERGE (w:Worker {worker_id: $worker_id})
            SET w.tenant_id = $tenant_id,
                w.org_path = $org_path,
                w.worker_name_masked = $worker_name_masked,
                w.work_type = $work_type,
                w.status = $status
            """,
            {
                "worker_id": worker.worker_id,
                "tenant_id": worker.tenant_id,
                "org_path": worker.org_path,
                "worker_name_masked": worker.worker_name_masked,
                "work_type": worker.work_type,
                "status": worker.status,
            },
        )
        if worker.project_id:
            client.run_query(
                """
                MATCH (w:Worker {worker_id: $worker_id}), (p:Project {project_id: $project_id})
                MERGE (w)-[:WORKS_ON]->(p)
                """,
                {"worker_id": worker.worker_id, "project_id": worker.project_id},
            )
        if worker.subcontractor_id and worker.project_id:
            client.run_query(
                """
                MATCH (s:Subcontractor {subcontractor_id: $subcontractor_id}),
                      (p:Project {project_id: $project_id})
                MERGE (s)-[:SUBCONTRACTS]->(p)
                """,
                {
                    "subcontractor_id": worker.subcontractor_id,
                    "project_id": worker.project_id,
                },
            )

    for hazard in hazards:
        client.run_query(
            """
            MERGE (h:Hazard {hazard_id: $hazard_id})
            SET h.tenant_id = $tenant_id,
                h.org_path = $org_path,
                h.hazard_type = $hazard_type,
                h.hazard_level = $hazard_level,
                h.status = $status,
                h.is_major = $is_major
            """,
            {
                "hazard_id": hazard.hazard_id,
                "tenant_id": hazard.tenant_id,
                "org_path": hazard.org_path,
                "hazard_type": hazard.hazard_type,
                "hazard_level": hazard.hazard_level,
                "status": hazard.status,
                "is_major": hazard.is_major,
            },
        )
        client.run_query(
            """
            MATCH (p:Project {project_id: $project_id}), (h:Hazard {hazard_id: $hazard_id})
            MERGE (p)-[:HAS_HAZARD]->(h)
            """,
            {"project_id": hazard.project_id, "hazard_id": hazard.hazard_id},
        )
        if hazard.subcontractor_id:
            client.run_query(
                """
                MATCH (s:Subcontractor {subcontractor_id: $subcontractor_id}),
                      (h:Hazard {hazard_id: $hazard_id})
                MERGE (s)-[:HAS_HAZARD]->(h)
                """,
                {
                    "subcontractor_id": hazard.subcontractor_id,
                    "hazard_id": hazard.hazard_id,
                },
            )

    return {
        "projects": len(projects),
        "subcontractors": len(subcontractors),
        "workers": len(workers),
        "hazards": len(hazards),
    }
