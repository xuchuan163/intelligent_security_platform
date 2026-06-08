"""Seed Milvus RAG corpus from MySQL accident cases and config/knowledge markdown."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.infrastructure.database.session import SessionLocal  # noqa: E402
from app.infrastructure.milvus_client import build_milvus_client  # noqa: E402
from app.services.rag.ingest import ingest_rag_corpus  # noqa: E402

KNOWLEDGE_DIR = REPO_ROOT / "config" / "knowledge"


def main() -> int:
    if not settings.milvus_enabled:
        print("Milvus is disabled. Set MILVUS_ENABLED=true before seeding RAG corpus.")
        return 1
    if not KNOWLEDGE_DIR.exists():
        print(f"Knowledge directory not found: {KNOWLEDGE_DIR}")
        return 1

    client = build_milvus_client()
    db = SessionLocal()
    try:
        result = ingest_rag_corpus(db, client, knowledge_dir=KNOWLEDGE_DIR)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
