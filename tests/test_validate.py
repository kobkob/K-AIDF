from pathlib import Path

import pytest

from kaidf_gen.errors import KaidfGenError, SpecValidationError
from kaidf_gen.loader import load_yaml
from kaidf_gen.schema import validate_spec


def test_default_spec_valid():
    spec = load_yaml("specs/kaidf.default.yaml")
    validate_spec(spec)


def test_load_yaml_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(KaidfGenError, match="Spec file not found"):
        load_yaml(missing)


def test_load_yaml_requires_mapping_root(tmp_path: Path) -> None:
    spec_path = tmp_path / "list.yaml"
    spec_path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(KaidfGenError, match="Spec root must be a mapping/object"):
        load_yaml(spec_path)


def test_validate_spec_reports_schema_path() -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    del spec["repo"]["name"]

    with pytest.raises(SpecValidationError, match=r"repo: 'name' is a required property"):
        validate_spec(spec)


def test_validate_spec_rejects_unknown_front_matter_fields() -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["repo"]["files"][0]["front_matter"] = {"unknown": "value"}

    with pytest.raises(SpecValidationError, match=r"repo.files.0.front_matter: Additional properties are not allowed"):
        validate_spec(spec)


def test_validate_spec_allows_pack_specific_front_matter_fields() -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["repo"]["files"][0]["front_matter"] = {
        "id": "README.md",
        "title": "kobkob-kaidf",
        "document_class": "core-doc",
        "phase": "root",
        "visibility": "internal",
        "status": "active",
        "pack": "maturity-model",
        "assessment_type": "guidance",
    }

    validate_spec(spec)
