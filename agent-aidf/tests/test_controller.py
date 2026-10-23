from __future__ import annotations

import io
import json
from pathlib import Path
from urllib import error

import pytest

import agent_aidf.controller as controller_module
from agent_aidf.controller import (
    MODEL_UNAVAILABLE_PREFIX,
    OllamaChatController,
    OpenAIResponsesController,
    build_controller,
    is_model_unavailable_reply,
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


@pytest.fixture(autouse=True)
def _record_backoff_sleeps(monkeypatch) -> list[float]:
    """Retries wait between attempts; record the waits instead of sleeping in tests."""
    waits: list[float] = []
    monkeypatch.setattr(controller_module, "_sleep", waits.append)
    return waits


def test_ollama_controller_reports_connection_failure_without_raising(
    _record_backoff_sleeps: list[float],
) -> None:
    controller = OllamaChatController(base_url="http://127.0.0.1:1")

    reply = controller.chat("hello")

    assert is_model_unavailable_reply(reply)
    assert "did not answer after 3 attempts" in reply
    assert "connection failed" in reply
    assert _record_backoff_sleeps == [1.0, 2.0]


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

    assert is_model_unavailable_reply(reply)
    assert "timed out after" in reply


def test_openai_controller_reports_timeout_without_raising(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(controller_module.request, "urlopen", _raise_timeout)
    controller = OpenAIResponsesController(api_key="test-key")

    reply = controller.chat("hello", tmp_path)

    assert is_model_unavailable_reply(reply)
    assert "timed out after" in reply


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

    selected = select_context_documents(
        load_documents(repo), "how should we handle transparency?", limit=3
    )

    assert selected
    assert selected[0].path == "docs/20-ethical-model/principles/transparency.md"


def test_select_context_documents_prefers_maturity_checklist_for_checklist_prompt(
    tmp_path: Path,
) -> None:
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

    selected = select_context_documents(
        load_documents(repo), "show the maturity checklist", limit=3
    )

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


def test_ollama_controller_sends_kob_identity_and_captures_usage(
    tmp_path: Path, monkeypatch
) -> None:
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

    assert reply.startswith("hi")
    prompt_sent = captured["body"]["prompt"]
    assert "You are kob, version" in prompt_sent
    assert "powered by the test-model model" in prompt_sent
    assert "Kobkob LLC" in prompt_sent
    assert controller.last_usage == {"prompt_tokens": 10, "completion_tokens": 5}


def test_ollama_identity_does_not_attribute_olmo_to_kobkob(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(json.dumps({"response": "hi"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController(model="olmo2:7b-1124-instruct-q4_K_M")

    controller.chat("who are you?", tmp_path)

    prompt_sent = captured["body"]["prompt"]
    assert "Allen Institute for AI" in prompt_sent
    assert "does NOT make the underlying model" in prompt_sent


def test_openai_controller_sends_kob_identity_and_captures_usage(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            json.dumps(
                {
                    "id": "resp_1",
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "hi"}]}
                    ],
                    "usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OpenAIResponsesController(api_key="test-key", model="gpt-5")

    reply = controller.chat("hello", tmp_path)

    assert reply.startswith("hi")
    developer_message = captured["body"]["input"][0]["content"]
    assert "You are kob, version" in developer_message
    assert "powered by the gpt-5 model" in developer_message
    assert controller.last_usage == {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}


def test_generic_chat_context_does_not_dump_full_manifesto_body(tmp_path: Path) -> None:
    # Doctrine/manifesto interpretation belongs strictly to the mentor workflow's own
    # prompt-building, not generic chat - every document, manifesto included, gets the
    # same short teaser excerpt here, never the full body.
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
    assert "KAIDF principle line 49." not in context


def test_resolve_timeout_seconds_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_TIMEOUT_SECONDS", raising=False)

    assert (
        controller_module._resolve_timeout_seconds()
        == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS
    )


def test_resolve_timeout_seconds_honors_valid_override(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "600")

    assert controller_module._resolve_timeout_seconds() == 600


def test_resolve_timeout_seconds_falls_back_on_garbage_value(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "not-a-number")

    assert (
        controller_module._resolve_timeout_seconds()
        == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS
    )

    monkeypatch.setenv("AIDF_CHAT_TIMEOUT_SECONDS", "-5")

    assert (
        controller_module._resolve_timeout_seconds()
        == controller_module._DEFAULT_HTTP_TIMEOUT_SECONDS
    )


def test_ollama_controller_appends_caveat_to_successful_reply(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    def fake_urlopen(req, timeout=None):
        return _FakeResponse(json.dumps({"response": "The sky is blue."}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController()

    reply = controller.chat("why is the sky blue?", tmp_path)

    assert reply.startswith("The sky is blue.")
    assert controller_module.RESPONSE_CAVEAT in reply


def test_null_controller_reply_has_no_caveat() -> None:
    controller = controller_module.NullChatController()

    reply = controller.chat("hello")

    assert controller_module.RESPONSE_CAVEAT not in reply


def test_ollama_controller_timeout_message_has_no_caveat(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(controller_module.request, "urlopen", _raise_timeout)
    controller = OllamaChatController()

    reply = controller.chat("hello", tmp_path)

    assert controller_module.RESPONSE_CAVEAT not in reply


def test_mentor_instructions_override_replaces_default_and_drops_denial(
    tmp_path: Path, monkeypatch
) -> None:
    # Regression test: DEFAULT_CHAT_INSTRUCTIONS flatly denies file/shell access, which used to
    # get sent on every mentor turn too - directly contradicting the action protocol taught
    # later in the same prompt, and reliably causing "As an AI I can't execute commands..."
    # hallucinations. mentor.py must override it with MENTOR_CHAT_INSTRUCTIONS instead.
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController()

    controller.chat(
        "continue the workflow", tmp_path, instructions=controller_module.MENTOR_CHAT_INSTRUCTIONS
    )

    prompt_sent = captured["body"]["prompt"]
    assert "You cannot read or write files or run shell commands" not in prompt_sent
    assert "propose it using that protocol" in prompt_sent


def test_default_chat_still_denies_tool_access_when_no_override_given(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)
    controller = OllamaChatController()

    controller.chat("just chatting", tmp_path)

    prompt_sent = captured["body"]["prompt"]
    assert "You cannot read or write files or run shell commands" in prompt_sent


class _JsonResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_JsonResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _http_error(code: int) -> error.HTTPError:
    return error.HTTPError("http://model.test", code, "msg", {}, io.BytesIO(b"details"))


def _scripted_urlopen(monkeypatch, outcomes: list, calls: list) -> None:
    """Each call returns the next outcome: an exception to raise, or a payload to return."""

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return _JsonResponse(outcome)

    monkeypatch.setattr(controller_module.request, "urlopen", fake_urlopen)


OPENAI_OK = {
    "id": "resp_1",
    "output": [
        {"type": "message", "content": [{"type": "output_text", "text": "Recovered answer."}]}
    ],
}
OLLAMA_OK = {"response": "Recovered answer.", "eval_count": 3}


def test_transient_http_error_is_retried_until_the_model_answers(
    tmp_path: Path, monkeypatch, _record_backoff_sleeps: list[float]
) -> None:
    calls: list = []
    _scripted_urlopen(monkeypatch, [_http_error(503), _http_error(500), OPENAI_OK], calls)

    reply = OpenAIResponsesController(api_key="k").chat("hello", tmp_path)

    assert len(calls) == 3
    assert _record_backoff_sleeps == [1.0, 2.0]
    assert reply.startswith("Recovered answer.")
    assert not is_model_unavailable_reply(reply)


def test_connection_failure_is_retried_then_succeeds(
    tmp_path: Path, monkeypatch, _record_backoff_sleeps: list[float]
) -> None:
    calls: list = []
    _scripted_urlopen(monkeypatch, [error.URLError("refused"), OLLAMA_OK], calls)

    reply = OllamaChatController().chat("hello", tmp_path)

    assert len(calls) == 2
    assert _record_backoff_sleeps == [1.0]
    assert reply.startswith("Recovered answer.")


def test_persistent_transient_errors_end_in_a_structured_unavailable_reply(
    tmp_path: Path, monkeypatch, _record_backoff_sleeps: list[float]
) -> None:
    calls: list = []
    _scripted_urlopen(monkeypatch, [_http_error(503)] * 3, calls)

    reply = OpenAIResponsesController(api_key="k").chat("hello", tmp_path)

    assert len(calls) == 3
    assert _record_backoff_sleeps == [1.0, 2.0]
    assert reply.startswith(MODEL_UNAVAILABLE_PREFIX)
    assert "OpenAI API did not answer after 3 attempts (HTTP 503)" in reply
    assert "Nothing was recorded" in reply


def test_non_transient_http_error_is_not_retried(
    tmp_path: Path, monkeypatch, _record_backoff_sleeps: list[float]
) -> None:
    calls: list = []
    _scripted_urlopen(monkeypatch, [_http_error(401)], calls)

    reply = OpenAIResponsesController(api_key="bad").chat("hello", tmp_path)

    assert len(calls) == 1
    assert _record_backoff_sleeps == []
    assert reply == "OpenAI API error 401: details"


def test_ollama_persistent_server_errors_are_reported_as_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list = []
    _scripted_urlopen(monkeypatch, [_http_error(502)] * 3, calls)

    reply = OllamaChatController(base_url="http://model.test").chat("hello", tmp_path)

    assert len(calls) == 3
    assert "Local Ollama at http://model.test did not answer after 3 attempts" in reply
    assert "HTTP 502" in reply


def test_model_unavailable_detection_ignores_normal_replies() -> None:
    assert is_model_unavailable_reply(f"{MODEL_UNAVAILABLE_PREFIX} anything")
    assert not is_model_unavailable_reply("Here is my answer.")
    assert not is_model_unavailable_reply("OpenAI API error 401: details")
