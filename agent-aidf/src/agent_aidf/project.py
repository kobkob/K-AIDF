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


def locate_generator_repo() -> Path:
    workspace_root = Path(__file__).resolve().parents[3]
    generator_repo = workspace_root / "kobkob-kaidf-generator"
    if not generator_repo.is_dir():
        raise RuntimeError(f"Generator repository not found: {generator_repo}")
    spec_path = generator_repo / "specs/kaidf.default.yaml"
    if not spec_path.is_file():
        raise RuntimeError(f"Default generator spec not found: {spec_path}")
    return generator_repo


# The generator needs these at runtime. Its own package is not required: the generator is run
# from its source tree through PYTHONPATH (see generator_environment).
GENERATOR_RUNTIME_MODULES = ("yaml", "jsonschema")


def generator_environment(generator_repo: Path) -> dict[str, str]:
    """Environment that runs the generator from its source tree, without an installed package."""
    env = os.environ.copy()
    generator_src = str(generator_repo / "src")
    existing = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = f"{generator_src}{os.pathsep}{existing}" if existing else generator_src
    return env


def python_has_generator_runtime(python: str | Path) -> bool:
    probe = "import " + ", ".join(GENERATOR_RUNTIME_MODULES)
    try:
        result = subprocess.run(
            [str(python), "-c", probe], capture_output=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _fallback_to_current_python(reason: str) -> Path:
    """Use the Python running kob when it can run the generator, instead of failing."""
    current = Path(sys.executable)
    if python_has_generator_runtime(current):
        print(f"kob: using the current Python for the generator ({reason}).", file=sys.stderr)
        return current
    modules = " ".join(GENERATOR_RUNTIME_MODULES)
    raise RuntimeError(
        f"{reason}. The current Python ({current}) lacks {', '.join(GENERATOR_RUNTIME_MODULES)} "
        f"too; install them there (python -m pip install PyYAML jsonschema), "
        f"or fix the environment. Modules needed: {modules}."
    )


def resolve_generator_python(generator_repo: Path) -> Path:
    bootstrap_script = generator_repo / "scripts/bootstrap.sh"
    generator_python = generator_repo / ".venv/bin/python"
    if bootstrap_script.is_file():
        try:
            subprocess.run(
                ["bash", str(bootstrap_script)],
                cwd=generator_repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip()
            return _fallback_to_current_python(f"bootstrap failed: {stderr}")
        if generator_python.is_file() and python_has_generator_runtime(generator_python):
            return generator_python
        return _fallback_to_current_python("the generator .venv cannot import its runtime modules")
    if generator_python.is_file():
        return generator_python
    return Path(sys.executable)


def init_project_repo(project_root: str | Path | None = None, *, force: bool = False) -> Path:
    project = resolve_project_root(project_root)
    target = project_repo_root(project)
    if target.exists():
        if not force:
            raise ProjectAlreadyInitializedError(target)
        shutil.rmtree(target)

    generator_repo = locate_generator_repo()
    generator_python = resolve_generator_python(generator_repo)
    spec_path = generator_repo / "specs/kaidf.default.yaml"
    with tempfile.TemporaryDirectory(prefix="agent-aidf-init-", dir=str(project)) as temp_dir:
        temp_path = Path(temp_dir)
        env = generator_environment(generator_repo)
        command = [
            str(generator_python),
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
