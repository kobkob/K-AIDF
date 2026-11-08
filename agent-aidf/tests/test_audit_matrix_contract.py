"""The generator's declarative KAIDF-AMM matrix must mirror the audit engine exactly.

``kobkob-kaidf-generator/specs/kaidf.default.yaml`` carries an ``audit_matrix`` block that the
generator renders into ``docs/30-kaidf-amm/``. The engine in ``audit.py`` (``DIMENSION_SPECS``) is
what scores a repository, so it is the source of truth; this test fails when either side changes
a dimension or check id, a name or title, or a point value.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agent_aidf.audit import DIMENSION_SPECS

SPEC_PATH = (
    Path(__file__).resolve().parents[2] / "kobkob-kaidf-generator" / "specs" / "kaidf.default.yaml"
)


def _spec_matrix() -> dict:
    if not SPEC_PATH.is_file():
        pytest.skip(
            f"sibling checkout missing: {SPEC_PATH} (this contract test needs the K-AIDF monorepo)"
        )
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    matrix = spec.get("audit_matrix") if isinstance(spec, dict) else None
    assert isinstance(matrix, dict), f"{SPEC_PATH} has no audit_matrix block"
    return matrix


def _engine_dimensions() -> list[tuple[str, str, int, list[tuple[str, str, int]]]]:
    return [
        (
            dimension_id,
            name,
            sum(points for _, _, points, _ in checks),
            [(check_id, title, points) for check_id, title, points, _ in checks],
        )
        for dimension_id, name, checks in DIMENSION_SPECS
    ]


def _spec_dimensions(matrix: dict) -> list[tuple[str, str, int, list[tuple[str, str, int]]]]:
    return [
        (
            dimension["id"],
            dimension["name"],
            dimension["max_points"],
            [(check["id"], check["title"], check["points"]) for check in dimension["checks"]],
        )
        for dimension in matrix["dimensions"]
    ]


def test_spec_audit_matrix_mirrors_dimension_specs_exactly() -> None:
    matrix = _spec_matrix()

    assert _spec_dimensions(matrix) == _engine_dimensions()


def test_spec_audit_matrix_totals_mirror_the_engine() -> None:
    matrix = _spec_matrix()
    engine_total = sum(max_points for _, _, max_points, _ in _engine_dimensions())

    assert matrix["total_points"] == engine_total == 100
    # The version the scorecard panel prints ("KAIDF-AMM v1.0 - Audit Scorecard").
    assert matrix["version"] == "1.0"


def test_contract_would_catch_a_changed_point_or_id() -> None:
    """Guard against a vacuous comparison: a one-point or one-id change must be visible."""
    matrix = _spec_matrix()
    expected = _engine_dimensions()

    changed_points = yaml.safe_load(yaml.safe_dump(matrix))
    changed_points["dimensions"][0]["checks"][0]["points"] += 1
    assert _spec_dimensions(changed_points) != expected

    changed_id = yaml.safe_load(yaml.safe_dump(matrix))
    changed_id["dimensions"][-1]["checks"][-1]["id"] = "remote-fallback"
    assert _spec_dimensions(changed_id) != expected
