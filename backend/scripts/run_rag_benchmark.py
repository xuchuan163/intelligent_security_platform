"""Run RAG retrieval benchmark against rag_retrieval_30.jsonl."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.infrastructure.database.session import Base
from app.services.cases.seed_cases import seed_accident_cases
from app.services.rag.benchmark import (
    DEFAULT_DATASET_PATH,
    DEFAULT_KNOWLEDGE_DIR,
    load_rag_retrieval_cases,
    run_rag_retrieval_benchmark,
)


def main() -> int:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        seed_accident_cases(db)
        cases = load_rag_retrieval_cases(DEFAULT_DATASET_PATH)
        report = run_rag_retrieval_benchmark(
            db,
            cases,
            milvus_client=None,
            knowledge_dir=DEFAULT_KNOWLEDGE_DIR,
        )
        print(json.dumps(
            {
                "total": report["total"],
                "passed": report["passed"],
                "failed": report["failed"],
                "top_k_hit_rate": report["top_k_hit_rate"],
                "category_breakdown": report["category_breakdown"],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if report["top_k_hit_rate"] >= 0.8 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
