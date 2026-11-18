from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .generator_bridge import GeneratorError, default_spec_path, generate_repo
from .instant_apps import list_instant_apps, load_instant_app_runtime
from .mentor import load_mentor_state
from .repo import list_packs, load_documents, resolve_repo_root

KAIDF_DIRNAME = ".kaidf"
# Where `kob init` records the spec that generated the scaffold, inside .kaidf/.
SCAFFOLD_SPEC_PATH = "specs/kaidf.yaml"


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
    mentor_accepted_phases: list[int]


def resolve_project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        return Path.cwd().resolve()
    path = Path(project_root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {path}")
    return path


def project_repo_root(project_root: str | Path | None) -> Path:
    return resolve_project_root(project_root) / KAIDF_DIRNAME


class MentorNotInitializedError(ValueError):
    pass


class ProjectAlreadyInitializedError(ValueError):
    """The project already has a .kaidf/ directory and init was not asked to overwrite it."""

    def __init__(self, target: Path) -> None:
        super().__init__(f"Project already contains {KAIDF_DIRNAME}: {target}")
        self.target = target


def resolve_mentor_repo_root(project_root: str | Path | None = None) -> Path:
    """The mentor workflow always reads and writes .kaidf/mentor-workflow.json.

    Unlike resolve_runtime_repo_root(), this never falls back to the project root or
    AIDF_REPO_ROOT: doing so let `kob mentor` write its state file outside .kaidf/ before
    `kob init` had run, scattering local runtime state across the project tree.
    """
    project = resolve_project_root(project_root)
    repo = project_repo_root(project)
    if not repo.exists():
        raise MentorNotInitializedError(
            f"No {KAIDF_DIRNAME}/ found at {project}. Run `kob init` first to start the mentor "
            f"workflow."
        )
    return repo


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
        mentor_accepted_phases=mentor_state.accepted_phases,
    )


# Runtime state that `init --force` carries over from the replaced .kaidf/ into the new one.
# mentor-workflow.json is the progress of the user's mentor session; apps/, contracts/ and policy/
# hold accepted work. The generator writes defaults for policy/, so the saved copy wins there.
PRESERVED_RUNTIME_STATE = ("mentor-workflow.json", "apps", "contracts", "policy")


def _carry_over_runtime_state(backup: Path, target: Path) -> None:
    for name in PRESERVED_RUNTIME_STATE:
        source = backup / name
        if not source.exists():
            continue
        destination = target / name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def init_project_repo(project_root: str | Path | None = None, *, force: bool = False) -> Path:
    """Create .kaidf/ from the generator.

    The scaffold is generated in a temporary directory first, so a missing generator or an
    invalid spec leaves an existing .kaidf/ untouched. With force, the old directory is renamed to
    .kaidf.bak-<timestamp> and kept (its path is printed), the runtime state in
    PRESERVED_RUNTIME_STATE is copied into the new scaffold, and the old directory is restored if
    anything fails after the rename.
    """
    project = resolve_project_root(project_root)
    target = project_repo_root(project)
    if target.exists() and not force:
        raise ProjectAlreadyInitializedError(target)

    spec_path = default_spec_path()
    with tempfile.TemporaryDirectory(prefix="agent-aidf-init-", dir=str(project)) as temp_dir:
        temp_path = Path(temp_dir)
        try:
            generated = generate_repo(spec_path, temp_path, force=True)
        except GeneratorError as exc:
            raise RuntimeError(f"Failed to initialize {KAIDF_DIRNAME}: {exc}") from exc

        backup: Path | None = None
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = target.with_name(f"{target.name}.bak-{stamp}")
            target.rename(backup)
        try:
            shutil.move(str(generated), str(target))
            if backup is not None:
                _carry_over_runtime_state(backup, target)
        except BaseException:
            if target.exists():
                shutil.rmtree(target)
            if backup is not None:
                backup.rename(target)
            raise
    if backup is not None:
        print(f"kob: the previous {KAIDF_DIRNAME} was kept at {backup}", file=sys.stderr)
    # Record which spec produced the scaffold, so `kob audit` can parse it (specs-parse) and a
    # later regeneration knows where it came from. A missing spec would already have failed the
    # generator above, so the guard only keeps that error from being masked by a second one.
    if spec_path.is_file():
        recorded_spec = target / SCAFFOLD_SPEC_PATH
        recorded_spec.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(spec_path, recorded_spec)
    return target
