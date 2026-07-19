from __future__ import annotations

from pathlib import Path

from agent_aidf.instant_apps import load_instant_app_runtime, stop_instant_app
from agent_aidf.mentor import continue_mentor_workflow, load_mentor_state, reset_mentor_state


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


def test_mentor_starts_with_pending_question_and_persists_state(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    turn = continue_mentor_workflow(repo)
    state = load_mentor_state(repo)

    assert "Mentor workflow is active." in turn.message
    assert "Current focus: manifesto" in turn.message
    assert state.pending_category == "manifesto"
    assert state.pending_question is not None


def test_mentor_answer_advances_workflow_and_records_interaction(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)

    turn = continue_mentor_workflow(
        repo,
        answer="We need a transparent localhost web app with human validation and clear accountability.",
    )
    state = load_mentor_state(repo)

    assert "Mentor assessment:" in turn.message
    assert "Action: created persistent web instant app 'mentor-web-app'" in turn.message
    assert "Next question:" in turn.message
    assert state.step_count == 1
    assert len(state.interactions) == 1
    assert state.pending_question is not None
    assert state.current_app_id == "mentor-web-app"
    assert (repo / "apps" / "mentor-web-app" / "mentor-notes.md").is_file()
    assert (repo / "apps" / "mentor-web-app" / "mentor-brief.json").is_file()
    readme = (repo / "apps" / "mentor-web-app" / "README.md").read_text(encoding="utf-8")
    assert "transparent localhost web app" in readme
    runtime = load_instant_app_runtime(repo, "mentor-web-app")
    assert runtime is not None
    assert runtime.status == "running"
    assert "http://127.0.0.1:" in turn.message
    stop_instant_app(repo, "mentor-web-app")


def test_mentor_reuses_current_app_for_later_relevant_answers(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)
    continue_mentor_workflow(
        repo,
        answer="We need a transparent localhost web app with human validation and clear accountability.",
    )
    first_runtime = load_instant_app_runtime(repo, "mentor-web-app")
    assert first_runtime is not None
    first_pid = first_runtime.pid

    turn = continue_mentor_workflow(
        repo,
        answer="The same web app should now expose a browser page for guided review on localhost.",
    )
    state = load_mentor_state(repo)

    assert "Action: reused persistent web instant app 'mentor-web-app'" in turn.message
    assert state.current_app_id == "mentor-web-app"
    notes = (repo / "apps" / "mentor-web-app" / "mentor-notes.md").read_text(encoding="utf-8")
    index_html = (repo / "apps" / "mentor-web-app" / "index.html").read_text(encoding="utf-8")
    second_runtime = load_instant_app_runtime(repo, "mentor-web-app")
    assert second_runtime is not None
    assert second_runtime.status == "running"
    assert second_runtime.pid != first_pid
    assert "restarted it at http://127.0.0.1:" in turn.message
    assert "Step 2" in notes
    assert "guided review screen on localhost" in index_html
    stop_instant_app(repo, "mentor-web-app")


def test_mentor_spawns_new_app_when_modality_changes(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)
    continue_mentor_workflow(
        repo,
        answer="We need a transparent localhost web app with human validation and clear accountability.",
    )

    turn = continue_mentor_workflow(
        repo,
        answer="We also need a separate terminal shell app for internal reviewers to capture checklist notes.",
    )
    state = load_mentor_state(repo)

    assert "Action: spawned new persistent shell instant app 'mentor-shell-app'" in turn.message
    assert "stopped superseded app 'mentor-web-app'" in turn.message
    assert state.current_app_id == "mentor-shell-app"
    assert (repo / "apps" / "mentor-shell-app" / "main.py").is_file()
    previous_runtime = load_instant_app_runtime(repo, "mentor-web-app")
    assert previous_runtime is not None
    assert previous_runtime.status == "stopped"
    stop_instant_app(repo, "mentor-web-app")


def test_mentor_spawns_second_app_when_answer_explicitly_requests_new_one(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)
    continue_mentor_workflow(
        repo,
        answer="We need a transparent localhost web app with human validation and clear accountability.",
    )

    turn = continue_mentor_workflow(
        repo,
        answer="Create another new app: a separate browser workflow for approval leaders on localhost.",
    )
    state = load_mentor_state(repo)

    assert "Action: spawned new persistent web instant app 'mentor-web-app-2'" in turn.message
    assert state.current_app_id == "mentor-web-app-2"
    assert (repo / "apps" / "mentor-web-app-2" / "index.html").is_file()
    runtime = load_instant_app_runtime(repo, "mentor-web-app-2")
    assert runtime is not None
    assert runtime.status == "running"
    previous_runtime = load_instant_app_runtime(repo, "mentor-web-app")
    assert previous_runtime is not None
    assert previous_runtime.status == "stopped"
    stop_instant_app(repo, "mentor-web-app")
    stop_instant_app(repo, "mentor-web-app-2")


def test_mentor_reset_removes_state_file(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    continue_mentor_workflow(repo)

    path = reset_mentor_state(repo)

    assert not path.exists()
