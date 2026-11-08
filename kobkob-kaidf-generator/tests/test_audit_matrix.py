from __future__ import annotations

import copy
import csv
import re
from pathlib import Path

import pytest

from kaidf_gen.audit_matrix import (
    CSV_COLUMNS,
    expand_markers,
    render_checks_table,
    render_csv,
    render_summary,
)
from kaidf_gen.errors import GenerationError, SpecValidationError
from kaidf_gen.generator import GenerateOptions, generate
from kaidf_gen.loader import load_yaml
from kaidf_gen.schema import validate_spec
from kaidf_gen.template_loader import list_library_keys

# The dimensions of the `kob audit` engine (agent-aidf audit.py DIMENSION_SPECS), in order: id,
# name and (check id, points) pairs. The engine is the source of truth, and
# agent-aidf/tests/test_audit_matrix_contract.py compares the spec block with it field by field,
# titles included. This copy lets the generator suite, which cannot import agent_aidf, catch a
# changed id, name or point on its own.
ENGINE_DIMENSIONS = (
    (
        "data-sovereignty",
        "Data Sovereignty & Perimeter",
        (("no-credentials", 10), ("pii-masking-rules", 10)),
    ),
    (
        "methodology-as-code",
        "Methodology-as-Code",
        (
            ("kaidf-scaffold", 4),
            ("mentor-state", 4),
            ("specs-parse", 4),
            ("front-matter-v2", 4),
            ("skills-manifest", 4),
        ),
    ),
    (
        "regulatory-compliance",
        "Regulatory Compliance",
        (
            ("risk-assessment", 5),
            ("explicability-schema", 5),
            ("hitl-config", 5),
            ("dataset-audit", 5),
        ),
    ),
    (
        "deterministic-guardrails",
        "Deterministic Guardrails",
        (("ci-workflows", 10), ("blocking-gates", 10)),
    ),
    (
        "cost-infrastructure-health",
        "Cost & Infrastructure Health",
        (("budget-caps", 10), ("local-fallback", 10)),
    ),
)
ENGINE_CHECK_COUNT = sum(len(checks) for _, _, checks in ENGINE_DIMENSIONS)


def _matrix() -> dict:
    return copy.deepcopy(load_yaml("specs/kaidf.default.yaml")["audit_matrix"])


def _spec_with(matrix: dict) -> dict:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["audit_matrix"] = matrix
    return spec


def _generate_default(tmp_path: Path) -> Path:
    return generate(
        load_yaml("specs/kaidf.default.yaml"), tmp_path / "out", GenerateOptions(force=False)
    )


def _unescape(cell: str) -> str:
    return re.sub(r"\\(.)", r"\1", cell)


def _table_rows(markdown: str) -> list[tuple[str, str, str, str]]:
    """(check id, title, points, evidence) for each body row of the check table."""
    rows = []
    for line in markdown.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [_unescape(cell.strip()) for cell in line.strip().strip("|").split(" | ")]
        rows.append((cells[0].strip("`"), cells[1], cells[2], cells[3]))
    return rows


def test_default_audit_matrix_has_five_dimensions_of_twenty_points() -> None:
    matrix = _matrix()

    assert matrix["version"] == "1.0"
    assert matrix["total_points"] == 100
    assert [d["max_points"] for d in matrix["dimensions"]] == [20] * 5
    for dimension in matrix["dimensions"]:
        assert sum(check["points"] for check in dimension["checks"]) == 20


def test_default_audit_matrix_lists_the_engine_checks_in_order() -> None:
    matrix = _matrix()

    assert [
        (d["id"], d["name"], tuple((c["id"], c["points"]) for c in d["checks"]))
        for d in matrix["dimensions"]
    ] == list(ENGINE_DIMENSIONS)
    assert all(c["evidence"].strip() for d in matrix["dimensions"] for c in d["checks"])
    assert all(d["summary"].strip() for d in matrix["dimensions"])


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


def test_schema_requires_a_dimension_summary() -> None:
    matrix = _matrix()
    del matrix["dimensions"][0]["summary"]

    with pytest.raises(SpecValidationError):
        validate_spec(_spec_with(matrix))


def test_schema_rejects_unknown_keys_in_audit_matrix() -> None:
    matrix = _matrix()
    matrix["weights"] = {}

    with pytest.raises(SpecValidationError):
        validate_spec(_spec_with(matrix))


def test_generated_scaffold_includes_the_audit_matrix_documents(tmp_path: Path) -> None:
    root = _generate_default(tmp_path) / "docs/30-kaidf-amm"

    assert (root / "README.md").is_file()
    assert (root / "audit-matrix.csv").is_file()
    assert (root / "templates/audit-report.md").is_file()
    dimension_pages = sorted((root / "dimensions").glob("*.md"))
    assert len(dimension_pages) == 5


def test_audit_matrix_csv_is_rendered_from_the_spec_block(tmp_path: Path) -> None:
    target = _generate_default(tmp_path)
    with (target / "docs/30-kaidf-amm/audit-matrix.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert tuple(reader.fieldnames or ()) == CSV_COLUMNS
    expected = [
        (d["id"], d["name"], c["id"], c["title"], str(c["points"]), c["evidence"])
        for d in _matrix()["dimensions"]
        for c in d["checks"]
    ]
    assert [
        (
            r["dimension_id"],
            r["dimension"],
            r["check_id"],
            r["check"],
            r["points"],
            r["evidence"],
        )
        for r in rows
    ] == expected
    assert len(rows) == ENGINE_CHECK_COUNT
    assert all(r["status"] == "" and r["auditor_notes"] == "" for r in rows)


def test_no_static_audit_matrix_csv_is_left_in_the_template_library() -> None:
    assert "docs/30-kaidf-amm/audit-matrix.csv" not in list_library_keys()


def test_dimension_pages_render_their_check_tables_from_the_spec_block(tmp_path: Path) -> None:
    root = _generate_default(tmp_path) / "docs/30-kaidf-amm/dimensions"

    for index, dimension in enumerate(_matrix()["dimensions"], start=1):
        page = (root / f"{index:02d}-{dimension['id']}.md").read_text(encoding="utf-8")
        expected = [
            (c["id"], c["title"], str(c["points"]), c["evidence"]) for c in dimension["checks"]
        ]
        assert "<!-- audit_matrix:" not in page, dimension["id"]
        assert "| Check | Criterion | Points | Evidence required |" in page, dimension["id"]
        assert _table_rows(page) == expected, dimension["id"]


def test_dimension_pages_render_their_summary_from_the_spec_block(tmp_path: Path) -> None:
    root = _generate_default(tmp_path) / "docs/30-kaidf-amm/dimensions"

    for index, dimension in enumerate(_matrix()["dimensions"], start=1):
        page = (root / f"{index:02d}-{dimension['id']}.md").read_text(encoding="utf-8")
        assert f"\n\n{dimension['summary']}\n\n" in page, dimension["id"]
        assert page.count(dimension["summary"]) == 1, dimension["id"]


def test_render_summary_requires_a_summary() -> None:
    matrix = _matrix()
    del matrix["dimensions"][2]["summary"]

    with pytest.raises(GenerationError, match="'regulatory-compliance' has no summary"):
        render_summary(matrix, "regulatory-compliance")


def test_unknown_marker_kind_is_rejected() -> None:
    with pytest.raises(GenerationError, match="Unknown audit_matrix marker 'points'"):
        expand_markers("<!-- audit_matrix:points data-sovereignty -->\n", _matrix())


def test_checks_table_escapes_markdown_punctuation() -> None:
    matrix = _matrix()
    check = matrix["dimensions"][0]["checks"][0]
    check["title"] = "a|b"
    check["evidence"] = "specs/*.yaml and __pycache__ with `code`"

    table = render_checks_table(matrix, matrix["dimensions"][0]["id"])

    assert r"| a\|b |" in table
    assert r"specs/\*.yaml and \_\_pycache\_\_ with \`code\`" in table


def test_render_csv_quotes_fields_that_contain_commas() -> None:
    matrix = _matrix()
    matrix["dimensions"][0]["checks"][0]["title"] = "one, two"

    lines = render_csv(matrix).splitlines()

    assert lines[0] == ",".join(CSV_COLUMNS)
    assert ',"one, two",' in lines[1]


def test_render_checks_table_rejects_unknown_dimension() -> None:
    with pytest.raises(GenerationError, match="Unknown audit dimension 'nope'"):
        render_checks_table(_matrix(), "nope")


def test_csv_content_requires_an_audit_matrix_block(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {"name": "demo", "files": [{"path": "matrix.csv", "content": "audit_matrix:csv"}]},
        "sections": [],
    }

    with pytest.raises(GenerationError, match="audit_matrix:csv needs an audit_matrix block"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_checks_marker_requires_an_audit_matrix_block(tmp_path: Path) -> None:
    spec = {
        "version": "1.0",
        "repo": {
            "name": "demo",
            "files": [
                {
                    "path": "page.md",
                    "inline": "# Page\n\n<!-- audit_matrix:checks data-sovereignty -->\n",
                }
            ],
        },
        "sections": [],
    }

    with pytest.raises(GenerationError, match="needs an audit_matrix block"):
        generate(spec, tmp_path, GenerateOptions(force=False))


def test_checks_marker_expands_in_inline_content_too(tmp_path: Path) -> None:
    spec = load_yaml("specs/kaidf.default.yaml")
    spec["repo"]["files"].append(
        {"path": "matrix.md", "inline": "<!-- audit_matrix:checks deterministic-guardrails -->\n"}
    )

    target = generate(spec, tmp_path / "out", GenerateOptions(force=False))

    page = (target / "matrix.md").read_text(encoding="utf-8")
    assert [row[0] for row in _table_rows(page)] == ["ci-workflows", "blocking-gates"]


def test_generated_scaffold_registers_the_kaidf_audit_skill(tmp_path: Path) -> None:
    import yaml

    target = _generate_default(tmp_path)
    manifest = yaml.safe_load((target / "data/manifests/skills.yaml").read_text(encoding="utf-8"))

    skills = {skill["id"]: skill for skill in manifest["skills"]}
    assert manifest["version"] == "1.0"
    assert skills["kaidf-audit"]["command"] == "kob audit"
    assert skills["kaidf-audit"]["permissions"]["writes"] == "none"
    assert skills["kaidf-audit"]["permissions"]["network"] == "none"
