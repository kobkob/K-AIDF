from __future__ import annotations

import socket
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
        [sys.executable, "-m", "agent_aidf.legacy_cli", "--repo", str(repo), *args],
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
        [sys.executable, "-m", "agent_aidf.legacy_cli", "--project", str(project), *args],
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
    assert "mentor_step_count: 0" in result.stdout
    assert "mentor_current_app_id: none" in result.stdout
    assert "mentor_current_app_url: none" in result.stdout


def test_context_command_lists_selected_documents_for_prompt(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    result = _run_project("context", "transparency", project=project)

    assert result.returncode == 0
    assert "selected_documents:" in result.stdout
    assert "docs/20-ethical-model/principles/transparency.md" in result.stdout


def test_app_create_command_creates_persistent_app_under_dot_kaidf(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    result = _run_project("app-create", "mentor-web", "--kind", "web", project=project)

    assert result.returncode == 0
    assert "app_id: mentor-web" in result.stdout
    assert (project / ".kaidf" / "apps" / "mentor-web" / "app.json").is_file()


def test_apps_command_lists_persistent_apps(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    _run_project("app-create", "mentor-shell", project=project)

    result = _run_project("apps", project=project)

    assert result.returncode == 0
    assert "mentor-shell" in result.stdout
    assert "persistent" in result.stdout


def test_contract_create_command_generates_basic_contract_files(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    result = _run_project(
        "contract-create",
        "basic-web-contract",
        "--brief",
        "Create a basic contract for a mentor-led web workflow.",
        project=project,
    )

    assert result.returncode == 0, result.stderr
    assert "contract_id: basic-web-contract" in result.stdout
    assert "phase_count: 5" in result.stdout
    assert (project / ".kaidf" / "contracts" / "basic-web-contract" / "contract.json").is_file()


def test_contracts_and_contract_open_commands_show_generated_contract(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    _run_project(
        "contract-create",
        "basic-shell-contract",
        "--brief",
        "Create a basic contract for a mentor-led shell workflow.",
        project=project,
    )

    listed = _run_project("contracts", project=project)
    opened = _run_project("contract-open", "basic-shell-contract", project=project)

    assert listed.returncode == 0
    assert "basic-shell-contract" in listed.stdout
    assert opened.returncode == 0
    assert "phase_count: 5" in opened.stdout
    assert "source_summary:" in opened.stdout


def test_mentor_command_persists_workflow_between_invocations(tmp_path: Path) -> None:
    project = _build_project(tmp_path)

    first = _run_project("mentor", project=project)
    second = _run_project(
        "mentor",
        "We need a transparent localhost web app with human review before release.",
        project=project,
    )
    status = _run_project("mentor", "--status", project=project)

    assert first.returncode == 0
    assert "Mentor workflow is active." in first.stdout
    assert second.returncode == 0
    assert "Mentor assessment:" in second.stdout
    assert "Action: created persistent web instant app 'mentor-web-app'" in second.stdout
    assert status.returncode == 0
    assert "step_count: 1" in status.stdout
    assert "current_app_id: mentor-web-app" in status.stdout
    assert "http://127.0.0.1:" in status.stdout
    _run_project("app-stop", "mentor-web-app", project=project)


def test_mentor_reset_clears_persisted_state(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    _run_project("mentor", project=project)

    result = _run_project("mentor", "--reset", project=project)
    status = _run_project("mentor", "--status", project=project)

    assert result.returncode == 0
    assert "Reset mentor workflow state" in result.stdout
    assert "step_count: 0" in status.stdout


def test_mentor_status_tracks_new_current_app_after_spawn(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    _run_project("mentor", project=project)
    _run_project(
        "mentor",
        "We need a transparent localhost web app with human review before release.",
        project=project,
    )
    second = _run_project(
        "mentor",
        "We also need a separate terminal shell app for internal reviewers to capture checklist notes.",
        project=project,
    )
    status = _run_project("mentor", "--status", project=project)

    assert second.returncode == 0
    assert "spawned new persistent shell instant app 'mentor-shell-app'" in second.stdout
    assert "current_app_id: mentor-shell-app" in status.stdout
    _run_project("app-stop", "mentor-web-app", project=project)


def test_app_run_runtime_and_stop_commands(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    _run_project("app-create", "mentor-web", "--kind", "web", project=project)
    port = _free_port()

    started = _run_project("app-run", "mentor-web", "--port", str(port), project=project)
    runtime = _run_project("app-runtime", "mentor-web", project=project)
    stopped = _run_project("app-stop", "mentor-web", project=project)

    assert started.returncode == 0, started.stderr
    assert "status: running" in started.stdout
    assert f"port: {port}" in started.stdout
    assert runtime.returncode == 0
    assert "status: running" in runtime.stdout
    assert stopped.returncode == 0
    assert "status: stopped" in stopped.stdout


def test_init_command_creates_dot_kaidf_in_current_project(tmp_path: Path) -> None:
    project = tmp_path / "fresh-project"
    project.mkdir()

    result = _run_project("init", project=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".kaidf").is_dir()
    assert (project / ".kaidf" / "README.md").is_file()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
