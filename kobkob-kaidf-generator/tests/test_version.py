import importlib
import importlib.metadata
import re
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from packaging.version import Version

import kaidf_gen

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def pyproject_version() -> str:
    match = re.search(r'^version = "([^"]+)"$', PYPROJECT.read_text(encoding="utf-8"), re.M)
    assert match is not None, f'no `version = "..."` line in {PYPROJECT}'
    return match.group(1)


def test_version_matches_pyproject_when_package_metadata_is_available() -> None:
    try:
        installed = importlib.metadata.version("kobkob-kaidf-generator")
    except PackageNotFoundError:
        pytest.skip("kobkob-kaidf-generator is not installed, so there is no package metadata")

    assert kaidf_gen.__version__ == installed
    # Packaging normalizes pre-release spellings (0.7.0-rc1 -> 0.7.0rc1), so compare as versions.
    assert Version(kaidf_gen.__version__) == Version(pyproject_version())
    assert kaidf_gen.__version__ != "0.1.0"


def test_version_falls_back_to_unknown_without_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    try:
        assert importlib.reload(kaidf_gen).__version__ == "unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(kaidf_gen)
