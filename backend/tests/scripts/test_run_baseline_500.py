"""CLI tests for run_baseline_500.py (Phase 4-C.4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "run_baseline_500.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        command,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_baseline_500_generates_gate_report(tmp_path):
    json_output = tmp_path / "baseline_500.json"
    md_output = tmp_path / "baseline_500.md"
    result = _run_script(
        "--projects",
        "8",
        "--tenant-id",
        "TENANT-BASELINE-500",
        "--id-prefix",
        "B500",
        "--iterations",
        "4",
        "--concurrency",
        "2",
        "--json-output",
        str(json_output),
        "--md-output",
        str(md_output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["seed"]["totals"]["projects"] == 8
    assert payload["load_test"]["summary"]["sla_passed"] is True
    assert "500 项目门禁压测" in md_output.read_text(encoding="utf-8")
