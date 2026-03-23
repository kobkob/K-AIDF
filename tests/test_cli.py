from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    _write(
        repo / "README.md",
        "# Demo\n",
    )
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
        "# Transparency\n\n"
        "Explainable use.\n",
    )
    _write(
        repo / "docs/10-maturity-model/levels/04-managed.md",
        "---\n"
        "id: docs/10-maturity-model/levels/04-managed.md\n"
        "title: Managed\n"
        "document_class: core-doc\n"
        "phase: 10-maturity-model\n"
        "visibility: internal\n"
        "status: active\n"
        "pack: maturity-model\n"
        "maturity_level: managed\n"
        "---\n\n"
        "# Managed\n",
    )
    return repo


def _build_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    _build_repo(project / ".kaidf-parent")
    (project / ".kaidf-parent" / "demo").rename(project / ".kaidf")
    return project


def _run(*args: str, repo: Path) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": "src"}
    env.update()
    return subprocess.run(
        [sys.executable, "-m", "agent_aidf.cli", "--repo", str(repo), *args],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _run_project(*args: str, project: Path) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": "src"}
    env.update()
    return subprocess.run(
        [sys.executable, "-m", "agent_aidf.cli", "--project", str(project), *args],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_packs_command_lists_detected_packs(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    result = _run("packs", repo=repo)

    assert result.returncode == 0
    assert "ethical-model" in result.stdout
    assert "maturity-model" in result.stdout


def test_docs_command_filters_by_ethical_domain(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    result = _run("docs", "--pack", "ethical-model", "--ethical-domain", "transparency", repo=repo)

    assert result.returncode == 0
    assert "docs/20-ethical-model/principles/transparency.md" in result.stdout
    assert "Managed" not in result.stdout


def test_open_command_prints_document_content(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    result = _run("open", "docs/10-maturity-model/levels/04-managed.md", repo=repo)

    assert result.returncode == 0
    assert "# Managed" in result.stdout


def test_find_command_matches_pack_metadata(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    result = _run("find", "transparency", repo=repo)

    assert result.returncode == 0
    assert "docs/20-ethical-model/principles/transparency.md" in result.stdout


def test_chat_command_uses_controller_stub(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    result = _run("chat", "hello", repo=repo)

    assert result.returncode == 0
    assert "AI chat controller is not configured yet." in result.stdout


def test_status_command_uses_project_dot_kaidf_by_default(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    result = _run_project("status", project=project)

    assert result.returncode == 0
    assert "has_kaidf: yes" in result.stdout
    assert f"repo_root: {project / '.kaidf'}" in result.stdout
    assert "pack_count: 2" in result.stdout


def test_context_command_lists_selected_documents_for_prompt(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    result = _run_project("context", "transparency", project=project)

    assert result.returncode == 0
    assert "selected_documents:" in result.stdout
    assert "docs/20-ethical-model/principles/transparency.md" in result.stdout


def test_init_command_creates_dot_kaidf_in_current_project(tmp_path: Path) -> None:
    project = tmp_path / "fresh-project"
    project.mkdir()

    result = _run_project("init", project=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".kaidf").is_dir()
    assert (project / ".kaidf" / "README.md").is_file()
