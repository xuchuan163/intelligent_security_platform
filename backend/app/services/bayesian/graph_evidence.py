"""Neo4j graph neighbors as low-weight supplemental L3 evidence (Phase 5 L3-D.5)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.security import MockUser
from app.infrastructure.neo4j_client import Neo4jClient, build_neo4j_client_optional
from app.services.graph.neighbors import get_graph_neighbors

GRAPH_FACTOR_BOOST_CAP = 0.15

RELATIONSHIP_FACTOR_BOOSTS: dict[str, tuple[str, float]] = {
    "HAS_HAZARD": ("mgmt_rectification_gap", 0.12),
    "WORKS_ON": ("human_violation", 0.08),
    "SUBCONTRACTS": ("mgmt_subcontractor_weak", 0.10),
}

HAZARD_TYPE_FACTOR_BOOSTS: dict[str, tuple[str, float]] = {
    "scaffold": ("machine_guard_failure", 0.10),
    "electrical": ("method_permit_irregular", 0.10),
    "lifting": ("env_cross_operation", 0.09),
    "confined_space": ("method_plan_missing", 0.09),
}


def _neighbor_factor_hint(neighbor: dict[str, Any]) -> tuple[str, float] | None:
    relationship = str(neighbor.get("relationship") or "")
    if relationship in RELATIONSHIP_FACTOR_BOOSTS:
        return RELATIONSHIP_FACTOR_BOOSTS[relationship]

    props = neighbor.get("properties") or {}
    hazard_type = str(props.get("hazard_type") or "").lower()
    if hazard_type in HAZARD_TYPE_FACTOR_BOOSTS:
        return HAZARD_TYPE_FACTOR_BOOSTS[hazard_type]

    node_type = str(neighbor.get("node_type") or "").lower()
    if node_type == "hazard":
        return ("mgmt_oversight_gap", 0.08)
    if node_type == "worker":
        return ("human_training_gap", 0.07)
    if node_type == "subcontractor":
        return ("mgmt_subcontractor_weak", 0.08)
    return None


def merge_graph_factor_boosts(
    boosts: dict[str, float],
    *,
    factor_id: str,
    strength: float,
) -> None:
    capped = min(GRAPH_FACTOR_BOOST_CAP, max(0.0, strength))
    boosts[factor_id] = min(GRAPH_FACTOR_BOOST_CAP, max(boosts.get(factor_id, 0.0), capped))


def collect_neighbors_for_attribution(
    client: Neo4jClient | None,
    *,
    project_id: str,
    worker_id: str | None,
    subcontractor_id: str | None,
    current_user: MockUser,
) -> list[dict[str, Any]]:
    if client is None:
        return []

    neighbors: list[dict[str, Any]] = []
    anchors: list[tuple[str, str]] = [("project", project_id)]
    if worker_id:
        anchors.append(("worker", worker_id))
    if subcontractor_id:
        anchors.append(("subcontractor", subcontractor_id))

    for node_type, node_id in anchors:
        payload = get_graph_neighbors(
            client,
            node_type=node_type,
            node_id=node_id,
            depth=1,
            current_user=current_user,
        )
        if not payload:
            continue
        for item in payload.get("neighbors", []):
            neighbors.append({**item, "anchor_type": node_type, "anchor_id": node_id})
    return neighbors


def build_graph_supplemental_evidence(
    neighbors: list[dict[str, Any]],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    boosts: dict[str, float] = {}
    records: list[dict[str, Any]] = []

    for neighbor in neighbors:
        hint = _neighbor_factor_hint(neighbor)
        if hint is None:
            continue
        factor_id, strength = hint
        merge_graph_factor_boosts(boosts, factor_id=factor_id, strength=strength)
        props = neighbor.get("properties") or {}
        records.append(
            {
                "factor_id": factor_id,
                "source": "graph",
                "field": f"neo4j.{neighbor.get('relationship')}.{neighbor.get('node_type')}",
                "value": props.get("hazard_id") or props.get("worker_id") or props.get("subcontractor_id"),
                "strength": round(min(GRAPH_FACTOR_BOOST_CAP, strength), 4),
                "anchor_type": neighbor.get("anchor_type"),
                "anchor_id": neighbor.get("anchor_id"),
                "relationship": neighbor.get("relationship"),
                "weight_tier": "supplemental",
            }
        )
    return boosts, records


def collect_graph_supplemental_evidence(
    *,
    project_id: str,
    worker_id: str | None,
    subcontractor_id: str | None,
    current_user: MockUser,
    client: Neo4jClient | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]], str]:
    """Return factor boosts, evidence rows, and neo4j_status: disabled|unavailable|ready|applied."""
    if client is not None:
        resolved_client = client
    elif not settings.neo4j_enabled:
        return {}, [], "disabled"
    else:
        resolved_client = build_neo4j_client_optional()
        if resolved_client is None:
            return {}, [], "unavailable"

    neighbors = collect_neighbors_for_attribution(
        resolved_client,
        project_id=project_id,
        worker_id=worker_id,
        subcontractor_id=subcontractor_id,
        current_user=current_user,
    )
    boosts, records = build_graph_supplemental_evidence(neighbors)
    return boosts, records, "applied" if records else "ready"
