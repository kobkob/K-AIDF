from __future__ import annotations

import json
from pathlib import Path

import agent_aidf.controller as controller_module
from agent_aidf.controller import (
    OllamaChatController,
    OpenAIResponsesController,
    build_controller,
    select_context_documents,
)
from agent_aidf.instant_apps import create_instant_app
from agent_aidf.repo import load_documents


def test_build_controller_uses_stub_when_provider_is_none(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    controller = build_controller()

    assert controller.chat("hello").startswith("AI chat controller is not configured yet.")


def test_build_controller_defaults_to_local_ollama_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AIDF_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    controller = build_controller()

    assert isinstance(controller, OllamaChatController)
    assert controller.model == "olmo2:7b-1124-instruct-q4_K_M"
    assert controller.base_url == "http://localhost:11434"


def test_build_controller_ignores_ambient_api_key_without_explicit_provider(monkeypatch) -> None:
    # A stray OPENAI_API_KEY in the environment must not silently switch the
    # default away from local — only AIDF_CHAT_PROVIDER=openai does that.
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient-leftover-key")

    controller = build_controller()

    assert isinstance(controller, OllamaChatController)


def test_build_controller_uses_openai_when_explicitly_selected(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")

    controller = build_controller()

    assert isinstance(controller, OpenAIResponsesController)
    assert controller.model == "gpt-5"


def test_ollama_controller_reports_connection_failure_without_raising() -> None:
    controller = OllamaChatController(base_url="http://127.0.0.1:1")

    reply = controller.chat("hello")

    assert "Could not reach local Ollama" in reply


def test_ollama_controller_reports_timeout_without_raising(tmp_path: Path, monkeypatch) -> None:
    # Regression test: response.read() can time out on its own, separately from
    # URLError, when the connection succeeds but the model is slow to finish
    # generating. Left uncaught, this crashed the whole TUI/shell process.
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(controller_module.request, "urlopen", _raise_timeout)
    controller = OllamaChatController()

    reply = controller.chat("hello", tmp_path)

    assert "did not respond within" in reply


def test_openai_controller_reports_timeout_without_raising(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(controller_module.request, "urlopen", _raise_timeout)
    controller = OpenAIResponsesController(api_key="test-key")

    reply = controller.chat("hello", tmp_path)

    assert "timed out" in reply


def test_openai_controller_builds_payload_with_repo_context(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    doc = repo / "docs/20-ethical-model/principles/transparency.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "---\n"
        "id: docs/20-ethical-model/principles/transparency.md\n"
        "title: Transparency\n"
        "document_class: core-doc\n"
        "phase: 20-ethical-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: ethical-model\n"
        "ethical_domain: transparency\n"
        "---\n\n"
        "# Transparency\n\n"
        "Explainable use.\n",
        encoding="utf-8",
    )
    create_instant_app(repo, app_id="mentor-web", mode="persistent", kind="web")

    controller = OpenAIResponsesController(api_key="test-key")
    payload = controller._build_payload("tell me about transparency", Path(repo))

    assert payload["model"] == "gpt-5"
    assert isinstance(payload["input"], list)
    user_message = payload["input"][1]
    assert "Detected packs: ethical-model" in user_message["content"]
    assert "Persistent instant apps: mentor-web" in user_message["content"]
    assert "Mentor step count: 0" in user_message["content"]
    assert "Mentor current app: none" in user_message["content"]
    assert "Mentor current app URL: none" in user_message["content"]
    assert "docs/20-ethical-model/principles/transparency.md" in user_message["content"]


def test_openai_controller_extracts_output_text() -> None:
    data = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "First line."},
                    {"type": "output_text", "text": "Second line."},
                ],
            }
        ]
    }

    assert OpenAIResponsesController._extract_output_text(data) == "First line.\nSecond line."


def test_select_context_documents_prefers_ethical_domain_documents(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    ethical = repo / "docs/20-ethical-model/principles/transparency.md"
    ethical.parent.mkdir(parents=True, exist_ok=True)
    ethical.write_text(
        "---\n"
        "id: docs/20-ethical-model/principles/transparency.md\n"
        "title: Transparency\n"
        "document_class: core-doc\n"
        "phase: 20-ethical-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: ethical-model\n"
        "ethical_domain: transparency\n"
        "---\n\n"
        "# Transparency\n\n"
        "Explainable use.\n",
        encoding="utf-8",
    )
    maturity = repo / "docs/10-maturity-model/levels/04-managed.md"
    maturity.parent.mkdir(parents=True, exist_ok=True)
    maturity.write_text(
        "---\n"
        "id: docs/10-maturity-model/levels/04-managed.md\n"
        "title: Managed\n"
        "document_class: core-doc\n"
        "phase: 10-maturity-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: maturity-model\n"
        "maturity_level: managed\n"
        "---\n\n"
        "# Managed\n",
        encoding="utf-8",
    )

    selected = select_context_documents(load_documents(repo), "how should we handle transparency?", limit=3)

    assert selected
    assert selected[0].path == "docs/20-ethical-model/principles/transparency.md"


def test_select_context_documents_prefers_maturity_checklist_for_checklist_prompt(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    checklist = repo / "docs/10-maturity-model/assessment/checklist.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    checklist.write_text(
        "---\n"
        "id: docs/10-maturity-model/assessment/checklist.md\n"
        "title: Maturity Assessment Checklist\n"
        "document_class: core-doc\n"
        "phase: 10-maturity-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: maturity-model\n"
        "assessment_type: checklist\n"
        "---\n\n"
        "# Maturity Assessment Checklist\n\n"
        "Checklist for evidence and review controls.\n",
        encoding="utf-8",
    )
    readme = repo / "docs/10-maturity-model/README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        "---\n"
        "id: docs/10-maturity-model/README.md\n"
        "title: Maturity Model Pack\n"
        "document_class: core-doc\n"
        "phase: 10-maturity-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: maturity-model\n"
        "---\n\n"
        "# Maturity Model Pack\n",
        encoding="utf-8",
    )

    selected = select_context_documents(load_documents(repo), "show the maturity checklist", limit=3)

    assert selected
    assert selected[0].path == "docs/10-maturity-model/assessment/checklist.md"


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def test_ollama_controller_sends_kob_identity_and_captures_usage(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps({"response": "hi", "eval_count": 5, "prompt_eval_count": 10}).encode("utf-8")
        )

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController(model="test-model")

    reply = controller.chat("hello", tmp_path)

    assert reply == "hi"
    prompt_sent = captured["body"]["prompt"]
    assert "You are kob, version" in prompt_sent
    assert "running the test-model model" in prompt_sent
    assert "Kobkob LLC" in prompt_sent
    assert controller.last_usage == {"prompt_tokens": 10, "completion_tokens": 5}


def test_openai_controller_sends_kob_identity_and_captures_usage(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps(
                {
                    "id": "resp_1",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
                    "usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OpenAIResponsesController(api_key="test-key", model="gpt-5")

    reply = controller.chat("hello", tmp_path)

    assert reply == "hi"
    developer_message = captured["body"]["input"][0]["content"]
    assert "You are kob, version" in developer_message
    assert "running the gpt-5 model" in developer_message
    assert controller.last_usage == {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}


def test_manifesto_excerpt_is_full_body_not_a_teaser(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    manifesto = repo / "docs/00-overview/manifesto.md"
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    long_body = "\n".join(f"KAIDF principle line {i}." for i in range(50))
    manifesto.write_text(
        "---\n"
        "id: docs/00-overview/manifesto.md\n"
        "title: KAIDF Manifesto\n"
        "document_class: core-doc\n"
        "phase: 00-overview\n"
        "visibility: internal\n"
        "status: active\n"
        "---\n\n"
        f"# KAIDF Manifesto\n\n{long_body}\n",
        encoding="utf-8",
    )

    context = controller_module._build_context_prompt(repo, "what is kaidf?")

    assert "docs/00-overview/manifesto.md" in context
    assert "KAIDF principle line 49." in context


def test_resolve_timeout_seconds_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_TIMEOUT_SECONDS", raising=False)

    assert controller_module._resolve_timeout_seconds() == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS


def test_resolve_timeout_seconds_honors_valid_override(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "600")

    assert controller_module._resolve_timeout_seconds() == 600


def test_resolve_timeout_seconds_falls_back_on_garbage_value(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "not-a-number")

    assert controller_module._resolve_timeout_seconds() == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS

    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "-5")

    assert controller_module._resolve_timeout_seconds() == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS
