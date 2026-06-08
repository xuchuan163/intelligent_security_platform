"""CLI tests for run_profile_recalculate_benchmark.py (Phase 4-C.6)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "run_profile_recalculate_benchmark.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        command,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_profile_recalculate_benchmark_generates_reports(tmp_path):
    json_output = tmp_path / "profile_recalculate_benchmark.json"
    md_output = tmp_path / "profile_recalculate_benchmark.md"
    pool_md_output = tmp_path / "DB_POOL_TUNING.md"
    result = _run_script(
        "--projects",
        "6",
        "--tenant-id",
        "TENANT-RECALC-CLI",
        "--id-prefix",
        "RCLI",
        "--json-output",
        str(json_output),
        "--md-output",
        str(md_output),
        "--pool-md-output",
        str(pool_md_output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["benchmark"]["seed"]["totals"]["projects"] == 6
    assert len(payload["benchmark"]["scenarios"]) == 4
    assert "画像重算基线" in md_output.read_text(encoding="utf-8")
    assert "连接池调优建议" in pool_md_output.read_text(encoding="utf-8")
