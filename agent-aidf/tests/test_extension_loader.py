from __future__ import annotations

import argparse
import importlib
import logging
from pathlib import Path

import pytest

from agent_aidf import prompt_hooks
from agent_aidf.extensions.extension_loader import (
    BUILTIN_EXTENSIONS_DIR,
    active_registry,
    load_extensions,
    reset_active_registry,
    user_extensions_dir,
)
from agent_aidf.prompt_hooks import intercept_prompt

# See test_model_flag.py: `agent_aidf.cli` re-exports a function named `main`.
cli_main = importlib.import_module("agent_aidf.cli.main")

HEADER = """\
# Extension: {name}
# Description: test extension
# Version: 0.1.0
# Author: Tests
# Entrypoints: cli, prompt
# Topics: testing
"""


def source(name: str, body: str = "") -> str:
    return HEADER.format(name=name) + body


FULL_EXTENSION = source(
    "Demo",
    """
def register(hooks):
    def add(parser):
        parser.add_argument("--demo-flag", default=None)

    def run(args):
        if getattr(args, "demo_flag", None):
            print("demo-flag:" + args.demo_flag)
            return 7
        return None

    def configure(sub):
        sub.add_argument("--loud", action="store_true")

    def run_hello(args):
        return 3

    hooks.add_cli_arguments(add)
    hooks.add_cli_handler(run)
    hooks.add_subcommand("hello", "Say hello", configure, run_hello)
    hooks.add_prompt_interceptor(lambda prompt: "INTERCEPTED" if "ping" in prompt else None)
""",
)


def _write_extension(root: Path, folder: str, main_source: str) -> Path:
    directory = root / folder
    directory.mkdir(parents=True)
    (directory / "main.py").write_text(main_source, encoding="utf-8")
    return directory


@pytest.fixture
def roots(tmp_path: Path) -> list[Path]:
    root = tmp_path / "extensions"
    root.mkdir()
    return [root]


def test_default_roots_are_builtin_and_user_dirs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(tmp_path / "mine"))

    assert user_extensions_dir() == tmp_path / "mine"
    assert (BUILTIN_EXTENSIONS_DIR / "ext" / "main.py").is_file()
    assert (BUILTIN_EXTENSIONS_DIR / "words" / "main.py").is_file()


def test_loads_builtin_extensions_by_default() -> None:
    registry = load_extensions(roots=[BUILTIN_EXTENSIONS_DIR], disabled=[])

    assert {ext.id for ext in registry.loaded} == {"ext", "words"}


def test_cli_flag_and_subcommand_are_added_to_the_parser(roots: list[Path]) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    registry = load_extensions(roots=roots, disabled=[])
    parser = argparse.ArgumentParser(prog="kob")
    subparsers = parser.add_subparsers(dest="command")

    registry.configure_parser(parser, subparsers)

    args = parser.parse_args(["--demo-flag", "x", "hello", "--loud"])
    assert args.demo_flag == "x"
    assert args.command == "hello"
    assert args.loud is True


def test_dispatch_runs_handlers_and_gates_subcommands(roots: list[Path]) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    registry = load_extensions(roots=roots, disabled=[])
    parser = argparse.ArgumentParser(prog="kob")
    subparsers = parser.add_subparsers(dest="command")
    registry.configure_parser(parser, subparsers)

    flag_args = parser.parse_args(["--demo-flag", "abc"])
    assert registry.dispatch(flag_args) == 7

    hello_args = parser.parse_args(["hello"])
    assert registry.dispatch(hello_args) == 3

    plain_args = parser.parse_args([])
    assert registry.dispatch(plain_args) is None


def test_cli_extension_flag_reaches_the_real_parser(roots: list[Path], monkeypatch) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(roots[0]))
    reset_active_registry()

    args = cli_main._build_cli_parser().parse_args(["--demo-flag", "live", "status"])

    assert args.demo_flag == "live"
    assert args.command == "status"


def test_extension_subcommand_is_dispatched_through_run_cli(roots, monkeypatch, capsys) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(roots[0]))
    reset_active_registry()

    assert cli_main._run_cli(["--demo-flag", "shout"]) == 7
    assert "demo-flag:shout" in capsys.readouterr().out


def test_prompt_interceptor_is_registered_and_answers(roots: list[Path]) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)

    load_extensions(roots=roots, disabled=[])

    assert intercept_prompt("please ping") == "INTERCEPTED"
    assert intercept_prompt("hello there") is None


def test_broken_extension_is_skipped_and_logged(roots, caplog) -> None:
    _write_extension(roots[0], "broken", source("Broken", "def register(hooks)\n    pass\n"))
    _write_extension(roots[0], "fine", FULL_EXTENSION)

    with caplog.at_level(logging.WARNING):
        registry = load_extensions(roots=roots, disabled=[])

    assert [ext.id for ext in registry.loaded] == ["fine"]
    assert "skipping extension 'broken'" in caplog.text


def test_extension_without_register_is_skipped(roots, caplog) -> None:
    _write_extension(roots[0], "noreg", source("Noreg", "X = 1\n"))

    with caplog.at_level(logging.WARNING):
        registry = load_extensions(roots=roots, disabled=[])

    assert registry.loaded == []
    assert "no register(hooks)" in caplog.text


def test_failing_register_keeps_no_partial_registrations(roots) -> None:
    body = source(
        "Half",
        """
def register(hooks):
    hooks.add_prompt_interceptor(lambda prompt: "HALF-DONE")
    raise RuntimeError("boom")
""",
    )
    _write_extension(roots[0], "half", body)

    registry = load_extensions(roots=roots, disabled=[])

    assert registry.loaded == []
    assert intercept_prompt("anything") is None


def test_interceptor_exception_does_not_break_chat(roots, caplog) -> None:
    body = source(
        "Noisy",
        """
def register(hooks):
    def explode(prompt):
        raise ValueError("bad catalog")
    hooks.add_prompt_interceptor(explode)
""",
    )
    _write_extension(roots[0], "noisy", body)
    load_extensions(roots=roots, disabled=[])

    with caplog.at_level(logging.WARNING):
        assert intercept_prompt("hi") is None

    assert "bad catalog" in caplog.text


def test_shadowed_user_extension_is_skipped(tmp_path: Path, caplog) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_extension(first, "demo", FULL_EXTENSION)
    _write_extension(second, "demo", FULL_EXTENSION)

    with caplog.at_level(logging.WARNING):
        registry = load_extensions(roots=[first, second], disabled=[])

    assert [ext.id for ext in registry.loaded] == ["demo"]
    assert "shadows" in caplog.text


def test_disabled_extensions_are_not_loaded(roots, monkeypatch) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    monkeypatch.setenv("KOB_DISABLE_EXTENSIONS", "Demo, words")

    registry = load_extensions(roots=roots)

    assert registry.loaded == []
    assert intercept_prompt("please ping") is None


def test_hidden_staging_directories_are_ignored(roots) -> None:
    _write_extension(roots[0], ".staging-abc", FULL_EXTENSION)

    assert load_extensions(roots=roots, disabled=[]).loaded == []


def test_missing_root_is_not_an_error(tmp_path: Path) -> None:
    assert load_extensions(roots=[tmp_path / "absent"], disabled=[]).loaded == []


def test_active_registry_loads_once_and_reset_clears_interceptors(roots, monkeypatch) -> None:
    _write_extension(roots[0], "demo", FULL_EXTENSION)
    monkeypatch.setenv("KOB_EXTENSIONS_DIR", str(roots[0]))
    reset_active_registry()

    first = active_registry()
    assert active_registry() is first
    assert intercept_prompt("ping") == "INTERCEPTED"

    reset_active_registry()

    assert intercept_prompt("ping") is None
    assert prompt_hooks._interceptors == []
