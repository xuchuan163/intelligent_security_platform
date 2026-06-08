"""Generate tests/datasets/bayesian_l3_train_50.jsonl from seed cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.bayesian.case_labels import label_accident_case_row
from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS

OUTPUT = BACKEND_ROOT / "tests" / "datasets" / "bayesian_l3_train_50.jsonl"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for seed in ACCIDENT_CASE_SEEDS[:50]:
        labels = label_accident_case_row(seed)
        payload = {
            "case_id": labels["case_id"],
            "outcome_id": labels["outcome_id"],
            "factor_labels": labels["factor_labels"],
            "profile_type": labels["profile_type"],
            "warning_indicators": labels["warning_indicators"],
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} rows to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
