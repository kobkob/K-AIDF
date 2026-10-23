from __future__ import annotations

from pathlib import Path

import pytest

from agent_aidf.tools import (
    ACTION_MARKER_END,
    ACTION_MARKER_START,
    ACTION_PROTOCOL_INSTRUCTIONS,
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
    action = ProposedAction(
        kind="write_file", path="docs/01_intent_constraints/templates/ICB.md", content="hello"
    )

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
        ("y", True),
        ("sim", True),
        ("Sim.", True),
        ("s", True),
        ("true", True),
        ("1", True),
        ("yes, do it", True),
        ("sim, pode", True),
        ("done", False),
        ("pronto", False),
        ("finish", False),
        ("ok", False),
        ("accept", False),
        ("go ahead", False),
        ("correct", False),
        ("yep, let's do it", False),
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


def test_extract_proposed_action_tolerates_real_olmo_closing_typo() -> None:
    # Captured verbatim from a live olmo2:7b-1124-instruct-q4_K_M response: the model got the
    # JSON exactly right but closed the block with a bare "<<<" instead of "KOB_ACTION>>>".
    # The old exact-closing-marker regex silently dropped this entire action, which is what
    # made a real tool-use attempt look like "the agent is bypassing tool execution".
    text = (
        "Here's how you might propose this action to the user:\n\n"
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": '
        '"docs/01_intent_constraints/templates/constraint-matrix.csv", '
        '"content": "privacy,comply with all applicable privacy laws"}\n'
        "<<<\n\n"
        "This action suggests writing a new row in the constraint matrix CSV file."
    )

    cleaned, action = extract_proposed_action(text)

    assert action is not None
    assert action.kind == "write_file"
    assert action.path == "docs/01_intent_constraints/templates/constraint-matrix.csv"
    assert "privacy" in action.content
    assert "KOB_ACTION" not in cleaned
    assert "Here's how you might propose this action to the user:" in cleaned
    assert "This action suggests writing a new row" in cleaned


def test_extract_proposed_action_tolerates_missing_closing_brace_and_raw_newlines() -> None:
    # Captured verbatim (shape-for-shape) from a second live olmo2:7b-1124-instruct-q4_K_M
    # response: the model wrote a long multi-line "content" value with a literal (unescaped)
    # newline partway through, then jumped straight from the closing quote to the KOB_ACTION>>>
    # marker without ever writing the JSON object's own closing "}". Both are real, observed
    # small-model slips, not hypothetical edge cases - strict json.loads rejects both.
    text = (
        "<<<KOB_ACTION\n"
        '{"action": "write_file", "path": "docs/01_intent_constraints/ICB.md", "content": '
        '"## Problem Statement\\nFirst line is properly escaped.\n'
        'Second line has a raw, unescaped newline before it."\n'
        "KOB_ACTION>>>\n\n"
        "Please review this answer yourself."
    )

    cleaned, action = extract_proposed_action(text)

    assert action is not None
    assert action.kind == "write_file"
    assert action.path == "docs/01_intent_constraints/ICB.md"
    assert "First line is properly escaped." in action.content
    assert "Second line has a raw, unescaped newline before it." in action.content
    assert "KOB_ACTION" not in cleaned
    assert "Please review this answer yourself." in cleaned


def test_action_protocol_instructions_show_a_closing_marker_for_every_example() -> None:
    # Regression test for the actual bug: an earlier version of this string showed the
    # write_file example with NO closing marker at all, so the model had no correct example
    # to imitate for exactly the action kind it needed.
    examples = ACTION_PROTOCOL_INSTRUCTIONS.split("or\n")
    assert len(examples) >= 2
    for example in examples:
        if ACTION_MARKER_START in example:
            assert ACTION_MARKER_END in example
