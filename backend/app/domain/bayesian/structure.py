"""Bayesian L3 network structure loader and validation (Phase 5 L3-A.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from app.domain.bayesian.prior import FACTOR_BY_ID, OUTCOME_BY_ID

NodeKind = Literal["factor", "outcome"]

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_STRUCTURE_PATH = REPO_ROOT / "config" / "bayesian" / "network_structure.yaml"


@dataclass(frozen=True)
class NetworkNode:
    node_id: str
    kind: NodeKind
    category: str | None = None


@dataclass(frozen=True)
class NetworkEdge:
    source: str
    target: str


@dataclass(frozen=True)
class BayesianNetworkStructure:
    version: str
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]

    @property
    def node_ids(self) -> frozenset[str]:
        return frozenset(node.node_id for node in self.nodes)

    def parents_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(edge.source for edge in self.edges if edge.target == node_id)

    def children_of(self, node_id: str) -> tuple[str, ...]:
        return tuple(edge.target for edge in self.edges if edge.source == node_id)


class StructureValidationError(ValueError):
    """Raised when the DAG structure is invalid."""


def _validate_known_nodes(nodes: tuple[NetworkNode, ...]) -> None:
    for node in nodes:
        if node.kind == "factor" and node.node_id not in FACTOR_BY_ID:
            raise StructureValidationError(f"Unknown factor node: {node.node_id}")
        if node.kind == "outcome" and node.node_id not in OUTCOME_BY_ID:
            raise StructureValidationError(f"Unknown outcome node: {node.node_id}")


def _detect_cycle(node_ids: frozenset[str], edges: tuple[NetworkEdge, ...]) -> None:
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise StructureValidationError(f"Edge references unknown node: {edge.source}->{edge.target}")
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in adjacency[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if visited != len(node_ids):
        raise StructureValidationError("Network structure contains cycles")


def load_network_structure(path: Path | None = None) -> BayesianNetworkStructure:
    structure_path = path or DEFAULT_STRUCTURE_PATH
    payload = yaml.safe_load(structure_path.read_text(encoding="utf-8"))
    nodes = tuple(
        NetworkNode(
            node_id=str(item["id"]),
            kind=item["kind"],
            category=item.get("category"),
        )
        for item in payload.get("nodes", [])
    )
    edges = tuple(
        NetworkEdge(source=str(item["from"]), target=str(item["to"]))
        for item in payload.get("edges", [])
    )
    structure = BayesianNetworkStructure(
        version=str(payload.get("version", "unknown")),
        nodes=nodes,
        edges=edges,
    )
    _validate_known_nodes(structure.nodes)
    _detect_cycle(structure.node_ids, structure.edges)
    return structure
