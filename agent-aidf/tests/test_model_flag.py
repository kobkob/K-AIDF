from __future__ import annotations

import importlib

import pytest

from agent_aidf.cli.main import _build_cli_parser, _run_cli, active_model_label
from agent_aidf.controller import (
    DEFAULT_OLLAMA_MODEL,
    OllamaChatController,
    apply_model_override,
    build_controller,
    resolve_local_model,
)

MODEL_ENV_VARS = ("AIDF_MODEL", "AIDF_OLLAMA_MODEL", "OLLAMA_MODEL", "OPENAI_MODEL")
# `agent_aidf.cli` re-exports a function named `main`, which shadows the submodule on attribute
# access, so the module is fetched by name.
cli_main = importlib.import_module("agent_aidf.cli.main")


@pytest.fixture(autouse=True)
def clean_model_env(monkeypatch):
    # Without this, a developer's shell or .env could change what these tests resolve.
    for name in (*MODEL_ENV_VARS, "AIDF_CHAT_PROVIDER", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


# --- resolution precedence (environment, no flag) ---------------------------


def test_default_local_model_is_the_standard_olmo_tag() -> None:
    assert DEFAULT_OLLAMA_MODEL == "olmo2:7b-1124-instruct-q4_K_M"
    assert resolve_local_model() == DEFAULT_OLLAMA_MODEL


@pytest.mark.parametrize(
    ("set_vars", "expected"),
    [
        ({"OLLAMA_MODEL": "from-ollama"}, "from-ollama"),
        ({"AIDF_OLLAMA_MODEL": "from-aidf-ollama", "OLLAMA_MODEL": "x"}, "from-aidf-ollama"),
        (
            {"AIDF_MODEL": "from-aidf", "AIDF_OLLAMA_MODEL": "y", "OLLAMA_MODEL": "z"},
            "from-aidf",
        ),
    ],
)
def test_env_vars_resolve_in_documented_order(monkeypatch, set_vars, expected) -> None:
    for name, value in set_vars.items():
        monkeypatch.setenv(name, value)

    assert resolve_local_model() == expected
    assert build_controller().model == expected


def test_blank_env_var_falls_through_to_next_source(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_MODEL", "   ")
    monkeypatch.setenv("OLLAMA_MODEL", "from-ollama")

    assert resolve_local_model() == "from-ollama"


def test_build_controller_without_env_uses_default(monkeypatch) -> None:
    controller = build_controller()

    assert isinstance(controller, OllamaChatController)
    assert controller.model == DEFAULT_OLLAMA_MODEL


# --- --model parsing --------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--model", "qwen2.5:0.5b", "mentor"],
        ["mentor", "--model", "qwen2.5:0.5b"],
        ["shell", "--model", "qwen2.5:0.5b"],
        ["ui", "--model", "qwen2.5:0.5b"],
        ["serve", "--model", "qwen2.5:0.5b"],
    ],
)
def test_model_flag_parses_at_top_level_and_on_llm_subcommands(argv) -> None:
    args = _build_cli_parser().parse_args(argv)

    assert args.model == "qwen2.5:0.5b"


def test_subcommand_does_not_reset_top_level_model() -> None:
    # Regression guard: a subparser default of None would overwrite `--model` given before it.
    args = _build_cli_parser().parse_args(["--model", "qwen2.5:0.5b", "mentor"])

    assert args.model == "qwen2.5:0.5b"


def test_model_flag_is_absent_by_default() -> None:
    args = _build_cli_parser().parse_args(["mentor"])

    assert args.model is None


def test_model_flag_strips_whitespace() -> None:
    args = _build_cli_parser().parse_args(["mentor", "--model", "  qwen2.5:0.5b  "])

    assert args.model == "qwen2.5:0.5b"


def test_empty_model_flag_is_rejected(capsys) -> None:
    with pytest.raises(SystemExit):
        _build_cli_parser().parse_args(["mentor", "--model", "   "])

    assert "empty value" in capsys.readouterr().err


# --- flag precedence over the environment -----------------------------------


def test_apply_override_beats_every_env_var(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_MODEL", "from-aidf")
    monkeypatch.setenv("AIDF_OLLAMA_MODEL", "from-aidf-ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "from-ollama")

    apply_model_override("qwen2.5:0.5b")

    assert resolve_local_model() == "qwen2.5:0.5b"
    assert build_controller().model == "qwen2.5:0.5b"
    assert active_model_label() == "qwen2.5:0.5b"


def test_apply_override_beats_the_default(monkeypatch) -> None:
    apply_model_override("qwen2.5:0.5b")

    assert build_controller().model == "qwen2.5:0.5b"


def test_apply_override_targets_openai_model_when_openai_is_selected(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AIDF_MODEL", "untouched")

    apply_model_override("gpt-5-mini")

    assert build_controller().model == "gpt-5-mini"
    assert active_model_label() == "gpt-5-mini"
    assert build_controller().model != "untouched"


# --- dispatch: the flag is applied before any command runs -------------------


@pytest.fixture
def captured_shell(monkeypatch, tmp_path):
    seen: list[str] = []

    def fake_shell(repo_root, project_root) -> int:
        seen.append(build_controller().model)
        return 0

    monkeypatch.setattr(cli_main, "resolve_project_root", lambda _project: tmp_path)
    monkeypatch.setattr(cli_main, "resolve_runtime_repo_root", lambda _project, _repo: tmp_path)
    monkeypatch.setattr(cli_main, "run_shell", fake_shell)
    # Seeded then deleted so monkeypatch restores the variable after the test.
    monkeypatch.setenv("AIDF_MODEL", "seed")
    monkeypatch.delenv("AIDF_MODEL")
    return seen


def test_shell_receives_the_flag_model(captured_shell) -> None:
    assert _run_cli(["shell", "--model", "qwen2.5:0.5b"]) == 0
    assert captured_shell == ["qwen2.5:0.5b"]


def test_top_level_flag_reaches_subcommand(captured_shell) -> None:
    assert _run_cli(["--model", "qwen2.5:0.5b", "shell"]) == 0
    assert captured_shell == ["qwen2.5:0.5b"]


def test_no_flag_keeps_environment_resolution(monkeypatch, captured_shell) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "from-ollama")

    assert _run_cli(["shell"]) == 0
    assert captured_shell == ["from-ollama"]


def test_flag_without_subcommand_launches_tui_with_model(monkeypatch) -> None:
    launched: list[str] = []

    class FakeApp:
        def __init__(self, yolo: bool) -> None:
            self.yolo = yolo

        def run(self) -> None:
            launched.append(active_model_label())

    monkeypatch.setattr(cli_main, "KobAgentApp", FakeApp)

    assert _run_cli(["--model", "qwen2.5:0.5b"]) == 0
    assert launched == ["qwen2.5:0.5b"]
