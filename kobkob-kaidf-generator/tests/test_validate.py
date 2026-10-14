from pathlib import Path

import pytest
import yaml

from kaidf_gen.errors import KaidfGenError, SpecParsingError, SpecValidationError
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

    error_msg = r"repo.files.0.front_matter: Additional properties are not allowed"
    with pytest.raises(SpecValidationError, match=error_msg):
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


def test_validate_spec_allows_ethical_model_front_matter_fields() -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["repo"]["files"][0]["front_matter"] = {
        "id": "README.md",
        "title": "kobkob-kaidf",
        "document_class": "core-doc",
        "phase": "root",
        "visibility": "internal",
        "status": "active",
        "pack": "ethical-model",
        "ethical_domain": "transparency",
        "control_type": "guidance",
        "risk_type": "bias-and-harm",
    }

    validate_spec(spec)


def _spec_with(root_files: list[dict], sections: list[dict]) -> dict:
    return {"version": "1.0", "repo": {"name": "demo", "files": root_files}, "sections": sections}


def test_load_yaml_reports_malformed_yaml_as_spec_parsing_error(tmp_path: Path) -> None:
    spec_path = tmp_path / "broken.yaml"
    spec_path.write_text("version: '1.0'\nrepo: [unclosed\n", encoding="utf-8")

    with pytest.raises(
        SpecParsingError, match=r"Malformed YAML .*broken\.yaml \(line \d+, column \d+\)"
    ):
        load_yaml(spec_path)


def test_load_yaml_malformed_yaml_is_not_a_raw_yaml_error(tmp_path: Path) -> None:
    spec_path = tmp_path / "broken.yaml"
    spec_path.write_text("key: value\n  bad: indent\n", encoding="utf-8")

    with pytest.raises(SpecParsingError) as excinfo:
        load_yaml(spec_path)

    assert isinstance(excinfo.value, KaidfGenError)
    assert not isinstance(excinfo.value, yaml.YAMLError)


def test_load_yaml_rejects_non_utf8_spec_as_spec_parsing_error(tmp_path: Path) -> None:
    spec_path = tmp_path / "latin1.yaml"
    spec_path.write_bytes("title: Automação\n".encode("latin-1"))

    with pytest.raises(SpecParsingError, match="not valid UTF-8"):
        load_yaml(spec_path)


def test_validate_spec_rejects_duplicate_section_file_paths() -> None:
    spec = _spec_with(
        [],
        [
            {
                "path": "docs/01_intent_constraints",
                "files": [{"path": "README.md", "inline": "a\n"}],
            },
            {
                "path": "docs/01_intent_constraints",
                "files": [{"path": "README.md", "inline": "b\n"}],
            },
        ],
    )

    with pytest.raises(
        SpecValidationError, match="Duplicate output path 'docs/01_intent_constraints/README.md'"
    ):
        validate_spec(spec)


def test_validate_spec_rejects_duplicate_between_root_and_section_files() -> None:
    spec = _spec_with(
        [{"path": "docs/notes.md", "inline": "root\n"}],
        [{"path": "docs", "files": [{"path": "notes.md", "inline": "section\n"}]}],
    )

    with pytest.raises(SpecValidationError, match="Duplicate output path 'docs/notes.md'"):
        validate_spec(spec)


def test_validate_spec_treats_equivalent_spellings_as_duplicates() -> None:
    spec = _spec_with(
        [],
        [
            {"path": "docs/00-overview", "files": [{"path": "./kaidf.md", "inline": "a\n"}]},
            {"path": "docs/00-overview/", "files": [{"path": "kaidf.md", "inline": "b\n"}]},
        ],
    )

    with pytest.raises(
        SpecValidationError, match="Duplicate output path 'docs/00-overview/kaidf.md'"
    ):
        validate_spec(spec)


def test_validate_spec_allows_same_section_path_with_distinct_files() -> None:
    spec = _spec_with(
        [],
        [
            {
                "path": "docs/10-maturity-model",
                "files": [{"path": "README.md", "inline": "a\n"}],
            },
            {
                "path": "docs/10-maturity-model",
                "files": [{"path": "levels/01.md", "inline": "b\n"}],
            },
        ],
    )

    validate_spec(spec)
