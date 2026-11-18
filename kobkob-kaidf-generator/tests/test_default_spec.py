"""The default spec ships inside the package, so an installed generator needs no checkout.

specs/kaidf.default.yaml stays the file people edit and CI validates; the copy in the package is
what `kaidf_gen` and `agent-aidf` load at runtime. This test keeps the two identical.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import kaidf_gen

REPO_SPEC = Path(__file__).resolve().parents[1] / "specs" / "kaidf.default.yaml"


def test_packaged_default_spec_matches_the_repository_spec():
    packaged = resources.files("kaidf_gen").joinpath("specs/kaidf.default.yaml")

    assert packaged.read_bytes() == REPO_SPEC.read_bytes()


def test_packaged_default_spec_is_loadable_from_the_package_root():
    assert Path(kaidf_gen.__file__).parent.joinpath("specs", "kaidf.default.yaml").is_file()
