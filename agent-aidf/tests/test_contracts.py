from __future__ import annotations

import json
from pathlib import Path

from agent_aidf.contracts import create_basic_contract, get_contract, list_contracts
from agent_aidf.instant_apps import stop_instant_app
from agent_aidf.mentor import continue_mentor_workflow


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    _write(repo / "README.md", "# Demo\n")
    _write(
        repo / "docs/00-overview/manifesto.md",
        "---\n"
        "id: docs/00-overview/manifesto.md\n"
        "title: Manifesto\n"
        "document_class: core-doc\n"
        "phase: 00-overview\n"
        "visibility: internal\n"
        "status: active\n"
        "---\n\n"
        "# Manifesto\n\n"
        "The project should serve people.\n",
    )
    _write(
        repo / "docs/00-overview/principles.md",
        "---\n"
        "id: docs/00-overview/principles.md\n"
        "title: Principles\n"
        "document_class: core-doc\n"
        "phase: 00-overview\n"
        "visibility: internal\n"
        "status: active\n"
        "---\n\n"
        "# Principles\n\n"
        "Transparency and validation matter.\n",
    )
    return repo


def test_create_basic_contract_writes_standard_files_and_phases(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    contract = create_basic_contract(
        repo,
        contract_id="basic-mentor-contract",
        brief="Create a mentor-led contract for a quiz-driven localhost workflow.",
    )

    assert contract.contract_id == "basic-mentor-contract"
    assert (repo / "contracts" / "basic-mentor-contract" / "contract.json").is_file()
    assert (repo / "contracts" / "basic-mentor-contract" / "contract.md").is_file()
    assert (repo / "contracts" / "basic-mentor-contract" / "quiz.md").is_file()

    payload = json.loads((repo / "contracts" / "basic-mentor-contract" / "contract.json").read_text(encoding="utf-8"))
    assert payload["contract_id"] == "basic-mentor-contract"
    assert payload["brief"] == "Create a mentor-led contract for a quiz-driven localhost workflow."
    assert len(payload["phases"]) == 5
    assert payload["phases"][0]["name"] == "Intent & Constraints"
    assert payload["phases"][4]["name"] == "Verification & Transfer"

    quiz = (repo / "contracts" / "basic-mentor-contract" / "quiz.md").read_text(encoding="utf-8")
    assert "1. Intent & Constraints" in quiz
    assert "5. Verification & Transfer" in quiz
    assert "What outcome should this project achieve first" in quiz


def test_create_basic_contract_uses_mentor_state_and_current_app_context(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)
    continue_mentor_workflow(
        repo,
        answer="We need a transparent localhost web app with human validation and clear accountability.",
    )

    contract = create_basic_contract(repo)

    assert contract.current_app_id == "mentor-web-app"
    assert contract.current_app_url is not None
    assert "latest_answer=We need a transparent localhost web app" in contract.source_summary
    loaded = get_contract(repo, contract.contract_id)
    assert loaded is not None
    assert loaded.current_app_id == "mentor-web-app"
    assert list_contracts(repo)[0].contract_id == contract.contract_id
    stop_instant_app(repo, "mentor-web-app")
