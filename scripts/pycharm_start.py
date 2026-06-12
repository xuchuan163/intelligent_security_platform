from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DEFAULT_DB_NAME = "intelligent_security_platform"
DEFAULT_MYSQL_PASSWORD = "275874"


def main() -> int:
    args = build_arg_parser().parse_args()
    register_stop_handlers()

    env = os.environ.copy()
    env.update(load_dotenv(ROOT / ".env"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("UPLOAD_DIR", str(ROOT / ".uploads"))
    env["DATABASE_URL"] = env.get("DATABASE_URL") or detect_database_url(env)
    env["VITE_API_TARGET"] = f"http://127.0.0.1:{args.backend_port}"

    python = resolve_python_interpreter()
    ensure_file(FRONTEND / "package.json", "frontend package.json")

    print_header(env, args.backend_port, args.frontend_port, python)
    ensure_python_version(python)
    ensure_backend_dependencies(python)
    ensure_ports_available([args.backend_port, args.frontend_port], kill_ports=args.kill_ports)

    if not args.skip_migrate:
        run_checked(alembic_upgrade_command(python), cwd=BACKEND, env=env)
    if not args.skip_seed:
        run_checked([str(python), "scripts/seed_demo_data.py"], cwd=BACKEND, env=env)

    frontend_command = frontend_dev_command(env, args.frontend_port)
    processes: list[subprocess.Popen[str]] = []
    try:
        processes.append(
            spawn_labeled_process(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--reload",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.backend_port),
                ],
                cwd=BACKEND,
                env=env,
                label="backend",
            )
        )
        processes.append(
            spawn_labeled_process(
                frontend_command,
                cwd=FRONTEND,
                env=env,
                label="frontend",
            )
        )

        wait_for_port(args.backend_port, "backend", processes[0])
        wait_for_port(args.frontend_port, "frontend", processes[1])
        print("")
        print(f"Backend docs: http://127.0.0.1:{args.backend_port}/docs")
        print(f"Frontend:     http://127.0.0.1:{args.frontend_port}/work-orders")
        print("Press Ctrl+C in PyCharm to stop both services.")

        while all(process.poll() is None for process in processes):
            time.sleep(1)
        return first_exit_code(processes)
    except KeyboardInterrupt:
        print("")
        print("Stopping services...")
        return 0
    finally:
        stop_processes(processes, [args.backend_port, args.frontend_port])


def register_stop_handlers() -> None:
    def handle_stop(_signum: int, _frame: object | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the CSCEC smart safety platform for PyCharm.")
    parser.add_argument("--backend-port", type=int, default=8011)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--skip-migrate", action="store_true")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--kill-ports", action=argparse.BooleanOptionalAction, default=True, help="Stop existing processes on backend/frontend ports before startup.")
    return parser


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def detect_database_url(env: dict[str, str]) -> str:
    password = env.get("MYSQL_ROOT_PASSWORD") or DEFAULT_MYSQL_PASSWORD
    db_name = env.get("PYCHARM_DB_NAME") or DEFAULT_DB_NAME
    for port in (3307, 3306):
        if mysql_is_reachable(port, password, db_name):
            return f"mysql+pymysql://root:{password}@127.0.0.1:{port}/{db_name}"
    raise RuntimeError(
        "No MySQL instance is reachable on 127.0.0.1:3307 or 127.0.0.1:3306. "
        "Start Docker Desktop/local MySQL first, or set DATABASE_URL in .env."
    )


def mysql_is_reachable(port: int, password: str, db_name: str) -> bool:
    try:
        import pymysql

        conn = pymysql.connect(
            host="127.0.0.1",
            port=port,
            user="root",
            password=password,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=3,
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.close()
        return True
    except Exception:
        return False


def resolve_python_interpreter() -> Path:
    explicit = os.environ.get("PROJECT_PYTHON")
    if explicit:
        path = Path(explicit).resolve()
        ensure_file(path, "PROJECT_PYTHON interpreter")
        return path

    current = Path(sys.executable).resolve()
    ensure_file(current, "Python interpreter")
    return current


def ensure_python_version(python: Path) -> None:
    result = subprocess.run(
        [str(python), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    raise RuntimeError(
        f"{python} is Python 3.10 or older. Backend requires Python 3.11+. "
        f"In PyCharm set Interpreter to {ROOT / '.venv' / 'Scripts' / 'python.exe'} "
        "or upgrade your conda env to Python 3.11+."
    )


def ensure_backend_dependencies(python: Path) -> None:
    result = subprocess.run(
        [str(python), "-c", "import jwt"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    raise RuntimeError(
        f"Backend dependencies are missing in {python}. "
        f'Install them once with: "{python}" -m pip install -e "{BACKEND}[dev]"'
    )


def ensure_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def alembic_upgrade_command(python: Path) -> list[str]:
    alembic_exe = python.parent / ("alembic.exe" if os.name == "nt" else "alembic")
    if alembic_exe.exists():
        return [str(alembic_exe), "upgrade", "head"]
    return [str(python), "-m", "alembic", "upgrade", "head"]


def npm_command(env: dict[str, str]) -> list[str]:
    explicit = env.get("NPM_CMD")
    if explicit:
        npm_path = Path(explicit)
        if npm_path.exists():
            return [str(npm_path), "run", "dev", "--"]
        raise FileNotFoundError(f"NPM_CMD points to a missing file: {npm_path}")

    names = ["npm.cmd", "npm"] if os.name == "nt" else ["npm"]
    for name in names:
        found = shutil.which(name, path=env.get("PATH"))
        if found:
            return [found, "run", "dev", "--"]

    for candidate in common_npm_candidates(env):
        if candidate.exists():
            return [str(candidate), "run", "dev", "--"]

    raise FileNotFoundError(
        "npm executable not found. Install Node.js/npm, add it to PATH in PyCharm, "
        "or set NPM_CMD to the full npm.cmd path in the PyCharm Run Configuration."
    )


def frontend_dev_command(env: dict[str, str], frontend_port: int) -> list[str]:
    vite_js = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if vite_js.exists():
        return [node_command(env), str(vite_js), "--host", "127.0.0.1", "--port", str(frontend_port)]
    return npm_command(env) + ["--host", "127.0.0.1", "--port", str(frontend_port)]


def node_command(env: dict[str, str]) -> str:
    explicit = env.get("NODE_CMD")
    if explicit:
        node_path = Path(explicit)
        if node_path.exists():
            return str(node_path)
        raise FileNotFoundError(f"NODE_CMD points to a missing file: {node_path}")

    names = ["node.exe", "node"] if os.name == "nt" else ["node"]
    for name in names:
        found = shutil.which(name, path=env.get("PATH"))
        if found:
            return found

    for candidate in common_node_candidates(env):
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "node executable not found. Install Node.js, add it to PATH in PyCharm, "
        "or set NODE_CMD to the full node.exe path in the PyCharm Run Configuration."
    )


def common_node_candidates(env: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = env.get(key) or os.environ.get(key)
        if not value:
            continue
        root = Path(value)
        if key == "LOCALAPPDATA":
            candidates.append(root / "Programs" / "nodejs" / "node.exe")
        else:
            candidates.append(root / "nodejs" / "node.exe")

    # Some local coding tools bundle Node.js outside the standard install dirs.
    for drive in ("C", "D", "E"):
        candidates.extend(
            [
                Path(f"{drive}:\\软件安装\\nodejs\\node.exe"),
                Path(f"{drive}:\\软件安装\\claude code\\node.exe"),
            ]
        )
    return candidates


def common_npm_candidates(env: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = env.get(key) or os.environ.get(key)
        if not value:
            continue
        root = Path(value)
        if key == "LOCALAPPDATA":
            candidates.append(root / "Programs" / "nodejs" / "npm.cmd")
        else:
            candidates.append(root / "nodejs" / "npm.cmd")
    return candidates


def run_checked(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f"> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def spawn_labeled_process(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    label: str,
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
    )
    thread = threading.Thread(target=stream_process_output, args=(process, label), daemon=True)
    thread.start()
    return process


def stream_process_output(process: subprocess.Popen[str], label: str) -> None:
    assert process.stdout is not None
    prefix = f"[{label}] "
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    for line in process.stdout:
        safe_line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
        try:
            print(f"{prefix}{safe_line}", end="", flush=True)
        except UnicodeEncodeError:
            fallback = safe_line.encode("ascii", errors="replace").decode("ascii", errors="replace")
            print(f"{prefix}{fallback}", end="", flush=True)


def wait_for_port(
    port: int,
    label: str,
    process: subprocess.Popen[str] | None = None,
    timeout_seconds: int = 30,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        exit_code = process.poll() if process is not None else None
        if exit_code is not None:
            raise RuntimeError(
                f"{label} exited with code {exit_code} before listening on port {port}. "
                "Check the [backend] or [frontend] logs above."
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                print(f"{label} is listening on {port}")
                return
        time.sleep(1)
    raise TimeoutError(f"{label} did not listen on port {port} within {timeout_seconds}s")


def ensure_ports_available(ports: list[int], kill_ports: bool = False) -> None:
    busy_ports = [port for port in ports if port_is_listening(port)]
    if not busy_ports:
        return

    if not kill_ports:
        busy = ", ".join(str(port) for port in busy_ports)
        raise RuntimeError(
            f"Port {busy} is already in use. Stop the existing process, "
            "or run main.py with --kill-ports to let the launcher stop these listeners."
        )

    for port in busy_ports:
        kill_port(port)

    deadline = time.time() + 15
    while time.time() < deadline:
        busy_ports = [port for port in ports if port_is_listening(port)]
        if not busy_ports:
            return
        for port in busy_ports:
            kill_port(port)
        time.sleep(0.5)

    busy_ports = [port for port in ports if port_is_listening(port)]
    details = "; ".join(describe_port_blockers(port) for port in busy_ports)
    raise RuntimeError(
        f"Port {', '.join(str(port) for port in busy_ports)} is still in use after --kill-ports cleanup. "
        f"{details}"
    )


def describe_port_blockers(port: int) -> str:
    pids = pids_holding_port(port)
    if not pids:
        return f"port {port}: unknown blocker"
    return f"port {port}: pid(s) {', '.join(str(pid) for pid in pids)}"


def pids_holding_port(port: int) -> list[int]:
    if os.name != "nt":
        return []

    pids = _pids_from_net_tcp_connection(port)
    if pids:
        return pids
    return _pids_from_netstat(port)


def _pids_from_net_tcp_connection(port: int) -> list[int]:
    command = (
        f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue "
        "| Where-Object {{ $_.OwningProcess -gt 0 }} "
        "| Select-Object -ExpandProperty OwningProcess -Unique"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        token = line.strip()
        if token.isdigit():
            pids.append(int(token))
    return sorted(set(pids))


def _pids_from_netstat(port: int) -> list[int]:
    netstat = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "netstat.exe"
    if not netstat.exists():
        return []

    result = subprocess.run(
        [str(netstat), "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pids: list[int] = []
    needle = f":{port}"
    for line in (result.stdout or "").splitlines():
        if needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        pid_token = parts[-1]
        if pid_token.isdigit() and int(pid_token) > 0:
            pids.append(int(pid_token))
    return sorted(set(pids))


def port_is_listening(port: int) -> bool:
    checks = [(socket.AF_INET, "127.0.0.1")]
    if socket.has_ipv6:
        checks.append((socket.AF_INET6, "::1"))

    for family, host in checks:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                return True
    return False


def kill_port(port: int) -> None:
    if os.name != "nt":
        raise RuntimeError("--kill-ports is currently implemented for Windows only.")

    pids = pids_holding_port(port)
    if not pids:
        return

    print(f"Stopping processes on port {port}: {', '.join(str(pid) for pid in pids)}")
    for pid in pids:
        kill_process_tree(pid)


def print_header(env: dict[str, str], backend_port: int, frontend_port: int, python: Path) -> None:
    database_url = redact_database_url(env["DATABASE_URL"])
    print("CSCEC smart safety platform dev startup")
    print(f"Root:         {ROOT}")
    print(f"Python:       {python}")
    print(f"Database:     {database_url}")
    print(f"Backend port: {backend_port}")
    print(f"Frontend port:{frontend_port}")


def redact_database_url(database_url: str) -> str:
    if "@" not in database_url or ":" not in database_url.split("@", 1)[0]:
        return database_url
    before_at, after_at = database_url.split("@", 1)
    scheme_and_user = before_at.rsplit(":", 1)[0]
    return f"{scheme_and_user}:***@{after_at}"


def first_exit_code(processes: list[subprocess.Popen[str]]) -> int:
    for process in processes:
        code = process.poll()
        if code is not None:
            return code
    return 0


def stop_processes(processes: list[subprocess.Popen[str]], ports: list[int] | None = None) -> None:
    for process in processes:
        if process.poll() is None:
            kill_process_tree(process.pid)
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                kill_process_tree(process.pid)

    if os.name == "nt" and ports:
        for port in ports:
            kill_port(port)


def kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        if taskkill.exists():
            subprocess.run(
                [str(taskkill), "/F", "/T", "/PID", str(pid)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return

    try:
        os.killpg(os.getpgid(pid), 9)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, 9)
        except (ProcessLookupError, PermissionError, OSError):
            return


if __name__ == "__main__":
    raise SystemExit(main())
