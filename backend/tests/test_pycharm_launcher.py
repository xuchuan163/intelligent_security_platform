import importlib.util
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


def test_alembic_command_requires_console_entrypoint(tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Alembic executable not found"):
        pycharm_start.alembic_upgrade_command(python)


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
    monkeypatch.setattr(pycharm_start, "port_is_listening", lambda port: port == 8000 and not killed)
    monkeypatch.setattr(pycharm_start, "kill_port", lambda port: killed.append(port))

    pycharm_start.ensure_ports_available([8000, 5173], kill_ports=True)

    assert killed == [8000]
