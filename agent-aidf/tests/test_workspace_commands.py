"""Workspace commands are root `kob` subcommands, and `kob shell` is a deprecated front for them."""

from __future__ import annotations

import builtins
import importlib
from pathlib import Path

import pytest

from agent_aidf.extensions.extension_loader import BUILTIN_COMMANDS
from agent_aidf.shell import SHELL_DEPRECATION, run_shell
from agent_aidf.workspace_commands import WORKSPACE_COMMANDS

cli_main = importlib.import_module("agent_aidf.cli.main")


def test_every_workspace_command_is_a_builtin_root_subcommand():
    assert WORKSPACE_COMMANDS <= BUILTIN_COMMANDS
    parser = cli_main._build_cli_parser()
    subparsers = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    assert WORKSPACE_COMMANDS <= set(subparsers.choices)


@pytest.mark.parametrize(
    "argv",
    [
        ["packs"],
        ["docs", "--pack", "core"],
        ["find", "governance"],
        ["open", "README.md"],
        ["chat", "hello"],
        ["apps"],
        ["app-create", "demo", "--mode", "ephemeral", "--kind", "web"],
        ["app-open", "demo"],
        ["app-run", "demo", "--port", "8123"],
        ["app-runtime", "demo"],
        ["app-stop", "demo"],
        ["contracts"],
        ["contract-create", "c1", "--brief", "x", "--force"],
        ["contract-open", "c1"],
    ],
)
def test_root_cli_parses_each_workspace_command(argv):
    args = cli_main._build_cli_parser().parse_args(argv)

    assert args.command == argv[0]


def test_root_cli_routes_workspace_commands_to_the_dispatcher(tmp_path: Path, monkeypatch):
    routed: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        cli_main,
        "resolve_runtime_repo_root",
        lambda _project, _repo: tmp_path,
    )
    monkeypatch.setattr(
        cli_main,
        "dispatch_workspace_command",
        lambda args, repo_root: routed.append((args.command, repo_root)) or 0,
    )

    assert cli_main._run_cli(["--project", str(tmp_path), "apps"]) == 0
    assert routed == [("apps", tmp_path)]


def test_kob_help_documents_a_workspace_command(capsys):
    assert cli_main._run_cli(["help", "apps"]) == 0

    assert "apps" in capsys.readouterr().out


def test_shell_prints_the_deprecation_banner_with_the_removal_version(
    monkeypatch, tmp_path: Path, capsys
):
    monkeypatch.setattr(builtins, "input", lambda prompt="": "quit")

    assert run_shell(tmp_path, tmp_path) == 0

    out = capsys.readouterr().out
    assert SHELL_DEPRECATION in out
    assert "v0.8.0" in SHELL_DEPRECATION
    assert "deprecated" in out


def test_shell_delegates_each_line_to_the_root_cli_in_the_shell_project(
    monkeypatch, tmp_path: Path
):
    calls: list[list[str]] = []
    monkeypatch.setattr(cli_main, "_run_cli", lambda argv: calls.append(argv) or 0)
    lines = iter(["packs", "docs --pack core", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))

    run_shell(tmp_path / "repo", tmp_path / "project")

    assert calls == [
        ["--project", str(tmp_path / "project"), "--repo", str(tmp_path / "repo"), "packs"],
        [
            "--project",
            str(tmp_path / "project"),
            "--repo",
            str(tmp_path / "repo"),
            "docs",
            "--pack",
            "core",
        ],
    ]


def test_shell_maps_the_old_mentor_spellings_onto_flags(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []
    monkeypatch.setattr(cli_main, "_run_cli", lambda argv: calls.append(argv) or 0)
    lines = iter(["mentor-status", "mentor-reset", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))

    run_shell(tmp_path, tmp_path)

    assert calls[0][-2:] == ["mentor", "--status"]
    assert calls[1][-2:] == ["mentor", "--reset"]


def test_shell_refuses_to_nest_itself(monkeypatch, tmp_path: Path, capsys):
    calls: list[list[str]] = []
    monkeypatch.setattr(cli_main, "_run_cli", lambda argv: calls.append(argv) or 0)
    lines = iter(["shell", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))

    run_shell(tmp_path, tmp_path)

    assert calls == []
    assert "already inside kob shell" in capsys.readouterr().out


def test_shell_survives_a_command_that_raises(monkeypatch, tmp_path: Path, capsys):
    def boom(_argv):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli_main, "_run_cli", boom)
    lines = iter(["apps", "quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(lines))

    assert run_shell(tmp_path, tmp_path) == 0
    assert "error: kaboom" in capsys.readouterr().out
