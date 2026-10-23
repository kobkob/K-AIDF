from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _run_bootstrap(project: Path, path_prefix: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": f"{path_prefix}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "scripts/bootstrap.sh"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")
def test_bootstrap_reuses_parent_packages_when_ensurepip_is_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "scripts/bootstrap.sh", project / "scripts/bootstrap.sh")
    shutil.copy(REPO / "pyproject.toml", project / "pyproject.toml")

    # A `python` that behaves like an interpreter without ensurepip: a full venv cannot be
    # created, but --without-pip works.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    wrapper = fake_bin / "python"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-m" && "$2" == "venv" && " $* " != *" --without-pip "* ]]; then\n'
        '  echo "ensurepip is not available" >&2\n'
        "  exit 1\n"
        "fi\n"
        f'exec "{sys.executable}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    first = _run_bootstrap(project, fake_bin)
    assert first.returncode == 0, first.stderr
    assert (project / ".venv/.parent-packages").is_file()
    probe = subprocess.run(
        [str(project / ".venv/bin/python"), "-c", "import yaml, jsonschema"],
        capture_output=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr

    second = _run_bootstrap(project, fake_bin)
    assert second.returncode == 0, second.stderr
