from __future__ import annotations

import contextlib
import json
import os
import signal
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _stub_chat_controller_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic and network-free.

    build_controller() defaults to a local Ollama controller when no
    OPENAI_API_KEY is set, which would otherwise make unrelated tests
    (mentor/contracts flows that call build_controller().chat(...)) attempt a
    real HTTP call. Tests that want to exercise a specific provider should
    override AIDF_CHAT_PROVIDER/OPENAI_API_KEY themselves.
    """
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _isolate_extensions(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Keep extension state from leaking between tests.

    Built-in extensions such as Words register a global prompt interceptor the first time the CLI
    parser is built. Without this reset, a later test asking the same question would be answered
    by the extension instead of the controller it is testing.
    """
    from agent_aidf.extensions.extension_loader import reset_active_registry

    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(tmp_path / "user-extensions"))
    monkeypatch.delenv("KOB_DISABLE_EXTENSIONS", raising=False)
    reset_active_registry()
    yield
    reset_active_registry()


def _is_running(pid: int) -> bool:
    """True for a live process. A zombie (exited, not yet reaped) does not count."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            state = handle.read().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


def stop_leftover_app_servers(root: Path) -> list[int]:
    """Kill every instant-app server whose runtime state file sits under root. Returns the pids."""
    from agent_aidf.instant_apps import RUNTIME_STATE_FILENAME

    killed: list[int] = []
    for state_file in root.rglob(RUNTIME_STATE_FILENAME):
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = data.get("pid") if isinstance(data, dict) else None
        if not isinstance(pid, int) or pid <= 0 or not _is_running(pid):
            continue
        # Instant apps start in their own session, so the pid is also the process group id.
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        killed.append(pid)
    return killed


@pytest.fixture(autouse=True)
def _no_instant_app_server_survives(tmp_path: Path):
    """Safety net for every test: whatever a test started, its server is gone when the test ends,
    even when an assertion failed before the test could stop it."""
    yield
    stop_leftover_app_servers(tmp_path)
