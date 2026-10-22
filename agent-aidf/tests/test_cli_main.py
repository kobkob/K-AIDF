from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from agent_aidf.cli.main import (
    DEFAULT_LOCAL_MODEL,
    _build_cli_parser,
    _run_cli,
    active_model_label,
)
from agent_aidf.shell import run_shell


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


FRONT_MATTER = (
    "---\nid: docs/doc.md\ntitle: Doc\ndocument_class: core-doc\nphase: 00-overview\n"
    "visibility: internal\nstatus: active\n---\n\n# Doc\n"
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fully_compliant_repo(root: Path) -> Path:
    _write(root / ".kaidf/README.md", FRONT_MATTER)
    _write(root / ".kaidf/docs/00-overview/kaidf.md", FRONT_MATTER)
    _write(root / ".kaidf/mentor-workflow.json", '{"phase": "01"}')
    _write(root / ".kaidf/policy/pii-masking-rules.yaml", "rules:\n  - email\n")
    _write(root / ".kaidf/policy/hitl-config.yaml", "reviewer: human\n")
    _write(
        root / ".kaidf/policy/budget.yaml",
        "max_tokens: 4096\nrequest_timeout_seconds: 30\nlocal_fallback: true\n",
    )
    _write(root / "specs/kaidf.yaml", "version: '1.0'\n")
    _write(root / "docs/20-ethical-model/risk-assessment.json", '{"risk": "low"}')
    _write(root / "docs/20-ethical-model/explicability-schema.json", '{"fields": []}')
    _write(root / "data/manifests/dataset-audit.yaml", "dataset: demo\n")
    _write(root / ".github/workflows/ci.yml", "steps:\n  - run: pytest\n")
    _write(
        root / "data/manifests/skills.yaml",
        'version: "1.0"\nskills:\n  - id: "kaidf-audit"\n    command: "kob audit"\n'
        '    permissions:\n      filesystem: "read"\n',
    )
    return root


def test_audit_parser_defaults_to_current_directory_in_text_mode() -> None:
    args = _build_cli_parser().parse_args(["audit"])

    assert args.path == "."
    assert args.json is False


def test_audit_parser_accepts_a_path_and_json_flag() -> None:
    args = _build_cli_parser().parse_args(["audit", "some/repo", "--json"])

    assert args.path == "some/repo"
    assert args.json is True


def test_kob_audit_prints_scorecard_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_cli(["audit", str(tmp_path)])

    out = capsys.readouterr().out
    assert code == 0
    assert "KAIDF-AMM v1.0 - Audit Scorecard" in out
    assert "Score: 0/100" in out
    assert "Tier: Non-Compliant / Unrated" in out
    assert "Dimensão" in out and "Status" in out and "Progresso" in out
    assert "Remediações" in out
    assert "Data Sovereignty & Perimeter" in out


def test_kob_audit_reports_no_failed_checks_for_a_compliant_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_cli(["audit", str(_fully_compliant_repo(tmp_path))])

    out = capsys.readouterr().out
    assert code == 0
    assert "Score: 100/100" in out
    assert "Tier: Platinum" in out
    assert "No failed checks." in out


def test_kob_audit_json_mode_prints_structured_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_cli(["audit", str(_fully_compliant_repo(tmp_path)), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["score"] == 100
    assert payload["max_score"] == 100
    assert payload["tier"] == "Platinum"
    assert [d["id"] for d in payload["dimensions"]] == [
        "data-sovereignty",
        "methodology-as-code",
        "regulatory-compliance",
        "deterministic-guardrails",
        "cost-infrastructure-health",
    ]
    first_check = payload["dimensions"][0]["checks"][0]
    assert set(first_check) == {"id", "title", "points", "max_points", "detail", "remediation"}


def test_kob_audit_rejects_a_missing_path_with_exit_code_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _run_cli(["audit", str(tmp_path / "missing")])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "kob audit:" in captured.err
    assert "does not exist" in captured.err


def test_repl_audit_reports_the_project_and_survives_a_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    commands = iter(["audit", f"audit {tmp_path / 'missing'}", "exit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(commands))

    run_shell(tmp_path / "repo-missing-kaidf", tmp_path)

    out = capsys.readouterr().out
    assert "KAIDF-AMM v1.0 - Audit Scorecard" in out
    assert "Score: 0/100" in out
    assert "audit: " in out and "does not exist" in out


def test_rich_scorecard_colours_the_tier_on_a_terminal(tmp_path: Path) -> None:
    import io

    from rich.console import Console

    from agent_aidf.audit import print_audit_report, run_audit

    buffer = io.StringIO()
    console = Console(file=buffer, width=100, force_terminal=True, color_system="truecolor")
    print_audit_report(run_audit(_fully_compliant_repo(tmp_path)), console)

    out = buffer.getvalue()
    assert "\x1b[" in out
    assert "KAIDF-AMM v1.0 - Audit Scorecard" in out
    assert "Pass" in out
    assert "No failed checks." in out


def test_plain_scorecard_has_no_escape_codes_and_shows_partial_progress(tmp_path: Path) -> None:
    from agent_aidf.audit import render_audit_report, run_audit

    _write(tmp_path / ".kaidf/README.md", "# kaidf\n")
    _write(tmp_path / ".kaidf/docs/index.md", "# docs\n")
    result = run_audit(tmp_path)
    text = render_audit_report(result)

    assert "\x1b" not in text
    assert "Partial" in text
    assert "█" in text and "░" in text
    scaffold = next(c for d in result.dimensions for c in d.checks if c.id == "kaidf-scaffold")
    assert scaffold.points == scaffold.max_points
