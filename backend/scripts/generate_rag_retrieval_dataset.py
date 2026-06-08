"""Generate rag_retrieval_30.jsonl from seeded accident cases and knowledge chunks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS  # noqa: E402
from app.services.rag.chunking import load_knowledge_chunks  # noqa: E402

OUTPUT_PATH = BACKEND_ROOT / "tests" / "datasets" / "rag_retrieval_30.jsonl"
KNOWLEDGE_DIR = REPO_ROOT / "config" / "knowledge"


def _accident_query(seed: dict) -> str:
    # MySQL keyword fallback uses a single LIKE pattern; accident_type alone is stable.
    return str(seed["accident_type"])


def main() -> int:
    cases: list[dict] = []

    for index, seed in enumerate(ACCIDENT_CASE_SEEDS[:20], start=1):
        cases.append(
            {
                "case_id": f"RAG-AC-{index:03d}",
                "category": "accident_case",
                "tenant_id": seed["tenant_id"],
                "query": _accident_query(seed),
                "expected_record_ids": [seed["accident_case_id"]],
                "top_k": 3,
                "difficulty": "easy" if index <= 14 else "medium",
            }
        )

    knowledge_chunks = load_knowledge_chunks(KNOWLEDGE_DIR, tenant_id="CSCEC")
    for index, chunk in enumerate(knowledge_chunks[:10], start=1):
        cases.append(
            {
                "case_id": f"RAG-KN-{index:03d}",
                "category": "safety_knowledge",
                "tenant_id": chunk.tenant_id,
                "query": chunk.title,
                "expected_record_ids": [chunk.chunk_id],
                "top_k": 3,
                "difficulty": "easy",
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT_PATH), "cases": len(cases)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
