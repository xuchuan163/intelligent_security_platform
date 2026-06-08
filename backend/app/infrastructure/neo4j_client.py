from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings

Neo4jStatus = Literal["disabled", "unavailable", "ready"]


@dataclass(frozen=True)
class Neo4jProbeResult:
    status: Neo4jStatus
    uri: str
    enabled: bool
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "uri": self.uri,
            "enabled": self.enabled,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


class Neo4jClient:
    def __init__(self, driver: Any, *, database: str) -> None:
        self._driver = driver
        self.database = database

    def ping(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def close(self) -> None:
        self._driver.close()


def build_neo4j_client() -> Neo4jClient:
    if not settings.neo4j_enabled:
        raise RuntimeError("Neo4j is disabled by configuration")
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("neo4j package is not installed") from exc

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    client = Neo4jClient(driver, database=settings.neo4j_database)
    if not client.ping():
        client.close()
        raise RuntimeError(f"Neo4j is unreachable at {settings.neo4j_uri}")
    return client


def build_neo4j_client_optional() -> Neo4jClient | None:
    if not settings.neo4j_enabled:
        return None
    try:
        return build_neo4j_client()
    except RuntimeError:
        return None


def probe_neo4j_status() -> Neo4jProbeResult:
    if not settings.neo4j_enabled:
        return Neo4jProbeResult(
            status="disabled",
            uri=settings.neo4j_uri,
            enabled=False,
            detail="NEO4J_ENABLED=false",
        )

    client = build_neo4j_client_optional()
    if client is None:
        return Neo4jProbeResult(
            status="unavailable",
            uri=settings.neo4j_uri,
            enabled=True,
            detail="connection_failed",
        )

    try:
        return Neo4jProbeResult(
            status="ready",
            uri=settings.neo4j_uri,
            enabled=True,
        )
    finally:
        client.close()
