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
