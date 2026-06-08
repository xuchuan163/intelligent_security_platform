"""CLI tests for run_baseline_100.py (Phase 4-C.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "run_baseline_100.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        command,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_baseline_100_generates_markdown_and_json(tmp_path):
    json_output = tmp_path / "baseline_100.json"
    md_output = tmp_path / "baseline_100.md"
    result = _run_script(
        "--projects",
        "5",
        "--tenant-id",
        "TENANT-BASELINE-100",
        "--id-prefix",
        "B100",
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
    assert json_output.is_file()
    assert md_output.is_file()

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["load_test"]["summary"]["total_requests"] == 12
    assert "Phase 4" in md_output.read_text(encoding="utf-8")
