"""Create Milvus RAG collections (Task 3-C.3 / 3-C.4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.infrastructure.milvus_client import build_milvus_client  # noqa: E402
from app.services.rag.collections import ensure_rag_collections  # noqa: E402


def main() -> int:
    if not settings.milvus_enabled:
        print("Milvus is disabled. Set MILVUS_ENABLED=true and ensure deploy/docker-compose.yml is up.")
        return 1

    client = build_milvus_client()
    try:
        results = ensure_rag_collections(client)
        print(json.dumps([item.as_dict() for item in results], ensure_ascii=False, indent=2))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
