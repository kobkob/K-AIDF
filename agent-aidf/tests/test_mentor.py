from __future__ import annotations

from pathlib import Path

import agent_aidf.controller as controller_module
from agent_aidf.instant_apps import load_instant_app_runtime, stop_instant_app
from agent_aidf.maturity import phase_progress, phase_snapshot
from agent_aidf.mentor import continue_mentor_workflow, load_mentor_state, reset_mentor_state
from agent_aidf.project import ProjectStatus


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo_with_phase_one_scaffold(tmp_path: Path) -> Path:
    """A real project_root/.kaidf/-shaped repo (matching resolve_mentor_repo_root's contract)
    with phase 1's real (stub) artifact files, matching exactly what kaidf-gen scaffolds: pure
    headers in the .md files, header-only .csv - i.e. not filled in."""
    repo = tmp_path / "project" / ".kaidf"
    _write(repo / "README.md", "# Demo\n")
    _write(
        repo / "docs/01_intent_constraints/README.md",
        "# Phase 1 - Intent & Constraints\n\nDeliverable: Intent & Constraint Brief (ICB)\n",
    )
    _write(
        repo / "docs/01_intent_constraints/templates/ICB.md",
        "# Intent & Constraint Brief (ICB)\n\n"
        "## Problem Statement\n## Business Objective\n## Non-Negotiables\n## Constraints\n"
        "## Out of Scope\n## Success Metrics\n## Risks & Assumptions\n",
    )
    _write(
        repo / "docs/01_intent_constraints/templates/constraint-matrix.csv",
        "constraint_type,description,owner,severity\n",
    )
    _write(repo / "docs/01_intent_constraints/data-provenance.md", "# Data Provenance\n\n## Data Sources\n")
    _write(repo / "docs/01_intent_constraints/exit-criteria.md", "# Exit Criteria (Phase 1)\n- ICB completed\n")
    return repo


class _FakeController:
    """A scripted ChatController stand-in: returns replies from a fixed queue, in order."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.last_usage = None
        self.previous_response_id = None

    def chat(self, prompt: str, repo_root=None) -> str:
        if not self._replies:
            return "Mentor assessment: nothing more to add right now."
        return self._replies.pop(0)


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
    assert "Current focus: Intent & Constraints" in turn.message
    assert state.pending_category == "Intent & Constraints"
    assert state.pending_question is not None
    assert state.pending_phase_order == 1
    assert state.accepted_phases == []


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


def _status_for(repo: Path) -> ProjectStatus:
    state = load_mentor_state(repo)
    return ProjectStatus(
        project_root=repo,
        repo_root=repo,
        has_kaidf=True,
        document_count=0,
        pack_count=0,
        packs=[],
        instant_app_count=0,
        instant_apps=[],
        mentor_step_count=state.step_count,
        mentor_pending_category=state.pending_category,
        mentor_current_app_id=state.current_app_id,
        mentor_current_app_url=None,
        mentor_accepted_phases=state.accepted_phases,
    )


def test_five_answers_without_artifacts_never_marks_a_phase_done(tmp_path: Path) -> None:
    # Regression test for the exact bug reported: answering repeatedly must never flip a
    # phase to "done" on its own - only real artifacts + explicit acceptance can.
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    continue_mentor_workflow(repo)
    for _ in range(5):
        continue_mentor_workflow(repo, answer="Just a short answer with no real content yet.")

    state = load_mentor_state(repo)
    status = _status_for(repo)
    completed, total = phase_progress(status)

    assert state.step_count == 5
    assert state.accepted_phases == []
    assert completed == 0
    assert total == 5
    snapshot = phase_snapshot(status)
    assert snapshot[0]["state"] == "current"
    assert all(phase["state"] != "done" for phase in snapshot)


def test_mentor_proposes_file_action_and_pauses_for_confirmation(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Here is a draft ICB for you.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": ".kaidf/docs/01_intent_constraints/templates/ICB.md", '
        '"content": "# Intent & Constraint Brief (ICB)\\n\\n## Problem Statement\\nWe need X.\\n"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    turn = continue_mentor_workflow(repo, answer="We need a tool to help onboard new hires.")
    state = load_mentor_state(repo)

    assert "Proposed action: write" in turn.message
    assert "ICB.md" in turn.message
    assert state.pending_file_action is not None
    assert state.pending_file_action["path"].endswith("templates/ICB.md")
    # Not written yet - still just the stub.
    icb_path = repo / "docs/01_intent_constraints/templates/ICB.md"
    assert "We need X." not in icb_path.read_text(encoding="utf-8")


def test_confirming_file_action_writes_it_and_can_lead_to_acceptance(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Here is a draft ICB for you.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": ".kaidf/docs/01_intent_constraints/templates/ICB.md", '
        '"content": "# Intent & Constraint Brief (ICB)\\n\\n## Problem Statement\\nWe need X.\\n"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    continue_mentor_workflow(repo, answer="We need a tool to help onboard new hires.")
    turn = continue_mentor_workflow(repo, answer="yes")
    state = load_mentor_state(repo)

    icb_path = repo / "docs/01_intent_constraints/templates/ICB.md"
    assert "We need X." in icb_path.read_text(encoding="utf-8")
    assert state.pending_file_action is None
    # ICB.md is filled in now, but constraint-matrix.csv and data-provenance.md are still
    # stubs, so the phase should NOT be ready for acceptance yet.
    assert not state.awaiting_acceptance
    assert state.accepted_phases == []
    assert "Next question" in turn.message


def test_rejecting_a_proposed_file_action_does_not_write_it(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Here is a draft.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": ".kaidf/docs/01_intent_constraints/templates/ICB.md", '
        '"content": "should not be written"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block, "Understood, I will hold off on that draft."])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    continue_mentor_workflow(repo, answer="We need a tool to help onboard new hires.")
    continue_mentor_workflow(repo, answer="no, let's not write that yet")
    state = load_mentor_state(repo)

    icb_path = repo / "docs/01_intent_constraints/templates/ICB.md"
    assert "should not be written" not in icb_path.read_text(encoding="utf-8")
    assert state.pending_file_action is None


def test_full_phase_acceptance_advances_to_phase_two(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    # Fill in phase 1's artifacts directly (simulating prior mentor-driven or manual edits).
    _write(
        repo / "docs/01_intent_constraints/templates/ICB.md",
        "# Intent & Constraint Brief (ICB)\n\n## Problem Statement\nWe need an onboarding tool.\n",
    )
    _write(
        repo / "docs/01_intent_constraints/templates/constraint-matrix.csv",
        "constraint_type,description,owner,severity\nbudget,limited,PM,high\n",
    )
    _write(
        repo / "docs/01_intent_constraints/data-provenance.md",
        "# Data Provenance\n\n## Data Sources\nInternal HR records.\n",
    )
    fake = _FakeController(["Great, that all looks solid and ready to move on."])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    turn = continue_mentor_workflow(repo, answer="Here is more detail on the onboarding tool.")
    state = load_mentor_state(repo)

    assert state.awaiting_acceptance
    assert "accept this phase as complete" in turn.message

    turn2 = continue_mentor_workflow(repo, answer="yes")
    state2 = load_mentor_state(repo)
    status = _status_for(repo)
    completed, total = phase_progress(status)

    assert state2.accepted_phases == [1]
    assert state2.pending_phase_order == 2
    assert "Phase 1 (Intent & Constraints) accepted." in turn2.message
    assert "Discovery & Mapping" in turn2.message
    assert completed == 1
    assert total == 5
    snapshot = phase_snapshot(status)
    assert snapshot[0]["state"] == "done"
    assert snapshot[1]["state"] == "current"


def test_rejecting_acceptance_keeps_phase_open(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    _write(
        repo / "docs/01_intent_constraints/templates/ICB.md",
        "# Intent & Constraint Brief (ICB)\n\n## Problem Statement\nWe need an onboarding tool.\n",
    )
    _write(
        repo / "docs/01_intent_constraints/templates/constraint-matrix.csv",
        "constraint_type,description,owner,severity\nbudget,limited,PM,high\n",
    )
    _write(
        repo / "docs/01_intent_constraints/data-provenance.md",
        "# Data Provenance\n\n## Data Sources\nInternal HR records.\n",
    )
    fake = _FakeController(["Looks solid.", "Noted, let's refine it further."])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    continue_mentor_workflow(repo, answer="Here is more detail on the onboarding tool.")
    turn = continue_mentor_workflow(repo, answer="no, not yet, I want to revise the budget line")
    state = load_mentor_state(repo)

    assert state.accepted_phases == []
    assert not state.awaiting_acceptance
    assert state.pending_phase_order == 1
    assert "Next question" in turn.message


def test_unsafe_proposed_path_is_reported_without_crashing(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Here is a draft.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": "../../escape.txt", "content": "malicious"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    continue_mentor_workflow(repo, answer="We need a tool to help onboard new hires.")
    turn = continue_mentor_workflow(repo, answer="yes")

    assert "Could not write that file" in turn.message
    assert not any(p.name == "escape.txt" for p in tmp_path.rglob("*"))


def test_yolo_applies_write_action_immediately_without_pausing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KOB_YOLO", "1")
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Drafting now.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": ".kaidf/docs/01_intent_constraints/templates/ICB.md", '
        '"content": "# Intent & Constraint Brief (ICB)\\n\\n## Problem Statement\\nAuto-drafted.\\n"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    turn = continue_mentor_workflow(repo, answer="We need a tool to help onboard new hires.")
    state = load_mentor_state(repo)

    assert "[--yolo]" in turn.message
    assert "Next question" in turn.message
    assert state.pending_file_action is None
    icb_path = repo / "docs/01_intent_constraints/templates/ICB.md"
    assert "Auto-drafted." in icb_path.read_text(encoding="utf-8")


def test_yolo_applies_run_shell_action_immediately(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KOB_YOLO", "1")
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    action_block = (
        "Checking something.\n"
        "<<<KOB_ACTION\n"
        '{"action": "run_shell", "command": "echo yolo-ran"}\n'
        "KOB_ACTION>>>"
    )
    fake = _FakeController([action_block])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    turn = continue_mentor_workflow(repo, answer="Please check something for me.")
    state = load_mentor_state(repo)

    assert "[--yolo]" in turn.message
    assert "yolo-ran" in turn.message
    assert state.pending_file_action is None


def test_yolo_does_not_bypass_phase_acceptance_confirmation(tmp_path: Path, monkeypatch) -> None:
    # --yolo governs tool-execution risk, not the methodology's own quality gate: a phase must
    # still be explicitly accepted even when --yolo is active.
    monkeypatch.setenv("KOB_YOLO", "1")
    repo = _build_repo_with_phase_one_scaffold(tmp_path)
    _write(
        repo / "docs/01_intent_constraints/templates/ICB.md",
        "# Intent & Constraint Brief (ICB)\n\n## Problem Statement\nWe need an onboarding tool.\n",
    )
    _write(
        repo / "docs/01_intent_constraints/templates/constraint-matrix.csv",
        "constraint_type,description,owner,severity\nbudget,limited,PM,high\n",
    )
    _write(
        repo / "docs/01_intent_constraints/data-provenance.md",
        "# Data Provenance\n\n## Data Sources\nInternal HR records.\n",
    )
    fake = _FakeController(["Looks solid and ready."])
    monkeypatch.setattr(controller_module, "build_controller", lambda: fake)

    continue_mentor_workflow(repo)
    turn = continue_mentor_workflow(repo, answer="Here is more detail on the onboarding tool.")
    state = load_mentor_state(repo)

    assert state.awaiting_acceptance
    assert state.accepted_phases == []
    assert "accept this phase as complete" in turn.message
