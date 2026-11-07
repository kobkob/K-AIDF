"""Render the KAIDF-AMM matrix documents from a spec's ``audit_matrix`` block.

The block mirrors the ``kob audit`` engine (agent-aidf ``audit.py`` ``DIMENSION_SPECS``), and a
cross-component test in agent-aidf keeps the two identical. Rendering ``audit-matrix.csv`` and the
summary and check table of each dimension page from the block, instead of shipping static copies,
means the generated documents cannot drift from it.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable
from typing import Any

from .errors import GenerationError

CSV_CONTENT_KEY = "audit_matrix:csv"
CSV_COLUMNS = (
    "dimension_id",
    "dimension",
    "check_id",
    "check",
    "points",
    "evidence",
    "status",
    "auditor_notes",
)
# A line of its own in a template, replaced by content rendered from the named dimension.
MARKER = re.compile(
    r"^<!-- audit_matrix:(?P<kind>[a-z_]+) (?P<dimension>[a-z0-9]+(?:-[a-z0-9]+)*) -->$",
    re.MULTILINE,
)
TABLE_HEADER = "| Check | Criterion | Points | Evidence required |\n| --- | --- | --- | --- |"
MARKDOWN_PUNCTUATION = re.compile(r"([\\`*_|])")


def render_csv(matrix: dict[str, Any] | None) -> str:
    """One row per check, ``status`` and ``auditor_notes`` left empty for the auditor."""
    matrix = _require(matrix, CSV_CONTENT_KEY)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for dimension in matrix["dimensions"]:
        for check in dimension["checks"]:
            writer.writerow(
                [
                    dimension["id"],
                    dimension["name"],
                    check["id"],
                    check["title"],
                    check["points"],
                    check["evidence"],
                    "",
                    "",
                ]
            )
    return buffer.getvalue()


def render_summary(matrix: dict[str, Any] | None, dimension_id: str) -> str:
    """The narrative paragraph of one dimension, inserted as written (Markdown allowed)."""
    dimension = _dimension(matrix, dimension_id, "summary")
    summary = str(dimension.get("summary") or "").strip()
    if not summary:
        raise GenerationError(f"Audit dimension {dimension_id!r} has no summary")
    return summary


def render_checks_table(matrix: dict[str, Any] | None, dimension_id: str) -> str:
    """The Markdown check table of one dimension."""
    dimension = _dimension(matrix, dimension_id, "checks")
    rows = [
        f"| `{check['id']}` | {_cell(check['title'])} | {check['points']} "
        f"| {_cell(check['evidence'])} |"
        for check in dimension["checks"]
    ]
    return "\n".join([TABLE_HEADER, *rows])


RENDERERS: dict[str, Callable[[dict[str, Any] | None, str], str]] = {
    "summary": render_summary,
    "checks": render_checks_table,
}


def expand_markers(content: str, matrix: dict[str, Any] | None) -> str:
    """Replace every ``<!-- audit_matrix:<kind> <dimension-id> -->`` line with its rendering."""

    def replace(match: re.Match[str]) -> str:
        kind = match.group("kind")
        renderer = RENDERERS.get(kind)
        if renderer is None:
            known = ", ".join(sorted(RENDERERS))
            raise GenerationError(f"Unknown audit_matrix marker {kind!r} (known: {known})")
        return renderer(matrix, match.group("dimension"))

    return MARKER.sub(replace, content)


def _require(matrix: dict[str, Any] | None, usage: str) -> dict[str, Any]:
    if matrix is None:
        raise GenerationError(f"{usage} needs an audit_matrix block in the spec")
    return matrix


def _dimension(matrix: dict[str, Any] | None, dimension_id: str, kind: str) -> dict[str, Any]:
    matrix = _require(matrix, f"audit_matrix:{kind} {dimension_id}")
    for dimension in matrix["dimensions"]:
        if dimension["id"] == dimension_id:
            return dimension
    known = ", ".join(dimension["id"] for dimension in matrix["dimensions"])
    raise GenerationError(f"Unknown audit dimension {dimension_id!r} (spec has: {known})")


def _cell(text: str) -> str:
    """Escape what would break the table or read as Markdown emphasis or code."""
    return MARKDOWN_PUNCTUATION.sub(r"\\\1", text)
