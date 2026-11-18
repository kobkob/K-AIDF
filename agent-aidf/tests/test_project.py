from __future__ import annotations

import subprocess
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


def _generator(tmp_path: Path, monkeypatch, spec: str = "repo:\n  name: demo\n") -> Path:
    """The default spec is a file the test controls; init reads it through default_spec_path()."""
    spec_path = tmp_path / "default.yaml"
    spec_path.write_text(spec, encoding="utf-8")
    monkeypatch.setattr("agent_aidf.project.default_spec_path", lambda: spec_path)
    return spec_path


def _fake_generate(monkeypatch, *, files: dict[str, str] | None = None, error=None) -> None:
    """Replace the in-process generator: write `files` under out_dir/demo, or raise `error`."""

    def _generate(spec_path, out_dir, *, force):
        if error is not None:
            raise error
        generated = Path(out_dir) / "demo"
        for relative, content in (files or {"README.md": "# Demo\n"}).items():
            _write(generated / relative, content)
        return generated

    monkeypatch.setattr("agent_aidf.project.generate_repo", _generate)


def _generator_succeeds(monkeypatch) -> None:
    _fake_generate(
        monkeypatch, files={"README.md": "# Fresh\n", "policy/budget.yaml": "max_tokens: 1\n"}
    )


def _generator_fails(monkeypatch) -> None:
    _fake_generate(monkeypatch, error=project_module.GeneratorError("spec is invalid"))


def test_init_project_repo_uses_generator_output(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _generator(tmp_path, monkeypatch)
    _fake_generate(monkeypatch)

    repo_root = init_project_repo(project)

    assert repo_root == project / ".kaidf"
    assert (project / ".kaidf" / "README.md").is_file()


def test_init_project_repo_records_the_spec_it_used_under_dot_kaidf_specs(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    spec = "version: '1.0'\nrepo:\n  name: demo\n  files: []\nsections: []\n"
    _generator(tmp_path, monkeypatch, spec=spec)
    _fake_generate(monkeypatch)

    init_project_repo(project)

    recorded = project / ".kaidf" / project_module.SCAFFOLD_SPEC_PATH
    assert recorded == project / ".kaidf/specs/kaidf.yaml"
    assert recorded.read_text(encoding="utf-8") == spec


def test_init_generates_in_process_without_a_subprocess_or_pip(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _generator(tmp_path, monkeypatch)
    _fake_generate(monkeypatch)

    def _refuse(*args, **kwargs):
        raise AssertionError("init must not spawn a process or install packages")

    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)

    init_project_repo(project)

    assert (project / ".kaidf" / "README.md").is_file()


def _existing_project_with_state(project: Path) -> Path:
    repo = project / ".kaidf"
    _write(repo / "README.md", "# Old\n")
    _write(repo / "mentor-workflow.json", '{"accepted_phases": ["01"]}')
    _write(repo / "apps/app-1/app.json", '{"app_id": "app-1"}')
    _write(repo / "contracts/contract-1/contract.md", "# Contract\n")
    _write(repo / "policy/budget.yaml", "max_tokens: 99\n")
    return repo


def test_failing_generator_leaves_existing_dot_kaidf_untouched(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    repo = _existing_project_with_state(project)
    _generator(tmp_path, monkeypatch)
    _generator_fails(monkeypatch)

    with pytest.raises(RuntimeError, match="spec is invalid"):
        init_project_repo(project, force=True)

    assert (repo / "mentor-workflow.json").read_text(
        encoding="utf-8"
    ) == '{"accepted_phases": ["01"]}'
    assert (repo / "apps/app-1/app.json").is_file()
    assert not list(project.glob(".kaidf.bak-*"))


def test_force_keeps_the_old_directory_and_carries_over_runtime_state(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    repo = _existing_project_with_state(project)
    _generator(tmp_path, monkeypatch)
    _generator_succeeds(monkeypatch)

    init_project_repo(project, force=True)

    assert (repo / "README.md").read_text(encoding="utf-8") == "# Fresh\n"
    assert (repo / "mentor-workflow.json").read_text(
        encoding="utf-8"
    ) == '{"accepted_phases": ["01"]}'
    assert (repo / "apps/app-1/app.json").is_file()
    assert (repo / "contracts/contract-1/contract.md").is_file()
    # The saved policy wins over the generator default.
    assert (repo / "policy/budget.yaml").read_text(encoding="utf-8") == "max_tokens: 99\n"
    backups = list(project.glob(".kaidf.bak-*"))
    assert len(backups) == 1
    assert (backups[0] / "README.md").read_text(encoding="utf-8") == "# Old\n"
    assert str(backups[0]) in capsys.readouterr().err


def test_failed_swap_restores_the_old_dot_kaidf(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    repo = _existing_project_with_state(project)
    _generator(tmp_path, monkeypatch)
    _generator_succeeds(monkeypatch)

    def _broken_move(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(project_module.shutil, "move", _broken_move)

    with pytest.raises(OSError, match="disk full"):
        init_project_repo(project, force=True)

    assert (repo / "README.md").read_text(encoding="utf-8") == "# Old\n"
    assert (repo / "mentor-workflow.json").is_file()
    assert not list(project.glob(".kaidf.bak-*"))


def test_init_without_force_still_refuses_an_existing_dot_kaidf(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    _existing_project_with_state(project)
    _generator(tmp_path, monkeypatch)
    _generator_succeeds(monkeypatch)

    with pytest.raises(project_module.ProjectAlreadyInitializedError):
        init_project_repo(project)
