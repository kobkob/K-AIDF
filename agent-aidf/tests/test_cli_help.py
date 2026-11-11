from __future__ import annotations

import pytest

from agent_aidf.cli.help import COMMAND_DOCS, command_overview
from agent_aidf.cli.main import _build_cli_parser, _run_cli
from agent_aidf.extensions.extension_loader import BUILTIN_COMMANDS

DOCUMENTED = (
    "init",
    "status",
    "audit",
    "mentor",
    "ui",
    "serve",
    "compile",
    "gen",
    "ext",
    "ext list",
    "appliance",
    "appliance init",
    "appliance template",
    "help",
)


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    try:
        code = _run_cli(argv)
    except SystemExit as exc:  # argparse exits for -h and usage errors
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


def test_every_documented_command_has_a_description_and_examples() -> None:
    for name in DOCUMENTED:
        doc = COMMAND_DOCS[name]
        assert doc.description.strip(), name
        assert doc.examples, name
        for example in doc.examples:
            assert "kob" in example.command.split(), (name, example.command)


@pytest.mark.parametrize("name", DOCUMENTED)
def test_subcommand_help_prints_description_and_examples(name: str, capsys) -> None:
    code, out, _ = _run([*name.split(), "-h"], capsys)

    assert code == 0
    assert "examples:" in out
    assert COMMAND_DOCS[name].examples[0].command in out


def test_audit_help_explains_each_gate_flag(capsys) -> None:
    _, out, _ = _run(["audit", "-h"], capsys)

    for flag in ("--severity", "--fail-under", "--fail-on-critical", "--json"):
        assert flag in out
    assert "critical, high, medium or low" in out


def test_ext_help_documents_the_install_flag(capsys) -> None:
    _, out, _ = _run(["ext", "-h"], capsys)

    assert "kob -x SOURCE" in out
    assert "kob ext list" in out


def test_kob_help_without_arguments_lists_every_builtin_command(capsys) -> None:
    code, out, _ = _run(["help"], capsys)

    assert code == 0
    for name in BUILTIN_COMMANDS:
        assert f"  {name} " in out, name
    assert "kob help <command>" in out


def test_kob_help_overview_gives_one_line_per_command() -> None:
    text = command_overview(_build_cli_parser())

    audit_line = next(line for line in text.splitlines() if line.strip().startswith("audit "))
    assert "KAIDF-AMM" in audit_line


def test_kob_help_command_prints_the_same_page_as_dash_h(capsys) -> None:
    _, via_dash_h, _ = _run(["audit", "-h"], capsys)
    code, via_help, _ = _run(["help", "audit"], capsys)

    assert code == 0
    assert via_help == via_dash_h


def test_kob_help_nested_command_resolves_each_word(capsys) -> None:
    _, via_dash_h, _ = _run(["ext", "list", "-h"], capsys)
    code, via_help, _ = _run(["help", "ext", "list"], capsys)

    assert code == 0
    assert via_help == via_dash_h


def test_kob_help_unknown_command_fails_with_suggestion(capsys) -> None:
    code, out, err = _run(["help", "audt"], capsys)

    assert code == 2
    assert out == ""
    assert "unknown command 'audt'" in err
    assert "Did you mean 'audit'?" in err
    assert "Available:" in err


def test_kob_help_unknown_nested_command_names_its_parent(capsys) -> None:
    code, _, err = _run(["help", "ext", "lst"], capsys)

    assert code == 2
    assert "unknown command 'lst' for 'kob ext'" in err
    assert "Did you mean 'list'?" in err


def test_kob_help_on_command_without_subcommands_is_an_error(capsys) -> None:
    code, _, err = _run(["help", "status", "extra"], capsys)

    assert code == 2
    assert "It takes no subcommands." in err


def test_help_is_reserved_so_extensions_cannot_shadow_it() -> None:
    assert "help" in BUILTIN_COMMANDS
