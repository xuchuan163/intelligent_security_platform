"""CLI tests for run_case_backtest.py (Phase 4-B.5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "run_case_backtest.py"
DATASET_PATH = BACKEND_ROOT / "tests" / "datasets" / "case_backtest_30.jsonl"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        command,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_case_backtest_dataset_mode_prints_json_summary():
    result = _run_script("--source", "dataset", "--dataset", str(DATASET_PATH), "--min-hit-rate", "1.0")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["meta"]["source"] == "dataset"
    assert payload["summary"]["total_cases"] == 30
    assert payload["summary"]["hit_rate"] == 1.0
    assert "coverage" in payload["summary"]
    assert len(payload["evaluations"]) == 30


def test_run_case_backtest_writes_output_file(tmp_path):
    output_path = tmp_path / "case_backtest_report.json"
    result = _run_script(
        "--source",
        "dataset",
        "--dataset",
        str(DATASET_PATH),
        "--output",
        str(output_path),
        "--min-hit-rate",
        "1.0",
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["passed_cases"] == 30


def test_run_case_backtest_fails_when_hit_rate_below_threshold():
    result = _run_script("--source", "dataset", "--dataset", str(DATASET_PATH), "--min-hit-rate", "1.1")

    assert result.returncode == 1
