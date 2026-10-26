from __future__ import annotations

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
