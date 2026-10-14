from __future__ import annotations

from agent_aidf.cli.main import DEFAULT_LOCAL_MODEL, active_model_label


def test_active_model_label_defaults_to_friendly_local_name(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AIDF_MODEL", raising=False)

    assert active_model_label() == DEFAULT_LOCAL_MODEL == "OLMo 3.1 local"


def test_active_model_label_ignores_ambient_openai_key(monkeypatch) -> None:
    # Regression: an OPENAI_API_KEY left set in the shell must not make the
    # TUI header show "gpt-5" unless AIDF_CHAT_PROVIDER=openai was chosen.
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient-leftover-key")
    monkeypatch.delenv("AIDF_MODEL", raising=False)

    assert active_model_label() == "OLMo 3.1 local"


def test_active_model_label_reflects_configured_local_model(monkeypatch) -> None:
    monkeypatch.delenv("AIDF_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AIDF_MODEL", "olmo2:13b-1124-instruct-q4_K_M")

    assert active_model_label() == "olmo2:13b-1124-instruct-q4_K_M"


def test_active_model_label_reflects_explicit_openai_provider(monkeypatch) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")

    assert active_model_label() == "gpt-5"


def test_gen_resolves_relative_out_and_spec_against_caller_cwd(monkeypatch, tmp_path) -> None:
    # Regression: the generator subprocess runs with cwd=generator_repo, so relative
    # --out/--spec must be made absolute in the caller's cwd first, or the output
    # lands inside the generator checkout instead of the user's project.
    import importlib
    import sys
    from pathlib import Path

    # Import the module explicitly: `agent_aidf.cli` re-exports a `main` function that shadows it.
    cli_main = importlib.import_module("agent_aidf.cli.main")

    generator_repo = tmp_path / "kobkob-kaidf-generator"
    generator_repo.mkdir()
    project = tmp_path / "user-project"
    project.mkdir()
    (project / "spec_relative.yaml").write_text("name: demo\n", encoding="utf-8")

    monkeypatch.setattr(cli_main, "locate_generator_repo", lambda: generator_repo)
    monkeypatch.setattr(cli_main, "resolve_generator_python", lambda repo: Path(sys.executable))
    monkeypatch.chdir(project)

    calls = []

    def fake_generator(command, cwd, check):
        # Emulate the generator: relative paths are interpreted against the subprocess cwd.
        calls.append((command, cwd, check))
        spec_arg = Path(cwd) / command[command.index("generate") + 1]
        out_arg = Path(cwd) / command[command.index("--out") + 1]
        assert spec_arg.read_text(encoding="utf-8") == "name: demo\n"
        out_arg.mkdir(parents=True, exist_ok=True)
        (out_arg / "generated.txt").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(cli_main.subprocess, "run", fake_generator)

    cli_main._run_compile_backend("./spec_relative.yaml", "./out_relative", force=False)

    assert len(calls) == 1
    command, cwd, check = calls[0]
    assert cwd == generator_repo
    assert check is True
    spec_arg = Path(command[command.index("generate") + 1])
    assert spec_arg == (project / "spec_relative.yaml").resolve()
    assert Path(command[command.index("--out") + 1]) == (project / "out_relative").resolve()
    assert (project / "out_relative" / "generated.txt").is_file()
    assert not (generator_repo / "out_relative").exists()
