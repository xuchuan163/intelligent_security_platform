"""Bayesian L3 case labeling and dataset tests (Phase 5 L3-B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.bayesian.case_labels import (
    label_accident_case_row,
    resolve_outcome_id,
)
from app.domain.bayesian.prior import ACCIDENT_TYPE_ALIASES, FACTOR_BY_ID
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.bayesian.dataset import build_l3_training_row
from app.services.bayesian.gate import L3_MIN_CASES, check_l3_case_gate
from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS, seed_accident_cases

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "datasets" / "bayesian_l3_train_50.jsonl"


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_resolve_outcome_id_uses_alias_table():
    for accident_type, outcome_id in ACCIDENT_TYPE_ALIASES.items():
        assert resolve_outcome_id(accident_type) == outcome_id


def test_label_accident_case_row_maps_keywords_and_indicators():
    row = ACCIDENT_CASE_SEEDS[0]
    labels = label_accident_case_row(row)
    assert labels["case_id"] == "AC-MVP-001"
    assert labels["outcome_id"] == "fall_from_height"
    assert "mgmt_rectification_gap" in labels["factor_labels"]
    assert "human_violation" in labels["factor_labels"]
    assert all(factor_id in FACTOR_BY_ID for factor_id in labels["factor_labels"])


@pytest.mark.parametrize("seed", ACCIDENT_CASE_SEEDS[:10])
def test_build_l3_training_row_snapshot_fields(seed: dict):
    training_row = build_l3_training_row(seed)
    assert training_row["case_id"] == seed["accident_case_id"]
    assert training_row["outcome_id"] is not None
    assert isinstance(training_row["factor_labels"], dict)


def test_golden_jsonl_matches_seed_labels():
    assert GOLDEN_PATH.exists(), "golden dataset missing; regenerate from ACCIDENT_CASE_SEEDS"
    with GOLDEN_PATH.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    assert len(rows) == 50
    for golden, seed in zip(rows, ACCIDENT_CASE_SEEDS[:50], strict=True):
        expected = label_accident_case_row(seed)
        assert golden["case_id"] == expected["case_id"]
        assert golden["outcome_id"] == expected["outcome_id"]
        assert golden["factor_labels"] == expected["factor_labels"]


def test_seed_accident_cases_meets_l3_gate():
    db = _session()
    seed_accident_cases(db)
    result = check_l3_case_gate(db, tenant_id="CSCEC", min_cases=L3_MIN_CASES)
    assert result["case_count"] >= L3_MIN_CASES
    assert result["passed"] is True


def test_build_l3_training_row_from_db_model():
    db = _session()
    seed_accident_cases(db)
    row = db.query(AccidentCaseLibrary).filter(
        AccidentCaseLibrary.accident_case_id == "AC-MVP-001"
    ).one()
    training_row = build_l3_training_row(row)
    assert training_row["case_id"] == "AC-MVP-001"
    assert training_row["mapped_indicator_count"] is not None
