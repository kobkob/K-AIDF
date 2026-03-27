from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .instant_apps import list_instant_apps, load_instant_app_runtime
from .mentor import load_mentor_state
from .repo import list_packs, load_documents, resolve_repo_root

KAIDF_DIRNAME = ".kaidf"


@dataclass(frozen=True)
class ProjectStatus:
    project_root: Path
    repo_root: Path
    has_kaidf: bool
    document_count: int
    pack_count: int
    packs: list[str]
    instant_app_count: int
    instant_apps: list[str]
    mentor_step_count: int
    mentor_pending_category: str | None
    mentor_current_app_id: str | None
    mentor_current_app_url: str | None


def resolve_project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        return Path.cwd().resolve()
    path = Path(project_root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {path}")
    return path


def project_repo_root(project_root: str | Path | None) -> Path:
    return resolve_project_root(project_root) / KAIDF_DIRNAME


def resolve_runtime_repo_root(
    project_root: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> Path:
    if repo_root is not None:
        return resolve_repo_root(repo_root)
    project = resolve_project_root(project_root)
    local_repo = project_repo_root(project)
    if local_repo.exists():
        return resolve_repo_root(local_repo)
    env_repo = os.environ.get("AIDF_REPO_ROOT", "").strip()
    if env_repo:
        return resolve_repo_root(env_repo)
    return resolve_repo_root(project)


def read_project_status(
    project_root: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> ProjectStatus:
    project = resolve_project_root(project_root)
    local_repo = project_repo_root(project)
    runtime_repo = resolve_runtime_repo_root(project, repo_root)
    documents = load_documents(runtime_repo)
    packs = list_packs(documents)
    instant_app_repo = local_repo if local_repo.exists() else runtime_repo
    instant_apps = list_instant_apps(instant_app_repo)
    mentor_state = load_mentor_state(instant_app_repo)
    current_runtime = (
        load_instant_app_runtime(instant_app_repo, mentor_state.current_app_id)
        if mentor_state.current_app_id
        else None
    )
    current_app_url = (
        f"http://127.0.0.1:{current_runtime.port}"
        if current_runtime and current_runtime.status == "running" and current_runtime.port
        else None
    )
    return ProjectStatus(
        project_root=project,
        repo_root=runtime_repo,
        has_kaidf=local_repo.exists(),
        document_count=len(documents),
        pack_count=len(packs),
        packs=packs,
        instant_app_count=len(instant_apps),
        instant_apps=[app.app_id for app in instant_apps],
        mentor_step_count=mentor_state.step_count,
        mentor_pending_category=mentor_state.pending_category,
        mentor_current_app_id=mentor_state.current_app_id,
        mentor_current_app_url=current_app_url,
    )


def locate_generator_repo() -> Path:
    workspace_root = Path(__file__).resolve().parents[3]
    generator_repo = workspace_root / "kobkob-kaidf-generator"
    if not generator_repo.is_dir():
        raise RuntimeError(f"Generator repository not found: {generator_repo}")
    spec_path = generator_repo / "specs/kaidf.default.yaml"
    if not spec_path.is_file():
        raise RuntimeError(f"Default generator spec not found: {spec_path}")
    return generator_repo


def init_project_repo(project_root: str | Path | None = None, *, force: bool = False) -> Path:
    project = resolve_project_root(project_root)
    target = project_repo_root(project)
    if target.exists():
        if not force:
            raise ValueError(f"Project already contains {KAIDF_DIRNAME}: {target}")
        shutil.rmtree(target)

    generator_repo = locate_generator_repo()
    spec_path = generator_repo / "specs/kaidf.default.yaml"
    with tempfile.TemporaryDirectory(prefix="agent-aidf-init-", dir=str(project)) as temp_dir:
        temp_path = Path(temp_dir)
        env = os.environ.copy()
        generator_pythonpath = str(generator_repo / "src")
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = (
            f"{generator_pythonpath}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else generator_pythonpath
        )
        command = [
            sys.executable,
            "-m",
            "kaidf_gen.cli",
            "generate",
            str(spec_path),
            "--out",
            str(temp_path),
            "--force",
        ]
        try:
            subprocess.run(
                command,
                cwd=generator_repo,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            raise RuntimeError(f"Failed to initialize {KAIDF_DIRNAME}: {stderr}") from exc

        generated_roots = sorted(path for path in temp_path.iterdir() if path.is_dir())
        if len(generated_roots) != 1:
            raise RuntimeError(
                f"Expected one generated repository in {temp_path}, found {len(generated_roots)}"
            )
        shutil.move(str(generated_roots[0]), str(target))
    return target
