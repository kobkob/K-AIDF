from __future__ import annotations

from agent_aidf.cli.main import DEFAULT_LOCAL_MODEL, active_model_label


def test_active_model_label_defaults_to_friendly_local_name(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AIDF_MODEL", raising=False)

    assert active_model_label() == DEFAULT_LOCAL_MODEL == "OLMo 3.1 local"


def test_active_model_label_ignores_ambient_openai_key(monkeypatch) -> None:
    # Regression: an OPENAI_API_KEY left set in the shell must not make the
    # TUI header show "gpt-5" unless AIDF_CHAT_PROVIDER=openai was chosen.
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient-leftover-key")
    monkeypatch.delenv("AIDF_MODEL", raising=False)

    assert active_model_label() == "OLMo 3.1 local"


def test_active_model_label_reflects_configured_local_model(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AIDF_MODEL", "olmo2:13b-1124-instruct-q4_K_M")

    assert active_model_label() == "olmo2:13b-1124-instruct-q4_K_M"


def test_active_model_label_reflects_explicit_openai_provider(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")

    assert active_model_label() == "gpt-5"
