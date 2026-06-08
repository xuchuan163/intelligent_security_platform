"""CLI tests for run_baseline_2000.py (Phase 4-C.5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "run_baseline_2000.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        command,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_baseline_2000_generates_target_report(tmp_path):
    json_output = tmp_path / "baseline_2000.json"
    md_output = tmp_path / "baseline_2000.md"
    result = _run_script(
        "--projects",
        "6",
        "--tenant-id",
        "TENANT-BASELINE-2000",
        "--id-prefix",
        "B2K",
        "--iterations",
        "3",
        "--concurrency",
        "1",
        "--json-output",
        str(json_output),
        "--md-output",
        str(md_output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["seed"]["totals"]["projects"] == 6
    assert "2000 项目目标压测" in md_output.read_text(encoding="utf-8")
