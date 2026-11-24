"""kob review: proposals, path confinement, diff confirmation and the action log. No real model."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from agent_aidf.cli.main import _run_cli
from agent_aidf.review import (
    REVIEW_INSTRUCTIONS,
    REVISION_CLOSE,
    REVISION_OPEN,
    ReviewError,
    extract_revision,
    propose_revision,
    run_review,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / ".kaidf" / "docs").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".kaidf" / "docs" / "scope.md").write_text(
        "# Scope\n\nThe system does many things.\n", encoding="utf-8"
    )
    (root / ".git" / "config.md").write_text("secret\n", encoding="utf-8")
    return root


cli_main = importlib.import_module("agent_aidf.cli.main")


def _reply(body: str) -> str:
    return f"Here is the revision.\n{REVISION_OPEN}\n{body}\n{REVISION_CLOSE}\n"


def _fake_ask(body: str, seen: list[tuple[str, str]] | None = None):
    def ask(prompt: str, instructions: str) -> str:
        if seen is not None:
            seen.append((prompt, instructions))
        return _reply(body)

    return ask


def test_the_revision_is_taken_between_the_tags_and_commentary_is_dropped() -> None:
    assert extract_revision(_reply("# Scope\n\nTight.")) == "# Scope\n\nTight."


def test_a_reply_without_the_tags_yields_no_revision() -> None:
    assert extract_revision("Sure, here is a shorter version.") is None
    assert extract_revision(f"{REVISION_OPEN} unterminated") is None


def test_the_proposal_carries_a_unified_diff_and_writes_nothing(project: Path) -> None:
    target = project / ".kaidf" / "docs" / "scope.md"
    before = target.read_text(encoding="utf-8")

    proposal = propose_revision(
        project, ".kaidf/docs/scope.md", "tighten it", _fake_ask("# Scope\n\nTight.")
    )

    assert proposal.changed
    assert "-The system does many things." in proposal.diff
    assert "+Tight." in proposal.diff
    assert target.read_text(encoding="utf-8") == before


def test_the_document_is_sent_as_untrusted_data_with_the_instruction(project: Path) -> None:
    seen: list[tuple[str, str]] = []

    propose_revision(project, ".kaidf/docs/scope.md", "tighten it", _fake_ask("# Scope", seen=seen))

    prompt, instructions = seen[0]
    assert "Operator instruction: tighten it" in prompt
    assert "many things" in prompt
    assert instructions == REVIEW_INSTRUCTIONS
    assert "untrusted" in REVIEW_INSTRUCTIONS.lower()


@pytest.mark.parametrize("path", ["../outside.md", "/etc/passwd"])
def test_a_path_outside_the_project_is_refused_before_the_model_is_asked(
    project: Path, path: str
) -> None:
    def must_not_ask(prompt: str, instructions: str) -> str:
        raise AssertionError("asked the model about a path outside the project")

    with pytest.raises(ReviewError):
        propose_revision(project, path, "x", must_not_ask)


def test_a_missing_file_and_an_empty_instruction_are_refused(project: Path) -> None:
    with pytest.raises(ReviewError, match="not a file"):
        propose_revision(project, ".kaidf/docs/none.md", "x", _fake_ask("y"))
    with pytest.raises(ReviewError, match="needs an instruction"):
        propose_revision(project, ".kaidf/docs/scope.md", "   ", _fake_ask("y"))


def test_a_reply_without_a_document_stops_with_nothing_changed(project: Path) -> None:
    target = project / ".kaidf" / "docs" / "scope.md"
    before = target.read_text(encoding="utf-8")

    with pytest.raises(ReviewError, match="did not return a revised document"):
        propose_revision(
            project,
            ".kaidf/docs/scope.md",
            "x",
            lambda prompt, instructions: "no tags here",
        )
    assert target.read_text(encoding="utf-8") == before


def test_declining_leaves_the_file_untouched_and_logs_nothing(project: Path) -> None:
    scaffold = project / ".kaidf"
    target = scaffold / "docs" / "scope.md"
    before = target.read_text(encoding="utf-8")
    proposal = propose_revision(project, ".kaidf/docs/scope.md", "x", _fake_ask("Tight."))

    outcome = run_review(project, scaffold, proposal, confirm=lambda prompt: False, model="m")

    assert outcome == "Nothing was written."
    assert target.read_text(encoding="utf-8") == before
    assert not (scaffold / "action-log.jsonl").exists()


def test_confirming_writes_the_document_and_logs_the_model_used(project: Path) -> None:
    scaffold = project / ".kaidf"
    target = scaffold / "docs" / "scope.md"
    proposal = propose_revision(project, ".kaidf/docs/scope.md", "x", _fake_ask("Tight."))

    outcome = run_review(project, scaffold, proposal, confirm=lambda prompt: True, model="olmo-3")

    assert "Wrote" in outcome
    assert target.read_text(encoding="utf-8") == "Tight."
    entry = json.loads((scaffold / "action-log.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert entry["event"] == "review_edit"
    assert entry["path"] == ".kaidf/docs/scope.md"
    assert entry["model"] == "olmo-3"
    assert entry["sha256_before"] != entry["sha256_after"]


def test_an_unchanged_revision_writes_nothing_and_says_so(project: Path) -> None:
    scaffold = project / ".kaidf"
    current = (scaffold / "docs" / "scope.md").read_text(encoding="utf-8")
    proposal = propose_revision(project, ".kaidf/docs/scope.md", "x", _fake_ask(current))

    def must_not_confirm(prompt: str) -> bool:
        raise AssertionError("asked to confirm an unchanged document")

    outcome = run_review(project, scaffold, proposal, confirm=must_not_confirm, model="m")

    assert outcome.startswith("No change proposed")


def test_a_protected_directory_is_refused_even_after_confirmation(project: Path) -> None:
    scaffold = project / ".kaidf"
    proposal = propose_revision(project, ".git/config.md", "x", _fake_ask("changed"))

    with pytest.raises(ReviewError):
        run_review(project, scaffold, proposal, confirm=lambda prompt: True, model="m")
    assert (project / ".git" / "config.md").read_text(encoding="utf-8") == "secret\n"


def test_the_cli_without_a_terminal_or_yes_refuses_before_asking_the_model(
    project: Path, monkeypatch, capsys
) -> None:
    def must_not_build(*args, **kwargs):
        raise AssertionError("built a model controller without a confirmation path")

    monkeypatch.setattr("agent_aidf.controller.build_controller", must_not_build)

    code = _run_cli(["--project", str(project), "review", ".kaidf/docs/scope.md", "x"])

    assert code == 2
    assert "needs a terminal" in capsys.readouterr().err


def test_the_cli_with_yes_writes_the_reviewed_document(project: Path, monkeypatch, capsys) -> None:
    class FakeController:
        def chat(self, prompt, repo_root=None, *, instructions=None):
            return _reply("# Scope\n\nTight.")

    monkeypatch.setattr("agent_aidf.controller.build_controller", lambda *a, **k: FakeController())
    monkeypatch.setattr(cli_main, "active_model_label", lambda: "fake-model")

    code = _run_cli(
        ["--project", str(project), "review", ".kaidf/docs/scope.md", "tighten", "--yes"]
    )

    assert code == 0
    assert "+Tight." in capsys.readouterr().out
    assert (project / ".kaidf" / "docs" / "scope.md").read_text(encoding="utf-8") == (
        "# Scope\n\nTight."
    )
