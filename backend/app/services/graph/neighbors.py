from __future__ import annotations

from typing import Any

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.neo4j_client import Neo4jClient

NODE_LABELS = {
    "project": "Project",
    "subcontractor": "Subcontractor",
    "worker": "Worker",
    "hazard": "Hazard",
}

NODE_ID_FIELDS = {
    "project": "project_id",
    "subcontractor": "subcontractor_id",
    "worker": "worker_id",
    "hazard": "hazard_id",
}


def _node_visible(node: dict[str, Any], current_user: MockUser) -> bool:
    tenant_id = node.get("tenant_id")
    if tenant_id and tenant_id != current_user.tenant_id:
        return False
    if current_user.data_scope == DataScope.ORG and current_user.org_path:
        org_path = node.get("org_path")
        if org_path and not str(org_path).startswith(current_user.org_path):
            return False
    if current_user.scope_type == ScopeType.PROJECT and current_user.authorized_project_ids:
        project_id = node.get("project_id")
        if project_id and project_id not in current_user.authorized_project_ids:
            return False
    return True


def get_graph_neighbors(
    client: Neo4jClient,
    *,
    node_type: str,
    node_id: str,
    depth: int = 1,
    current_user: MockUser,
) -> dict[str, Any] | None:
    label = NODE_LABELS.get(node_type)
    id_field = NODE_ID_FIELDS.get(node_type)
    if not label or not id_field:
        return None

    depth = max(1, min(depth, 1))
    anchor_rows = client.run_query(
        f"""
        MATCH (n:{label} {{{id_field}: $node_id}})
        RETURN labels(n) AS labels, properties(n) AS properties
        """,
        {"node_id": node_id},
    )
    if not anchor_rows:
        return None

    anchor_props = anchor_rows[0]["properties"]
    if not _node_visible(anchor_props, current_user):
        return None

    neighbor_rows = client.run_query(
        f"""
        MATCH (n:{label} {{{id_field}: $node_id}})-[r]-(m)
        RETURN type(r) AS relationship,
               labels(m) AS labels,
               properties(m) AS properties
        LIMIT 50
        """,
        {"node_id": node_id},
    )

    neighbors: list[dict[str, Any]] = []
    for row in neighbor_rows:
        props = row.get("properties") or {}
        if not _node_visible(props, current_user):
            continue
        labels = row.get("labels") or []
        neighbors.append(
            {
                "relationship": row.get("relationship"),
                "labels": labels,
                "node_type": labels[0].lower() if labels else None,
                "properties": props,
            }
        )

    return {
        "node_type": node_type,
        "node_id": node_id,
        "depth": depth,
        "anchor": {
            "labels": anchor_rows[0]["labels"],
            "properties": anchor_props,
        },
        "neighbors": neighbors,
        "neighbor_count": len(neighbors),
    }
