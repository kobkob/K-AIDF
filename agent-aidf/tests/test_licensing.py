"""Licensing and ownership stay consistent across the repository (issue #6).

These read files of the surrounding repository checkout, so they skip when it is not present.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOLDER = "Ricardo Filipo"
COMPONENTS = ("agent-aidf", "mcp-aidf", "kobkob-kaidf-generator")

pytestmark = pytest.mark.skipif(
    not (ROOT / "CONTRIBUTOR_LICENSE_AGREEMENT.md").is_file(),
    reason="needs the K-AIDF repository checkout",
)


def test_every_license_names_the_copyright_holder() -> None:
    for path in [ROOT / "LICENSE", *(ROOT / name / "LICENSE" for name in COMPONENTS)]:
        text = path.read_text(encoding="utf-8")
        assert f"Copyright (c) 2026 {HOLDER}\n" in text, str(path)


def test_every_package_declares_the_mit_license() -> None:
    for name in COMPONENTS:
        text = (ROOT / name / "pyproject.toml").read_text(encoding="utf-8")
        assert 'license = {text = "MIT"}' in text, name


def test_the_cla_assigns_rights_to_the_holder_personally() -> None:
    text = (ROOT / "CONTRIBUTOR_LICENSE_AGREEMENT.md").read_text(encoding="utf-8")
    assigned = re.search(r"assign, transfer, and convey to (.+?) all right", text)
    assert assigned is not None
    assert assigned.group(1) == HOLDER


def test_the_cla_allowlist_covers_every_root_codeowner() -> None:
    workflow = (ROOT / ".github/workflows/cla-check.yml").read_text(encoding="utf-8")
    allowlist = set(re.search(r"allowlist: '([^']*)'", workflow).group(1).split(","))
    owners = {
        line.split()[1].lstrip("@")
        for line in (ROOT / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if line.startswith("*")
    }
    assert owners <= allowlist


def test_component_codeowners_files_are_gone() -> None:
    # GitHub reads only the root CODEOWNERS; nested copies were never applied.
    for name in COMPONENTS:
        assert not (ROOT / name / "CODEOWNERS").exists(), name
