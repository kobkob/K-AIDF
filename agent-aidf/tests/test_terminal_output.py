"""Rich terminal output for `kob status` and `kob mentor`, and the plain and JSON fallbacks (#4)."""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from agent_aidf import terminal_output as out
from agent_aidf.audit import AuditResult, CheckResult, DimensionResult
from agent_aidf.cli.main import _run_cli
from agent_aidf.maturity import phase_snapshot
from agent_aidf.project import ProjectStatus

# The package attribute `agent_aidf.cli.main` is the main() function, so the module is imported
# by name to patch its globals.
CLI_MODULE = importlib.import_module("agent_aidf.cli.main")

PHASES = [
    {"order": 1, "name": "Intent & Constraints", "state": "done"},
    {"order": 2, "name": "Discovery & Mapping", "state": "current"},
    {"order": 3, "name": "Design & Simulation", "state": "pending"},
    {"order": 4, "name": "Execution & Instrumentation", "state": "pending"},
    {"order": 5, "name": "Verification & Transfer", "state": "pending"},
]
MODEL = {"provider": "ollama", "model": "olmo2:7b"}
EXTENSIONS = {"loaded": 2, "failed": 1, "disabled": 0, "total": 3}


class _Ascii:
    """A stream that reports an ASCII encoding, as a non-UTF-8 terminal does."""

    encoding = "ascii"

    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def write(self, text: str) -> int:
        return self.buffer.write(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True

    def getvalue(self) -> str:
        return self.buffer.getvalue()


def _tty(width: int = 120) -> tuple[Console, io.StringIO]:
    stream = io.StringIO()
    return Console(file=stream, force_terminal=True, width=width, color_system=None), stream


def _status(tmp_path: Path, *, packs=("maturity-model",), accepted=()) -> ProjectStatus:
    return ProjectStatus(
        project_root=tmp_path,
        repo_root=tmp_path / ".kaidf",
        has_kaidf=True,
        document_count=3,
        pack_count=len(packs),
        packs=list(packs),
        instant_app_count=0,
        instant_apps=[],
        mentor_step_count=2,
        mentor_pending_category="Intent & Constraints",
        mentor_current_app_id=None,
        mentor_current_app_url=None,
        mentor_accepted_phases=list(accepted),
    )


def _scorecard(points: int) -> AuditResult:
    check = CheckResult(
        id="c1",
        title="A check",
        points=points,
        max_points=20,
        severity="high",
        detail="",
        remediation="",
    )
    dimensions = tuple(
        DimensionResult(id=f"d{i}", name=f"Dimension {i}", max_points=20, checks=(check,))
        for i in range(5)
    )
    return AuditResult(repo_path="/x", dimensions=dimensions, scaffold_path="/x/.kaidf")


# --- pipeline ------------------------------------------------------------------------------------


def test_pipeline_marks_done_current_and_pending_phases() -> None:
    console, stream = _tty()
    console.print(out.pipeline_text(PHASES))
    text = stream.getvalue()

    assert "✔ 1. Intent & Constraints" in text
    assert "▶ 2. Discovery & Mapping" in text
    assert "3. Design & Simulation" in text
    assert text.count("❯") == 4


def test_pipeline_uses_ascii_markers_when_asked() -> None:
    text = out.pipeline_text(PHASES, ascii_only=True).plain

    assert "[x] 1. Intent & Constraints" in text
    assert "[>] 2. Discovery & Mapping" in text
    assert "❯" not in text and "▶" not in text


# --- Rich or plain -------------------------------------------------------------------------------


def test_rich_layout_needs_an_interactive_utf8_terminal(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    console, _ = _tty()
    assert out.use_rich(console)

    assert not out.use_rich(Console(file=io.StringIO()))  # a pipe or a CI log
    assert not out.use_rich(Console(file=_Ascii(), force_terminal=True))  # not UTF-8
    monkeypatch.setenv("NO_COLOR", "1")
    assert not out.use_rich(console)
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert not out.use_rich(console)


# --- status --------------------------------------------------------------------------------------


def test_status_dashboard_shows_every_section(tmp_path: Path) -> None:
    console, stream = _tty()

    out.render_status(
        console,
        _status(tmp_path, accepted=[1]),
        phases=PHASES,
        scorecard=_scorecard(10),
        extensions=EXTENSIONS,
        model=MODEL,
    )
    text = stream.getvalue()

    assert "K-AIDF status" in text
    assert "ollama · olmo2:7b" in text
    assert "2 loaded, 1 failed, 0 disabled" in text
    assert "1/5 accepted" in text
    assert "Score 50/100" in text
    for index in range(5):
        assert f"Dimension {index}" in text


def test_status_dashboard_says_when_the_scorecard_is_unavailable(tmp_path: Path) -> None:
    console, stream = _tty()

    out.render_status(
        console,
        _status(tmp_path),
        phases=PHASES,
        scorecard=None,
        extensions=EXTENSIONS,
        model=MODEL,
    )

    assert "scorecard unavailable" in stream.getvalue()


def test_plain_status_lines_keep_the_old_keys_and_add_the_new_ones(tmp_path: Path) -> None:
    lines = out.plain_status_lines(
        _status(tmp_path), phases=PHASES, extensions=EXTENSIONS, model=MODEL
    )

    assert lines[:5] == [
        f"project_root: {tmp_path}",
        f"repo_root: {tmp_path / '.kaidf'}",
        "has_kaidf: yes",
        "pack_count: 1",
        "mentor_step_count: 2",
    ]
    assert "phases_accepted: 0/5" in lines
    assert "model: ollama olmo2:7b" in lines
    assert "extensions: 2 loaded, 1 failed, 0 disabled" in lines


def test_status_json_is_complete_and_free_of_terminal_markup(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(CLI_MODULE, "run_audit", lambda _path: _scorecard(20))

    assert _run_cli(["--project", str(project), "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["phases"]["total"] == 5
    assert payload["phases"]["items"][0]["state"] in {"current", "pending", "done"}
    assert payload["scorecard"]["score"] == 100
    assert payload["scorecard"]["tier"] == "Platinum"
    assert len(payload["scorecard"]["dimensions"]) == 5
    assert set(payload["extensions"]) == {"loaded", "failed", "disabled", "total"}
    assert set(payload["model"]) == {"provider", "model"}
    assert "\x1b" not in json.dumps(payload)


def test_status_in_a_pipe_prints_plain_lines_and_no_boxes(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(CLI_MODULE, "run_audit", lambda _path: _scorecard(20))

    assert _run_cli(["--project", str(project), "status"]) == 0
    text = capsys.readouterr().out

    assert "phases_accepted: 0/5" in text
    assert "╭" not in text and "┏" not in text and "\x1b" not in text


def test_status_survives_a_project_that_cannot_be_audited(tmp_path: Path, monkeypatch) -> None:
    def _boom(_path):
        raise RuntimeError("cannot audit")

    monkeypatch.setattr(CLI_MODULE, "run_audit", _boom)

    assert (
        out.status_payload(
            _status(tmp_path), phases=PHASES, scorecard=None, extensions=EXTENSIONS, model=MODEL
        )["scorecard"]
        is None
    )


# --- mentor --------------------------------------------------------------------------------------


def test_mentor_body_drops_only_the_question_lines() -> None:
    message = "\n".join(
        [
            "Mentor workflow is active.",
            "Question: What is the goal?",
            "",
            "Next question: What is the goal?",
            "Next focus: Intent",
        ]
    )

    body = out.mentor_body(message, "What is the goal?")

    assert body == "Mentor workflow is active.\n\nNext focus: Intent"


def test_mentor_tags_show_maturity_and_ethics(tmp_path: Path) -> None:
    gold = out.mentor_tags(_scorecard(15), _status(tmp_path, packs=("ethical-model",))).plain
    bare = out.mentor_tags(None, _status(tmp_path)).plain

    assert "Maturity 75/100" in gold
    assert "Ethics: ethical-model pack" in gold
    assert "Maturity: unscored" in bare
    assert "Ethics: no ethical-model pack" in bare


def test_mentor_panel_shows_the_question_in_a_box(tmp_path: Path) -> None:
    console, stream = _tty()

    out.render_mentor_turn(
        console,
        message="Mentor workflow is active.\nQuestion: What is the goal?",
        pending_question="What is the goal?",
        pending_category="Intent & Constraints",
        phase_order=1,
        scorecard=None,
        status=_status(tmp_path),
    )
    text = stream.getvalue()

    assert "Mentor · phase 1/5 · Intent & Constraints" in text
    assert "What is the goal?" in text
    assert text.count("What is the goal?") == 1
    assert "Mentor workflow is active." in text


def test_mentor_in_a_pipe_prints_the_message_unchanged(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(CLI_MODULE, "run_audit", lambda _path: _scorecard(20))
    (project / ".kaidf").mkdir()

    assert _run_cli(["--project", str(project), "mentor"]) == 0
    text = capsys.readouterr().out

    assert "Question:" in text
    assert "╭" not in text


# --- helpers -------------------------------------------------------------------------------------


def test_extension_summary_counts_states() -> None:
    inventory = {
        "extensions": [
            {"state": "loaded"},
            {"state": "loaded"},
            {"state": "failed"},
            {"state": "disabled"},
        ]
    }

    assert out.extension_summary(inventory) == {"loaded": 2, "failed": 1, "disabled": 1, "total": 4}


@pytest.mark.parametrize(
    ("provider", "env", "expected_model"),
    [
        ("openai", {"OPENAI_MODEL": "gpt-test"}, "gpt-test"),
        ("none", {}, "-"),
    ],
)
def test_active_model_follows_the_provider(monkeypatch, provider, env, expected_model) -> None:
    monkeypatch.setenv("AIDF_CHAT_PROVIDER", provider)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert out.active_model()["model"] == expected_model


def test_phase_snapshot_feeds_the_pipeline(tmp_path: Path) -> None:
    status = _status(tmp_path, accepted=[1])
    states = [phase["state"] for phase in phase_snapshot(status)]

    assert states[0] == "done"
    assert states[1] == "current"
