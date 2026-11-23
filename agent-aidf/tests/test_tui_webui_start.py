from __future__ import annotations

import importlib
import socket
from pathlib import Path

import pytest

import agent_aidf.webui as webui_module

cli_main = importlib.import_module("agent_aidf.cli.main")


class _FakeTui:
    """Just enough of KobAgentApp for _start_webui and _run_webui_worker to run unbound."""

    _log_from_thread = cli_main.KobAgentApp._log_from_thread
    _set_web_server = cli_main.KobAgentApp._set_web_server
    _run_webui_worker = cli_main.KobAgentApp._run_webui_worker

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.repo_root = project_root
        self._web_server = None
        self._web_url = None
        self.workers: list[dict] = []
        self.logged: list[str] = []

    def run_worker(self, work, **options) -> None:
        self.workers.append(options)

    def call_from_thread(self, callback, *args):
        return callback(*args)

    def _log(self, text: str) -> None:
        self.logged.append(text)

    def _refresh_status_panels(self) -> None:
        return None


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("KOB_YOLO", raising=False)
    monkeypatch.delenv("AIDF_UI_PORT", raising=False)


def _busy_port():
    """Hold a listening socket on a free loopback port for the duration of a test."""
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    return holder, holder.getsockname()[1]


def test_busy_port_is_reported_and_the_web_ui_is_not_started(
    tmp_path: Path, monkeypatch, clean_env
) -> None:
    holder, port = _busy_port()
    try:
        monkeypatch.setenv("AIDF_UI_PORT", str(port))
        tui = _FakeTui(tmp_path)

        message = cli_main.KobAgentApp._start_webui(tui)

        assert f"Port {port} is already in use" in message
        assert tui.workers == []
        assert tui._web_url is None
    finally:
        holder.close()


def test_missing_assets_are_reported_before_anything_starts(
    tmp_path: Path, monkeypatch, clean_env
) -> None:
    monkeypatch.setattr(webui_module, "STATIC_DIR", tmp_path / "no-such-dist")
    tui = _FakeTui(tmp_path)

    message = cli_main.KobAgentApp._start_webui(tui)

    assert "assets are missing" in message
    assert "npm run build" in message
    assert tui.workers == []


def test_free_port_still_starts_the_web_ui(tmp_path: Path, monkeypatch, clean_env) -> None:
    holder, port = _busy_port()
    holder.close()  # now free again
    monkeypatch.setenv("AIDF_UI_PORT", str(port))
    tui = _FakeTui(tmp_path)

    message = cli_main.KobAgentApp._start_webui(tui)

    assert message.startswith("Starting the web UI")
    assert tui._web_url == f"http://127.0.0.1:{port}"
    (options,) = tui.workers
    assert options["exit_on_error"] is False


@pytest.mark.parametrize(
    "failure",
    [OSError(98, "Address already in use"), RuntimeError("assets vanished")],
)
def test_worker_reports_startup_failures_without_raising(
    tmp_path: Path, monkeypatch, clean_env, failure: Exception
) -> None:
    def _fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(cli_main, "run_webui", _fail)
    tui = _FakeTui(tmp_path)

    cli_main.KobAgentApp._run_webui_worker(tui, 8501)

    assert len(tui.logged) == 1
    assert "could not start on port 8501" in tui.logged[0]
    assert str(failure) in tui.logged[0]
    assert tui._web_url is None
