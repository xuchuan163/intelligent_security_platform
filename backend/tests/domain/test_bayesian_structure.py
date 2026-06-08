"""Bayesian L3 network structure tests (Phase 5 L3-A.2)."""

from __future__ import annotations

import pytest

from app.domain.bayesian.prior import FACTOR_BY_ID, OUTCOME_BY_ID
from app.domain.bayesian.structure import (
    StructureValidationError,
    load_network_structure,
)


def test_load_network_structure_covers_all_prior_nodes():
    structure = load_network_structure()
    factor_ids = {node.node_id for node in structure.nodes if node.kind == "factor"}
    outcome_ids = {node.node_id for node in structure.nodes if node.kind == "outcome"}
    assert factor_ids == set(FACTOR_BY_ID)
    assert outcome_ids == set(OUTCOME_BY_ID)


def test_network_structure_is_acyclic():
    structure = load_network_structure()
    indegree = {node_id: 0 for node_id in structure.node_ids}
    children: dict[str, list[str]] = {node_id: [] for node_id in structure.node_ids}
    for edge in structure.edges:
        indegree[edge.target] += 1
        children[edge.source].append(edge.target)

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    assert visited == len(structure.node_ids)


def test_unknown_factor_node_rejected(tmp_path):
    yaml_text = """
version: test
nodes:
  - { id: unknown_factor, kind: factor, category: 人 }
edges: []
"""
    path = tmp_path / "bad_structure.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(StructureValidationError, match="Unknown factor"):
        load_network_structure(path)
