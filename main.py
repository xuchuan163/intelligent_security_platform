"""PyCharm-friendly launcher for the CSCEC smart safety MVP.

Run this file from PyCharm to prepare the database and start both services:

- FastAPI backend: http://127.0.0.1:8000/docs
- Vue frontend:   http://127.0.0.1:5173

The launcher prefers Docker MySQL on port 3307 and falls back to a local
MySQL instance on port 3306. It does not store secrets in source code beyond
the local demo password already used by the development environment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_ALEMBIC = VENV_DIR / "Scripts" / "alembic.exe"

MYSQL_PASSWORD = os.getenv("MYSQL_ROOT_PASSWORD", "275874")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "cscec_safety")
RESET_DATABASE_ON_START = os.getenv("RESET_DATABASE_ON_START", "1").lower() not in {"0", "false", "no"}
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))


def run(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None, label: str | None = None) -> None:
    printable = label or " ".join(command)
    print(f"\n$ {printable}")
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def run_capture(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def ensure_venv() -> None:
    if VENV_PYTHON.exists():
        return
    print("Creating local Python 3.12 virtual environment...")
    run(["py", "-3.12", "-m", "venv", str(VENV_DIR)])


def ensure_backend_dependencies() -> None:
    probe = run_capture([str(VENV_PYTHON), "-c", "import fastapi, pymysql, alembic"])
    if probe.returncode == 0:
        return
    print("Installing backend dependencies into .venv...")
    run([str(VENV_PYTHON), "-m", "pip", "install", "-e", f"{BACKEND_DIR}[dev]"])


def ensure_frontend_dependencies() -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    print("Installing frontend dependencies...")
    run([npm_executable(), "install"], cwd=FRONTEND_DIR)


def npm_executable() -> str:
    executable = shutil.which("npm.cmd") or shutil.which("npm")
    if executable is None:
        raise RuntimeError("npm is not available. Install Node.js/npm, then rerun main.py.")
    return executable


def test_mysql_port(port: int) -> bool:
    script = f"""
import pymysql
try:
    conn = pymysql.connect(
        host="127.0.0.1",
        port={port},
        user="root",
        password="{MYSQL_PASSWORD}",
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=3,
    )
    with conn.cursor() as cursor:
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn.close()
except Exception as exc:
    print(exc)
    raise SystemExit(1)
"""
    result = run_capture([str(VENV_PYTHON), "-c", script])
    return result.returncode == 0


def choose_database_url() -> str:
    for port in (3307, 3306):
        if test_mysql_port(port):
            return f"mysql+pymysql://root:{MYSQL_PASSWORD}@127.0.0.1:{port}/{MYSQL_DATABASE}"
    raise RuntimeError(
        "No MySQL instance is reachable on 3307 or 3306. "
        "Start Docker Desktop/MySQL or local MySQL, then rerun main.py."
    )


def backend_env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return env


def mask_url_password(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if not parsed.password:
        return database_url
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def reset_demo_database(database_url: str) -> None:
    if not RESET_DATABASE_ON_START:
        return

    parsed = urlsplit(database_url)
    env = os.environ.copy()
    env["MYSQL_PORT"] = str(parsed.port or 3306)
    env["MYSQL_DATABASE"] = MYSQL_DATABASE
    env["MYSQL_ROOT_PASSWORD"] = MYSQL_PASSWORD

    script = r"""
import os
import re
import pymysql

database = os.environ["MYSQL_DATABASE"]
if not re.fullmatch(r"[A-Za-z0-9_]+", database):
    raise SystemExit(f"Unsafe database name: {database}")

connection = pymysql.connect(
    host="127.0.0.1",
    port=int(os.environ["MYSQL_PORT"]),
    user="root",
    password=os.environ["MYSQL_ROOT_PASSWORD"],
    charset="utf8mb4",
    autocommit=True,
)
with connection.cursor() as cursor:
    cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
    cursor.execute(
        f"CREATE DATABASE `{database}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
connection.close()
"""
    run([str(VENV_PYTHON), "-c", script], env=env, label=f"reset demo database {MYSQL_DATABASE}")


def migrate_and_seed(database_url: str) -> None:
    env = backend_env(database_url)
    run([str(VENV_ALEMBIC), "upgrade", "head"], cwd=BACKEND_DIR, env=env)
    run([str(VENV_PYTHON), "scripts/seed_demo_data.py"], cwd=BACKEND_DIR, env=env)


def stop_port(port: int) -> None:
    if os.name != "nt":
        return
    command = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
        "| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], check=False)


def start_services(database_url: str) -> list[subprocess.Popen[bytes]]:
    for port in (BACKEND_PORT, FRONTEND_PORT):
        stop_port(port)

    env = backend_env(database_url)
    backend = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=str(BACKEND_DIR),
        env=env,
    )
    frontend = subprocess.Popen(
        [npm_executable(), "run", "dev", "--", "--port", str(FRONTEND_PORT)],
        cwd=str(FRONTEND_DIR),
    )
    return [backend, frontend]


def main() -> int:
    print("Starting CSCEC smart safety MVP...")
    ensure_venv()
    ensure_backend_dependencies()
    ensure_frontend_dependencies()
    database_url = choose_database_url()
    print(f"Using database: {mask_url_password(database_url)}")
    reset_demo_database(database_url)
    migrate_and_seed(database_url)
    processes = start_services(database_url)

    print("\nProject is running:")
    print(f"- Backend Swagger: http://127.0.0.1:{BACKEND_PORT}/docs")
    print(f"- Frontend:        http://127.0.0.1:{FRONTEND_PORT}")
    print("\nKeep this PyCharm run window open. Press Ctrl+C to stop both services.")

    try:
        while all(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        for process in processes:
            process.terminate()
        return 0

    for process in processes:
        if process.poll() not in (None, 0):
            return process.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
