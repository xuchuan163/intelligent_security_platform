"""Full manual sync from MySQL demo data into Neo4j."""

from __future__ import annotations

import sys

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.neo4j_client import build_neo4j_client
from app.services.graph.sync import sync_graph_from_mysql


def main() -> int:
    client = build_neo4j_client()
    db = SessionLocal()
    try:
        counts = sync_graph_from_mysql(db, client)
        print("Neo4j graph sync completed:", counts)
        return 0
    finally:
        db.close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
