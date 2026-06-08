"""One-click Phase 3 four-library health check: MySQL, Redis, Milvus, Neo4j."""

from __future__ import annotations

import argparse
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.infrastructure.database.session import engine  # noqa: E402
from app.infrastructure.milvus_client import probe_milvus_status  # noqa: E402
from app.infrastructure.neo4j_client import probe_neo4j_status  # noqa: E402
from app.infrastructure.redis_client import probe_redis_status  # noqa: E402


def _tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def _mysql_ready() -> tuple[bool, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, settings.database_url.split("@")[-1]
    except Exception as exc:
        return False, str(exc)


def _neo4j_tcp_ready(host: str, port: int) -> bool:
    return _tcp_open(host, port)


def check_four_libraries(
    *,
    milvus_health_url: str = "http://127.0.0.1:19091/healthz",
    milvus_grpc_port: int = 29530,
    neo4j_host: str = "127.0.0.1",
    neo4j_port: int = 7687,
    require_neo4j: bool = False,
) -> dict[str, dict[str, object]]:
    mysql_ok, mysql_detail = _mysql_ready()
    redis_probe = probe_redis_status()
    milvus_probe = probe_milvus_status()
    neo4j_probe = probe_neo4j_status()
    neo4j_tcp = _neo4j_tcp_ready(neo4j_host, neo4j_port)

    milvus_stack_ok = _http_ok(milvus_health_url) and _tcp_open("127.0.0.1", milvus_grpc_port)
    milvus_ready = milvus_probe.status == "ready" or (
        milvus_probe.status == "disabled" and milvus_stack_ok
    )

    neo4j_ready = neo4j_probe.status == "ready" or (
        not settings.neo4j_enabled and neo4j_tcp
    )
    if require_neo4j:
        neo4j_ready = neo4j_probe.status == "ready"

    return {
        "mysql": {"ok": mysql_ok, "detail": mysql_detail},
        "redis": {"ok": redis_probe.status == "ready", "probe": redis_probe.as_dict()},
        "milvus": {
            "ok": milvus_ready,
            "probe": milvus_probe.as_dict(),
            "stack_health": milvus_stack_ok,
        },
        "neo4j": {
            "ok": neo4j_ready,
            "probe": neo4j_probe.as_dict(),
            "bolt_tcp": neo4j_tcp,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 four-library health check.")
    parser.add_argument("--milvus-health-url", default="http://127.0.0.1:19091/healthz")
    parser.add_argument("--milvus-grpc-port", type=int, default=29530)
    parser.add_argument("--neo4j-host", default="127.0.0.1")
    parser.add_argument("--neo4j-port", type=int, default=7687)
    parser.add_argument(
        "--require-neo4j",
        action="store_true",
        help="Fail if NEO4J_ENABLED=true but driver probe is not ready.",
    )
    args = parser.parse_args(argv)

    results = check_four_libraries(
        milvus_health_url=args.milvus_health_url,
        milvus_grpc_port=args.milvus_grpc_port,
        neo4j_host=args.neo4j_host,
        neo4j_port=args.neo4j_port,
        require_neo4j=args.require_neo4j,
    )

    all_ok = True
    for name, payload in results.items():
        ok = bool(payload["ok"])
        all_ok = all_ok and ok
        status = "ok" if ok else "FAIL"
        print(f"{name}: {status} ({payload})")

    if all_ok:
        print("four_libraries: ok")
        return 0

    print("four_libraries: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
