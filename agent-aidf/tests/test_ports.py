from __future__ import annotations

import argparse
import builtins
import importlib
from pathlib import Path

import pytest

from agent_aidf import legacy_cli
from agent_aidf.ports import parse_tcp_port, tcp_port_argument
from agent_aidf.shell import run_shell

# `agent_aidf.cli` re-exports a `main` function that shadows the module.
cli_main = importlib.import_module("agent_aidf.cli.main")


@pytest.mark.parametrize("value", [1, 80, 8501, 65535, "1", " 8080 ", "65535"])
def test_parse_tcp_port_accepts_values_in_range(value: object) -> None:
    assert parse_tcp_port(value) == int(str(value).strip())


@pytest.mark.parametrize("value", [0, -1, 65536, 70000, "abc", "", "80.5", "0x50", None, True])
def test_parse_tcp_port_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError, match="Port must"):
        parse_tcp_port(value)


def test_tcp_port_argument_reports_usage_error_for_out_of_range_port() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="between 1 and 65535, got 70000"):
        tcp_port_argument("70000")


def test_ui_command_rejects_out_of_range_port_with_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = cli_main._build_cli_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["ui", "--port", "0"])

    assert excinfo.value.code == 2
    assert "argument --port: Port must be between 1 and 65535, got 0." in capsys.readouterr().err


def test_ui_command_accepts_valid_port() -> None:
    args = cli_main._build_cli_parser().parse_args(["ui", "--port", "8080"])

    assert args.port == 8080


def test_app_run_rejects_non_numeric_port_with_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = legacy_cli.build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["app-run", "demo", "--port", "abc"])

    assert excinfo.value.code == 2
    assert "Port must be a whole number" in capsys.readouterr().err


def test_invalid_ui_port_environment_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AIDF_UI_PORT", "70000")

    assert cli_main.ui_port() == cli_main.DEFAULT_UI_PORT
    assert "Ignoring AIDF_UI_PORT" in capsys.readouterr().err


def test_valid_ui_port_environment_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIDF_UI_PORT", "9123")

    assert cli_main.ui_port() == 9123


def _run_repl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, commands: list[str]) -> None:
    pending = iter([*commands, "exit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(pending))
    run_shell(tmp_path, tmp_path)


@pytest.mark.parametrize("bad_port", ["abc", "0", "-1", "70000"])
def test_repl_app_run_survives_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    bad_port: str,
) -> None:
    _run_repl(monkeypatch, tmp_path, [f"app-run demo --port {bad_port}"])

    out = capsys.readouterr().out
    assert "app-run: Port must" in out


def test_repl_app_run_reports_unknown_app_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run_repl(monkeypatch, tmp_path, ["app-run missing-app --port 8080"])

    assert "app-run: Instant app not found: missing-app" in capsys.readouterr().out
