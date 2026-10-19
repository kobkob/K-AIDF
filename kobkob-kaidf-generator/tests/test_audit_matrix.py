from __future__ import annotations

import copy
import csv
from pathlib import Path

import pytest

from kaidf_gen.errors import SpecValidationError
from kaidf_gen.generator import GenerateOptions, generate
from kaidf_gen.loader import load_yaml
from kaidf_gen.schema import validate_spec


def _matrix() -> dict:
    return copy.deepcopy(load_yaml("specs/kaidf.default.yaml")["audit_matrix"])


def _spec_with(matrix: dict) -> dict:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["audit_matrix"] = matrix
    return spec


def test_default_audit_matrix_has_five_dimensions_of_twenty_points() -> None:
    matrix = _matrix()

    assert matrix["version"] == "1.0"
    assert matrix["total_points"] == 100
    assert [d["max_points"] for d in matrix["dimensions"]] == [20] * 5
    for dimension in matrix["dimensions"]:
        assert sum(check["points"] for check in dimension["checks"]) == 20


def test_default_spec_with_audit_matrix_validates() -> None:
    validate_spec(load_yaml("specs/kaidf.default.yaml"))


def test_check_points_must_add_up_to_dimension_max() -> None:
    matrix = _matrix()
    matrix["dimensions"][0]["checks"][0]["points"] += 1

    with pytest.raises(SpecValidationError, match="add up to 21 points, expected 20"):
        validate_spec(_spec_with(matrix))


def test_dimensions_must_add_up_to_total() -> None:
    matrix = _matrix()
    matrix["total_points"] = 90

    with pytest.raises(SpecValidationError):
        validate_spec(_spec_with(matrix))


def test_duplicate_dimension_ids_are_rejected() -> None:
    matrix = _matrix()
    matrix["dimensions"][1]["id"] = matrix["dimensions"][0]["id"]

    with pytest.raises(SpecValidationError, match="Duplicate audit dimension id"):
        validate_spec(_spec_with(matrix))


def test_schema_rejects_wrong_dimension_count() -> None:
    matrix = _matrix()
    matrix["dimensions"] = matrix["dimensions"][:4]

    with pytest.raises(SpecValidationError):
        validate_spec(_spec_with(matrix))


def test_schema_rejects_unknown_keys_in_audit_matrix() -> None:
    matrix = _matrix()
    matrix["weights"] = {}

    with pytest.raises(SpecValidationError):
        validate_spec(_spec_with(matrix))


def test_generated_scaffold_includes_the_audit_matrix_documents(tmp_path: Path) -> None:
    target = generate(
        load_yaml("specs/kaidf.default.yaml"), tmp_path / "out", GenerateOptions(force=False)
    )
    root = target / "docs/30-kaidf-amm"

    assert (root / "README.md").is_file()
    assert (root / "audit-matrix.csv").is_file()
    assert (root / "templates/audit-report.md").is_file()
    dimension_pages = sorted((root / "dimensions").glob("*.md"))
    assert len(dimension_pages) == 5


def test_audit_matrix_csv_matches_the_spec(tmp_path: Path) -> None:
    target = generate(
        load_yaml("specs/kaidf.default.yaml"), tmp_path / "out", GenerateOptions(force=False)
    )
    with (target / "docs/30-kaidf-amm/audit-matrix.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    expected = [
        (d["id"], c["id"], str(c["points"])) for d in _matrix()["dimensions"] for c in d["checks"]
    ]
    assert [(r["dimension_id"], r["check_id"], r["points"]) for r in rows] == expected
    assert all(r["status"] == "" and r["auditor_notes"] == "" for r in rows)
