#!/usr/bin/env python3
"""Verify local Docker stack health for MySQL, Redis, and Milvus (Task 3-C.1)."""

from __future__ import annotations

import argparse
import socket
import sys
import urllib.error
import urllib.request


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


def check_stack(
    *,
    mysql_host: str = "127.0.0.1",
    mysql_port: int = 3306,
    redis_host: str = "127.0.0.1",
    redis_port: int = 6379,
    milvus_health_url: str = "http://127.0.0.1:19091/healthz",
    milvus_grpc_port: int = 29530,
) -> dict[str, bool]:
    return {
        "mysql": _tcp_open(mysql_host, mysql_port),
        "redis": _tcp_open(redis_host, redis_port),
        "milvus_health": _http_ok(milvus_health_url),
        "milvus_grpc": _tcp_open("127.0.0.1", milvus_grpc_port),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check CSCEC safety platform local stack health.")
    parser.add_argument("--mysql-host", default="127.0.0.1")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--redis-host", default="127.0.0.1")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--milvus-health-url", default="http://127.0.0.1:19091/healthz")
    parser.add_argument("--milvus-grpc-port", type=int, default=29530)
    args = parser.parse_args(argv)

    results = check_stack(
        mysql_host=args.mysql_host,
        mysql_port=args.mysql_port,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        milvus_health_url=args.milvus_health_url,
        milvus_grpc_port=args.milvus_grpc_port,
    )

    for name, ok in results.items():
        status = "ok" if ok else "FAIL"
        print(f"{name}: {status}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
