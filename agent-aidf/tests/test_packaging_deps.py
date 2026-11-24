"""The .deb depends on python3 and python3-venv only; its libraries live in a private venv.

Checks the requirement list against pyproject, the maintainer scripts, and the launcher's clean
failure when the venv has no libraries. No network and no installation.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGING = REPO / "packaging" / "debian"


def _pyproject_dependencies() -> set[str]:
    text = (REPO / "agent-aidf" / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies = \[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    assert block is not None
    return set(re.findall(r'"([^"]+)"', block.group(1)))


def test_the_packaged_requirements_match_the_project_dependencies() -> None:
    lines = (PACKAGING / "requirements.txt").read_text(encoding="utf-8").splitlines()
    requirements = {line.strip() for line in lines if line.strip() and not line.startswith("#")}

    assert requirements == _pyproject_dependencies()


def test_the_deb_depends_only_on_python_and_venv_not_on_old_distro_libraries() -> None:
    control = (PACKAGING / "control.in").read_text(encoding="utf-8")
    depends = re.search(r"^Depends: (.*)$", control, re.MULTILINE).group(1)

    assert depends == "python3 (>= 3.10), python3-venv"


def test_maintainer_scripts_are_posix_and_never_touch_project_or_user_state() -> None:
    for name in ("postinst", "postrm", "install-deps.sh"):
        script = PACKAGING / name
        assert subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0, name
        code = "\n".join(
            line
            for line in script.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        assert ".kaidf" not in code, name
        assert ".config" not in code, name


def test_kob_says_how_to_fix_missing_libraries_instead_of_a_traceback(tmp_path: Path) -> None:
    home = tmp_path / "kaidf"
    (home / "agent" / "src").mkdir(parents=True)
    bare = tmp_path / "bare-venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(bare)], check=True)
    env = {**os.environ, "KAIDF_HOME": str(home), "KAIDF_PYTHON": str(bare / "bin" / "python")}
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        ["sh", str(PACKAGING / "kob"), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 1
    assert "install-deps.sh" in result.stderr
    assert "Traceback" not in result.stderr
