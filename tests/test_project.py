from __future__ import annotations

from pathlib import Path

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

    status = read_project_status(project, repo)

    assert status.has_kaidf is True
    assert status.document_count == 2
    assert status.pack_count == 1
    assert status.packs == ["ethical-model"]


def test_init_project_repo_uses_generator_output(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    generator_repo = tmp_path / "generator"
    (generator_repo / "specs").mkdir(parents=True)
    (generator_repo / "specs/kaidf.default.yaml").write_text("repo:\n  name: demo\n", encoding="utf-8")

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
