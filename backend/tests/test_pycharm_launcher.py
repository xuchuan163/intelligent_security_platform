import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pycharm_start", ROOT / "scripts" / "pycharm_start.py")
assert SPEC is not None
assert SPEC.loader is not None
pycharm_start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pycharm_start)


def test_default_backend_port_is_8011() -> None:
    parser = pycharm_start.build_arg_parser()
    args = parser.parse_args([])

    assert args.backend_port == 8011


def test_alembic_command_uses_console_entrypoint_when_available(tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    alembic = tmp_path / ".venv" / "Scripts" / "alembic.exe"
    alembic.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    alembic.write_text("", encoding="utf-8")

    command = pycharm_start.alembic_upgrade_command(python)

    assert command == [str(alembic), "upgrade", "head"]


def test_alembic_command_falls_back_to_module_invocation(tmp_path: Path) -> None:
    python = tmp_path / "conda" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")

    command = pycharm_start.alembic_upgrade_command(python)

    assert command == [str(python), "-m", "alembic", "upgrade", "head"]


def test_resolve_python_interpreter_prefers_current_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    current = tmp_path / "conda" / "python.exe"
    current.parent.mkdir(parents=True)
    current.write_text("", encoding="utf-8")

    monkeypatch.setattr(pycharm_start, "VENV_PYTHON", venv_python)
    monkeypatch.setattr(pycharm_start.sys, "executable", str(current))

    assert pycharm_start.resolve_python_interpreter() == current.resolve()


def test_resolve_python_interpreter_honors_project_python_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chosen = tmp_path / "custom" / "python.exe"
    chosen.parent.mkdir(parents=True)
    chosen.write_text("", encoding="utf-8")
    monkeypatch.setenv("PROJECT_PYTHON", str(chosen))

    assert pycharm_start.resolve_python_interpreter() == chosen.resolve()


def test_ensure_backend_dependencies_raises_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")

    def fake_run(command: list[str], cwd: Path, capture_output: bool, text: bool) -> subprocess.CompletedProcess[str]:
        assert command[0] == str(python)
        return subprocess.CompletedProcess(command, 1, "", "No module named 'jwt'")

    monkeypatch.setattr(pycharm_start.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match='pip install -e'):
        pycharm_start.ensure_backend_dependencies(python)


def test_npm_command_prefers_explicit_env_path(tmp_path: Path) -> None:
    npm = tmp_path / "npm.cmd"
    npm.write_text("", encoding="utf-8")

    command = pycharm_start.npm_command({"NPM_CMD": str(npm), "PATH": ""})

    assert command == [str(npm), "run", "dev", "--"]


def test_npm_command_uses_path_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    npm = tmp_path / "npm.cmd"
    npm.write_text("", encoding="utf-8")
    monkeypatch.setattr(pycharm_start.shutil, "which", lambda name, path=None: str(npm) if name == "npm.cmd" else None)

    command = pycharm_start.npm_command({"PATH": str(tmp_path)})

    assert command == [str(npm), "run", "dev", "--"]


def test_npm_command_raises_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pycharm_start.shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(pycharm_start, "common_npm_candidates", lambda env: [])

    with pytest.raises(FileNotFoundError, match="npm executable not found"):
        pycharm_start.npm_command({"PATH": ""})


def test_frontend_dev_command_prefers_local_vite_with_node_cmd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    vite_js = frontend / "node_modules" / "vite" / "bin" / "vite.js"
    vite_js.parent.mkdir(parents=True)
    vite_js.write_text("", encoding="utf-8")
    node = tmp_path / "node.exe"
    node.write_text("", encoding="utf-8")
    monkeypatch.setattr(pycharm_start, "FRONTEND", frontend)

    command = pycharm_start.frontend_dev_command({"NODE_CMD": str(node), "PATH": ""}, 5174)

    assert command == [str(node), str(vite_js), "--host", "127.0.0.1", "--port", "5174"]


def test_node_command_raises_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pycharm_start.shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(pycharm_start, "common_node_candidates", lambda env: [])

    with pytest.raises(FileNotFoundError, match="node executable not found"):
        pycharm_start.node_command({"PATH": ""})


def test_ensure_ports_available_raises_when_port_is_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pycharm_start, "port_is_listening", lambda port: port == 8000)

    with pytest.raises(RuntimeError, match="Port 8000 is already in use"):
        pycharm_start.ensure_ports_available([8000, 5173], kill_ports=False)


def test_ensure_ports_available_can_kill_busy_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    killed: list[int] = []
    state = {"busy": True}

    def fake_listening(port: int) -> bool:
        return port == 8000 and state["busy"]

    def fake_kill(port: int) -> None:
        killed.append(port)
        if killed.count(8000) >= 2:
            state["busy"] = False

    monkeypatch.setattr(pycharm_start, "port_is_listening", fake_listening)
    monkeypatch.setattr(pycharm_start, "kill_port", fake_kill)
    monkeypatch.setattr(pycharm_start, "describe_port_blockers", lambda port: f"port {port}: pid(s) 1234")

    pycharm_start.ensure_ports_available([8000, 5173], kill_ports=True)

    assert killed.count(8000) >= 2


def test_default_kill_ports_enabled() -> None:
    parser = pycharm_start.build_arg_parser()
    args = parser.parse_args([])

    assert args.kill_ports is True


def test_no_kill_ports_flag_disables_cleanup() -> None:
    parser = pycharm_start.build_arg_parser()
    args = parser.parse_args(["--no-kill-ports"])

    assert args.kill_ports is False


def test_pids_from_net_tcp_connection_parses_powershell_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "25428\n18672\n", "")

    monkeypatch.setattr(pycharm_start.subprocess, "run", fake_run)

    assert pycharm_start._pids_from_net_tcp_connection(8011) == [18672, 25428]


def test_pids_from_netstat_parses_windows_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], capture_output: bool, text: bool, encoding: str, errors: str, check: bool) -> subprocess.CompletedProcess[str]:
        stdout = "  TCP    127.0.0.1:8011         0.0.0.0:0              LISTENING       25428\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(pycharm_start, "_pids_from_net_tcp_connection", lambda port: [])
    monkeypatch.setattr(pycharm_start.subprocess, "run", fake_run)

    assert pycharm_start.pids_holding_port(8011) == [25428]
