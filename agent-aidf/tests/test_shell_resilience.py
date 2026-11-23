from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from agent_aidf.shell import run_shell

cli_main = importlib.import_module("agent_aidf.cli.main")


@pytest.fixture
def scripted(monkeypatch):
    """Feed the REPL a script of input() results and record each command it hands to kob."""
    commands: list[list[str]] = []
    lines: list[object] = []

    def fake_input(_prompt: str = "") -> str:
        if not lines:
            raise AssertionError("the REPL asked for more input than the script provided")
        item = lines.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def fake_cli(argv: list[str]) -> int:
        commands.append(argv)
        return 0

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli_main, "_run_cli", fake_cli)

    def run(*script: object) -> list[list[str]]:
        lines.extend(script)
        assert run_shell(Path("/tmp/unused-repo")) == 0
        return commands

    return run


def _last_scope_free(argv: list[str]) -> list[str]:
    return [arg for arg in argv if arg not in {"--repo", "/tmp/unused-repo"}]


def test_apostrophe_in_chat_text_is_sent_whole(scripted) -> None:
    commands = scripted("chat what's the next step", "quit")

    assert _last_scope_free(commands[0]) == ["chat", "what's the next step"]


def test_apostrophe_in_find_text_is_sent_whole(scripted) -> None:
    commands = scripted("find don't panic", "quit")

    assert _last_scope_free(commands[0]) == ["find", "don't panic"]


def test_properly_quoted_arguments_still_split(scripted) -> None:
    commands = scripted('find "two words"', "quit")

    assert _last_scope_free(commands[0]) == ["find", "two words"]


def test_unclosed_quote_in_other_commands_is_reported_and_the_session_continues(
    scripted, capsys
) -> None:
    commands = scripted('docs --phase "oops', "quit")

    assert commands == []
    assert "quote is not closed" in capsys.readouterr().out


def test_ctrl_c_at_the_prompt_cancels_the_line_and_keeps_the_session(scripted) -> None:
    commands = scripted(KeyboardInterrupt(), "docs", "quit")

    assert _last_scope_free(commands[0]) == ["docs"]


def test_ctrl_c_during_a_command_stops_it_without_ending_the_session(
    scripted, monkeypatch, capsys
) -> None:
    calls: list[list[str]] = []

    def interrupted_once(argv: list[str]) -> int:
        calls.append(argv)
        if len(calls) == 1:
            raise KeyboardInterrupt
        return 0

    monkeypatch.setattr(cli_main, "_run_cli", interrupted_once)

    scripted("chat hello", "quit")

    assert len(calls) == 1
    assert "interrupted" in capsys.readouterr().out


def test_end_of_input_still_leaves_the_shell(scripted) -> None:
    commands = scripted("docs", EOFError())

    assert len(commands) == 1
