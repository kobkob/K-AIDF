from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from agent_aidf.cli.main import _run_cli

cli_main = importlib.import_module("agent_aidf.cli.main")


class _RecordingApp:
    instances: list[_RecordingApp] = []

    def __init__(self, project_dir=None, repo_override=None, yolo=False) -> None:
        self.project_dir = project_dir
        self.repo_override = repo_override
        self.yolo = yolo
        self.ran = False
        _RecordingApp.instances.append(self)

    def run(self) -> None:
        self.ran = True


@pytest.fixture
def recording_app(monkeypatch) -> type[_RecordingApp]:
    _RecordingApp.instances = []
    monkeypatch.setattr(cli_main, "KobAgentApp", _RecordingApp)
    monkeypatch.delenv("KOB_YOLO", raising=False)
    return _RecordingApp


def test_global_project_and_repo_flags_reach_the_tui(
    recording_app, tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    repo = tmp_path / "srv-kaidf"
    repo.mkdir()
    monkeypatch.chdir(tmp_path)

    assert _run_cli(["--project", str(project), "--repo", str(repo)]) == 0

    (app,) = recording_app.instances
    assert app.project_dir == str(project)
    assert app.repo_override == str(repo)
    assert app.ran


def test_tui_without_global_flags_keeps_the_current_directory_default(
    recording_app, monkeypatch
) -> None:
    assert _run_cli([]) == 0

    (app,) = recording_app.instances
    assert app.project_dir is None
    assert app.repo_override is None


def test_missing_project_directory_is_reported_without_launching_the_tui(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli_main, "KobAgentApp", _failing_app)
    missing = tmp_path / "does-not-exist"

    assert _run_cli(["--project", str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().out


def _failing_app(**kwargs):
    raise ValueError(f"Project root does not exist or is not a directory: {kwargs['project_dir']}")
