"""The Debian package and the Makefile lifecycle targets. The build runs only where dpkg-deb is."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACKAGING = REPO / "packaging" / "debian"
HAS_DPKG = shutil.which("dpkg-deb") is not None


def _version() -> str:
    text = (REPO / "agent-aidf" / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "(.*)"', text, re.MULTILINE).group(1)


def _build(out: Path) -> Path:
    result = subprocess.run(
        ["bash", str(PACKAGING / "build-deb.sh"), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    deb = out / f"kaidf_{_version()}_all.deb"
    assert deb.is_file()
    return deb


def test_control_template_declares_the_package() -> None:
    control = (PACKAGING / "control.in").read_text(encoding="utf-8")
    fields = dict(
        line.split(": ", 1) for line in control.splitlines() if re.match(r"^[A-Z][\w-]*: ", line)
    )

    assert fields["Package"] == "kaidf"
    assert fields["Version"] == "@VERSION@"
    assert fields["Architecture"] == "all"
    assert "python3 (>= 3.10)" in fields["Depends"]


def test_the_launcher_is_posix_shell_and_targets_usr_bin_kob() -> None:
    launcher = PACKAGING / "kob"
    assert launcher.read_text(encoding="utf-8").startswith("#!/bin/sh\n")
    assert subprocess.run(["sh", "-n", str(launcher)], check=False).returncode == 0
    assert os.access(launcher, os.X_OK)


def test_makefile_declares_the_lifecycle_targets() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    phony = re.search(r"^\.PHONY:(.*?)(?=^\S)", makefile, re.MULTILINE | re.DOTALL)
    assert phony is not None
    declared = phony.group(1).replace("\\\n", " ").split()

    for target in ("deb", "install", "uninstall", "update", "upgrade"):
        assert target in declared, target
        assert re.search(rf"^{target}:", makefile, re.MULTILINE), target


def test_the_package_upgrade_path_never_ships_user_or_project_state() -> None:
    """Upgrades keep ~/.config/kaidf and .kaidf/ only if the package does not own them."""
    script = (PACKAGING / "build-deb.sh").read_text(encoding="utf-8")
    assert ".kaidf" not in script.split("cp -r")[0]
    assert "~/.config" not in script
    assert "conffiles" not in script


@pytest.mark.skipif(not HAS_DPKG, reason="dpkg-deb is not installed")
def test_build_produces_a_valid_deb_with_the_expected_files(tmp_path: Path) -> None:
    deb = _build(tmp_path)

    info = subprocess.run(
        ["dpkg-deb", "--info", str(deb)], capture_output=True, text=True, check=True
    ).stdout
    assert "Package: kaidf" in info
    assert f"Version: {_version()}" in info
    listing = subprocess.run(
        ["dpkg-deb", "--contents", str(deb)], capture_output=True, text=True, check=True
    ).stdout
    assert "./usr/bin/kob" in listing
    assert "./usr/lib/kaidf/agent/src/agent_aidf/cli/main.py" in listing
    assert "./usr/lib/kaidf/generator/src/kaidf_gen/" in listing
    assert "__pycache__" not in listing
    assert "/.kaidf/" not in listing
    assert "/.config/" not in listing


@pytest.mark.skipif(not HAS_DPKG, reason="dpkg-deb is not installed")
def test_the_installed_kob_starts_from_the_package_tree(tmp_path: Path) -> None:
    deb = _build(tmp_path / "out")
    tree = tmp_path / "root"
    subprocess.run(["dpkg-deb", "--extract", str(deb), str(tree)], check=True)
    env = {
        **os.environ,
        "KAIDF_HOME": str(tree / "usr" / "lib" / "kaidf"),
        "KAIDF_PYTHON": sys.executable,
    }
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        ["sh", str(tree / "usr" / "bin" / "kob"), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("kob ")
