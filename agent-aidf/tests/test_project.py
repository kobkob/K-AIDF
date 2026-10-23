from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_aidf import project as project_module
from agent_aidf.instant_apps import create_instant_app
from agent_aidf.project import init_project_repo, read_project_status, resolve_runtime_repo_root


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_project(project: Path) -> Path:
    repo = project / ".kaidf"
    _write(repo / "README.md", "# Demo\n")
    _write(
        repo / "docs/20-ethical-model/principles/transparency.md",
        "---\n"
        "id: docs/20-ethical-model/principles/transparency.md\n"
        "title: Transparency\n"
        "document_class: core-doc\n"
        "phase: 20-ethical-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: ethical-model\n"
        "ethical_domain: transparency\n"
        "---\n\n"
        "# Transparency\n",
    )
    return repo


def test_resolve_runtime_repo_root_prefers_local_dot_kaidf(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    repo = _build_project(project)
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setenv("AIDF_REPO_ROOT", str(external))

    resolved = resolve_runtime_repo_root(project)

    assert resolved == repo.resolve()


def test_read_project_status_reports_pack_counts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    repo = _build_project(project)
    create_instant_app(repo, app_id="mentor-shell", mode="persistent", kind="shell")

    status = read_project_status(project, repo)

    assert status.has_kaidf is True
    assert status.document_count == 2
    assert status.pack_count == 1
    assert status.packs == ["ethical-model"]
    assert status.instant_app_count == 1
    assert status.instant_apps == ["mentor-shell"]
    assert status.mentor_step_count == 0
    assert status.mentor_pending_category is None
    assert status.mentor_current_app_id is None
    assert status.mentor_current_app_url is None


def test_init_project_repo_uses_generator_output(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    generator_repo = tmp_path / "generator"
    (generator_repo / "specs").mkdir(parents=True)
    (generator_repo / "specs/kaidf.default.yaml").write_text(
        "repo:\n  name: demo\n", encoding="utf-8"
    )

    monkeypatch.setattr("agent_aidf.project.locate_generator_repo", lambda: generator_repo)

    def _fake_run(command, **kwargs):
        out_dir = Path(command[command.index("--out") + 1])
        generated = out_dir / "demo"
        generated.mkdir()
        (generated / "README.md").write_text("# Demo\n", encoding="utf-8")
        return None

    monkeypatch.setattr("subprocess.run", _fake_run)

    repo_root = init_project_repo(project)

    assert repo_root == project / ".kaidf"
    assert (project / ".kaidf" / "README.md").is_file()


def _generator_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "kobkob-kaidf-generator"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/bootstrap.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / ".venv/bin").mkdir(parents=True)
    (repo / ".venv/bin/python").write_text("", encoding="utf-8")
    return repo


def _bootstrap_fails(monkeypatch, stderr: str) -> None:
    def fake_run(command, **kwargs):
        if command[0] == "bash":
            raise subprocess.CalledProcessError(1, command, output="", stderr=stderr)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(project_module.subprocess, "run", fake_run)


def test_bootstrap_failure_falls_back_to_current_python_when_it_has_the_runtime(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _generator_repo(tmp_path)
    _bootstrap_fails(monkeypatch, "ensurepip is not available")
    monkeypatch.setattr(
        project_module,
        "python_has_generator_runtime",
        lambda python: Path(python) == Path(sys.executable),
    )

    assert project_module.resolve_generator_python(repo) == Path(sys.executable)
    assert "ensurepip is not available" in capsys.readouterr().err


def test_bootstrap_failure_without_the_runtime_anywhere_explains_what_to_install(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _generator_repo(tmp_path)
    _bootstrap_fails(monkeypatch, "ensurepip is not available")
    monkeypatch.setattr(project_module, "python_has_generator_runtime", lambda python: False)

    with pytest.raises(RuntimeError, match="bootstrap failed: ensurepip is not available") as info:
        project_module.resolve_generator_python(repo)

    assert "python -m pip install PyYAML jsonschema" in str(info.value)


def test_venv_without_its_runtime_uses_the_current_python(tmp_path: Path, monkeypatch) -> None:
    repo = _generator_repo(tmp_path)
    monkeypatch.setattr(
        project_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    monkeypatch.setattr(
        project_module,
        "python_has_generator_runtime",
        lambda python: Path(python) == Path(sys.executable),
    )

    assert project_module.resolve_generator_python(repo) == Path(sys.executable)


def test_working_venv_is_preferred_when_it_has_the_runtime(tmp_path: Path, monkeypatch) -> None:
    repo = _generator_repo(tmp_path)
    monkeypatch.setattr(
        project_module.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    monkeypatch.setattr(project_module, "python_has_generator_runtime", lambda python: True)

    assert project_module.resolve_generator_python(repo) == repo / ".venv/bin/python"


def test_generator_environment_puts_its_source_first_on_pythonpath(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/existing/path")

    env = project_module.generator_environment(tmp_path)

    assert env["PYTHONPATH"] == f"{tmp_path / 'src'}{os.pathsep}/existing/path"


def test_runtime_probe_detects_the_current_interpreter_and_rejects_missing_binaries(
    tmp_path: Path,
) -> None:
    assert project_module.python_has_generator_runtime(sys.executable) is True
    assert project_module.python_has_generator_runtime(tmp_path / "no-such-python") is False
