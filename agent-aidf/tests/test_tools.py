from __future__ import annotations

from pathlib import Path

import pytest

from agent_aidf.tools import (
    ProposedAction,
    SafeActionTool,
    UnsafeActionPathError,
    apply_action,
    apply_run_shell_action,
    apply_write_action,
    extract_proposed_action,
    is_affirmative,
    resolve_safe_path,
)


def test_extract_proposed_action_parses_valid_block() -> None:
    text = (
        "Here is a draft for you.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": "docs/01_intent_constraints/templates/ICB.md", '
        '"content": "# Intent & Constraint Brief\\n\\nWe want X."}\n'
        "KOB_ACTION>>>\n"
    )

    cleaned, action = extract_proposed_action(text)

    assert cleaned == "Here is a draft for you."
    assert action is not None
    assert action.kind == "write_file"
    assert action.path == "docs/01_intent_constraints/templates/ICB.md"
    assert "Intent & Constraint Brief" in action.content


def test_extract_proposed_action_returns_none_when_no_block_present() -> None:
    cleaned, action = extract_proposed_action("Just a plain reply, no action here.")

    assert cleaned == "Just a plain reply, no action here."
    assert action is None


@pytest.mark.parametrize(
    "broken_block",
    [
        "<<<KOB_ACTION\nnot json at all\nKOB_ACTION>>>",
        '<<<KOB_ACTION\n{"action": "run_shell", "path": "x", "content": "y"}\nKOB_ACTION>>>',
        '<<<KOB_ACTION\n{"action": "write_file", "content": "y"}\nKOB_ACTION>>>',
        '<<<KOB_ACTION\n{"action": "write_file", "path": "x"}\nKOB_ACTION>>>',
        '<<<KOB_ACTION\n["not", "a", "dict"]\nKOB_ACTION>>>',
    ],
)
def test_extract_proposed_action_drops_malformed_or_unrecognized_blocks(broken_block: str) -> None:
    text = f"Some reply.\n{broken_block}\nMore text."

    cleaned, action = extract_proposed_action(text)

    assert action is None
    assert "KOB_ACTION" not in cleaned


def test_resolve_safe_path_allows_paths_inside_project(tmp_path: Path) -> None:
    resolved = resolve_safe_path(tmp_path, "docs/01_intent_constraints/templates/ICB.md")

    assert resolved == (tmp_path / "docs/01_intent_constraints/templates/ICB.md").resolve()


@pytest.mark.parametrize("escaping_path", ["../escape.txt", "../../etc/passwd", "/etc/passwd"])
def test_resolve_safe_path_rejects_escaping_paths(tmp_path: Path, escaping_path: str) -> None:
    with pytest.raises(UnsafeActionPathError):
        resolve_safe_path(tmp_path, escaping_path)


def test_apply_write_action_writes_file_and_creates_parents(tmp_path: Path) -> None:
    action = ProposedAction(kind="write_file", path="docs/01_intent_constraints/templates/ICB.md", content="hello")

    summary = apply_write_action(tmp_path, action)

    written = tmp_path / "docs/01_intent_constraints/templates/ICB.md"
    assert written.read_text(encoding="utf-8") == "hello"
    assert "5 characters" in summary


def test_apply_write_action_rejects_escaping_path(tmp_path: Path) -> None:
    action = ProposedAction(kind="write_file", path="../escape.txt", content="hello")

    with pytest.raises(UnsafeActionPathError):
        apply_write_action(tmp_path, action)


def test_safe_action_tool_write_file_end_to_end(tmp_path: Path) -> None:
    tool = SafeActionTool(tmp_path)
    text = (
        "Draft ready.\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": "notes.md", "content": "hi"}\n'
        "KOB_ACTION>>>"
    )

    cleaned, action = tool.extract_action(text)
    assert action is not None
    description = tool.describe(action)
    assert "notes.md" in description
    assert "hi" in description

    summary = tool.apply(action)

    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "hi"
    assert "notes.md" in summary


def test_safe_action_tool_run_shell_end_to_end(tmp_path: Path) -> None:
    tool = SafeActionTool(tmp_path)
    text = (
        "Let's check that.\n"
        "<<<KOB_ACTION\n"
        '{"action": "run_shell", "command": "echo hello-from-kob"}\n'
        "KOB_ACTION>>>"
    )

    cleaned, action = tool.extract_action(text)
    assert action is not None
    assert action.kind == "run_shell"
    description = tool.describe(action)
    assert "echo hello-from-kob" in description

    summary = tool.apply(action)

    assert "hello-from-kob" in summary
    assert "exit code 0" in summary


def test_extract_proposed_action_parses_run_shell_block() -> None:
    text = (
        "I'll check the git status.\n"
        "<<<KOB_ACTION\n"
        '{"action": "run_shell", "command": "git status"}\n'
        "KOB_ACTION>>>"
    )

    cleaned, action = extract_proposed_action(text)

    assert cleaned == "I'll check the git status."
    assert action is not None
    assert action.kind == "run_shell"
    assert action.command == "git status"


def test_apply_run_shell_action_captures_stdout_and_exit_code(tmp_path: Path) -> None:
    action = ProposedAction(kind="run_shell", command="echo hi && exit 0")

    summary = apply_run_shell_action(tmp_path, action)

    assert "hi" in summary
    assert "exit code 0" in summary


def test_apply_run_shell_action_captures_nonzero_exit_code(tmp_path: Path) -> None:
    action = ProposedAction(kind="run_shell", command="exit 7")

    summary = apply_run_shell_action(tmp_path, action)

    assert "exit code 7" in summary


def test_apply_run_shell_action_runs_in_project_root(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    action = ProposedAction(kind="run_shell", command="cat marker.txt")

    summary = apply_run_shell_action(tmp_path, action)

    assert "here" in summary


def test_apply_run_shell_action_times_out(tmp_path: Path) -> None:
    action = ProposedAction(kind="run_shell", command="sleep 5")

    summary = apply_run_shell_action(tmp_path, action, timeout=1)

    assert "timed out" in summary


def test_apply_action_dispatches_by_kind(tmp_path: Path) -> None:
    write = ProposedAction(kind="write_file", path="a.md", content="x")
    shell = ProposedAction(kind="run_shell", command="echo dispatched")

    write_summary = apply_action(tmp_path, write)
    shell_summary = apply_action(tmp_path, shell)

    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "x"
    assert "a.md" in write_summary
    assert "dispatched" in shell_summary


def test_apply_action_reports_unsafe_write_path_without_raising(tmp_path: Path) -> None:
    action = ProposedAction(kind="write_file", path="../escape.txt", content="x")

    summary = apply_action(tmp_path, action)

    assert "Could not write that file" in summary


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("yes", True),
        ("Yes!", True),
        ("yep, let's do it", True),
        ("ok", True),
        ("accept", True),
        ("go ahead", True),
        ("no", False),
        ("no, use a different title", False),
        ("not yet", False),
        ("don't write that", False),
        ("", False),
        ("maybe later", False),
        ("yesterday I already wrote this", False),
    ],
)
def test_is_affirmative(answer: str, expected: bool) -> None:
    assert is_affirmative(answer) is expected
