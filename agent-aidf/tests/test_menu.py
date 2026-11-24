"""kob menu: the numbered menu, its choices, and the plain fallback without a terminal."""

from __future__ import annotations

import pytest

from agent_aidf.cli.main import _build_cli_parser
from agent_aidf.cli.menu import MENU_ITEMS, render_menu, resolve_choice, run_menu


def _actions(calls: list[str], code: int = 0) -> dict:
    return {name: (lambda n=name: calls.append(n) or code) for name, _ in MENU_ITEMS}


def _scripted(answers: list[str]):
    """An input() stand-in that replays answers, then reports end of input."""
    remaining = list(answers)

    def read(prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read


def _collect() -> tuple[list[str], object]:
    lines: list[str] = []
    return lines, lambda text="": lines.append(str(text))


def test_the_menu_lists_the_five_everyday_commands_in_order() -> None:
    assert [name for name, _ in MENU_ITEMS] == ["status", "mentor", "models", "scan", "audit"]
    assert render_menu()[0].startswith("1. status")
    assert render_menu()[4].startswith("5. audit")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("1", "status"), ("4", "scan"), ("AUDIT", "audit"), (" models ", "models"), ("9", None)],
)
def test_a_choice_is_a_number_or_a_name(answer: str, expected: str | None) -> None:
    assert resolve_choice(answer) == expected


def test_without_a_terminal_the_menu_prints_choices_and_never_prompts() -> None:
    calls: list[str] = []
    lines, write = _collect()

    def must_not_read(prompt: str) -> str:
        raise AssertionError("prompted without a terminal")

    code = run_menu(_actions(calls), interactive=False, read=must_not_read, write=write)

    assert code == 0
    assert calls == []
    assert any(line.startswith("1. status") for line in lines)
    assert any("kob status" in line for line in lines)


def test_a_choice_runs_its_action_and_then_the_menu_returns_until_quit() -> None:
    calls: list[str] = []
    lines, write = _collect()

    code = run_menu(
        _actions(calls),
        interactive=True,
        read=_scripted(["2", "audit", "q"]),
        write=write,
    )

    assert code == 0
    assert calls == ["mentor", "audit"]


def test_an_unknown_choice_is_reported_and_the_menu_stays_open() -> None:
    calls: list[str] = []
    lines, write = _collect()

    run_menu(
        _actions(calls),
        interactive=True,
        read=_scripted(["17", "q"]),
        write=write,
    )

    assert calls == []
    assert any("Not a menu choice" in line for line in lines)


def test_end_of_input_quits_cleanly() -> None:
    calls: list[str] = []
    _lines, write = _collect()

    code = run_menu(_actions(calls), interactive=True, read=_scripted([]), write=write)

    assert code == 0
    assert calls == []


def test_a_failing_action_reports_its_exit_code_and_the_menu_continues() -> None:
    calls: list[str] = []
    lines, write = _collect()
    actions = _actions(calls)
    actions["models"] = lambda: calls.append("models") or 1

    code = run_menu(actions, interactive=True, read=_scripted(["3", "q"]), write=write)

    assert code == 0
    assert calls == ["models"]
    assert any("models finished with exit code 1" in line for line in lines)


def test_menu_is_a_builtin_subcommand_and_parses() -> None:
    args = _build_cli_parser().parse_args(["menu"])

    assert args.command == "menu"
