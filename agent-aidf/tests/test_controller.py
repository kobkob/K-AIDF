from __future__ import annotations

from pathlib import Path

from agent_aidf.controller import OpenAIResponsesController, build_controller, select_context_documents
from agent_aidf.instant_apps import create_instant_app
from agent_aidf.repo import load_documents


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
