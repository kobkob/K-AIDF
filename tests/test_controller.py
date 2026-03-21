from __future__ import annotations

from pathlib import Path

from agent_aidf.controller import OpenAIResponsesController, build_controller


def test_build_controller_uses_stub_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    controller = build_controller()

    assert controller.chat("hello").startswith("AI chat controller is not configured yet.")


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

    controller = OpenAIResponsesController(api_key="test-key")
    payload = controller._build_payload("tell me about transparency", Path(repo))

    assert payload["model"] == "gpt-5"
    assert isinstance(payload["input"], list)
    user_message = payload["input"][1]
    assert "Detected packs: ethical-model" in user_message["content"]
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
