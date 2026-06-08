"""Bayesian L3 CPT training and calibration tests (Phase 5 L3-C)."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.bayesian.case_labels import label_accident_case_row
from app.services.bayesian.calibration import (
    factor_hit_rate,
    outcome_brier_score,
    run_l3_calibration,
    split_training_rows,
)
from app.services.bayesian.training import (
    build_training_rows_from_seeds,
    learn_cpt_from_training_rows,
    load_cpt_learned,
    write_cpt_learned_file,
)
from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "datasets" / "bayesian_l3_train_50.jsonl"


def test_learn_cpt_from_golden_rows_is_reproducible():
    with GOLDEN_PATH.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    first = learn_cpt_from_training_rows(rows, alpha=1.0, model_version="bayesian-l3-test-v1")
    second = learn_cpt_from_training_rows(rows, alpha=1.0, model_version="bayesian-l3-test-v1")
    assert first["nodes"]["human_violation"]["probabilities"] == second["nodes"]["human_violation"]["probabilities"]
    assert first["case_count"] == 50
    assert "conditional_probabilities" in first["nodes"]["fall_from_height"]


def test_write_and_load_cpt_learned_file(tmp_path: Path):
    rows = [label_accident_case_row(seed) for seed in ACCIDENT_CASE_SEEDS[:20]]
    payload = learn_cpt_from_training_rows(rows)
    target = tmp_path / "cpt_learned.json"
    write_cpt_learned_file(payload, target)
    loaded = load_cpt_learned(target)
    assert loaded["model_level"] == "L3"
    assert loaded["case_count"] == 20
    assert "mgmt_rectification_gap" in loaded["nodes"]


def test_split_training_rows_preserves_total():
    rows = build_training_rows_from_seeds()
    train, holdout = split_training_rows(rows, holdout_ratio=0.2, seed=7)
    assert len(train) + len(holdout) == len(rows)
    assert holdout


def test_calibration_on_seed_cases_meets_factor_hit_rate_threshold():
    rows = build_training_rows_from_seeds()
    report = run_l3_calibration(rows, holdout_ratio=0.2, alpha=1.0, seed=42, min_factor_hit_rate=0.55)
    assert report["train_cases"] > 0
    assert report["holdout_cases"] > 0
    assert report["factor_hit_rate"] >= 0.55
    assert report["passed"] is True
    assert 0.0 <= report["outcome_brier_score"] <= 1.0


def test_factor_hit_rate_and_brier_use_holdout_payload():
    rows = build_training_rows_from_seeds()
    train, holdout = split_training_rows(rows, holdout_ratio=0.2, seed=1)
    cpt_payload = learn_cpt_from_training_rows(train)
    hit_rate = factor_hit_rate(holdout, cpt_payload=cpt_payload)
    brier = outcome_brier_score(holdout, cpt_payload=cpt_payload)
    assert 0.0 <= hit_rate <= 1.0
    assert 0.0 <= brier <= 1.0
