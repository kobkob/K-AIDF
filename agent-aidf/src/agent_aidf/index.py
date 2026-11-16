"""Document index rules shared by agent-aidf and mcp-aidf.

Both components read the same repository the same way: which files are indexable, how front
matter is parsed, how a document is classified (doctrine category, phase, variant) and how its
metadata fields are normalised. Those rules live here once, so `kob` and the MCP server rank and
filter the same documents. The search itself (ranking, query matching, visibility filtering) stays
with each component. The shared index contract in `contracts/index-contract` checks the output.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import yaml

INDEXABLE_ROOT_FILES = {"README.md", "MANIFESTO.md"}
INDEXABLE_SUFFIXES = {".md", ".csv"}
# Doctrine stays under docs/00-overview/ here: the shared index contract
# (contracts/index-contract) and the generated repositories use that layout. The workspace's own
# docs/ tree is organised in numbered sections (01-basics ... 06-deploy); those are indexed like
# any other document, with the section as their phase.
CANONICAL_DOCTRINE_FILES = {
    "docs/00-overview/manifesto.md": "manifesto",
    "docs/00-overview/principles.md": "principles",
    "docs/00-overview/best-practices.md": "best-practices",
    "docs/00-overview/governance.md": "governance",
    "docs/00-overview/maturity.md": "maturity",
    "docs/00-overview/implementation.md": "implementation",
    "MANIFESTO.md": "manifesto",
}
DOCTRINE_PRIORITY = {
    "manifesto": 1000,
    "principles": 900,
    "governance": 800,
    "best-practices": 700,
    "maturity": 600,
    "implementation": 500,
    "training": 400,
    "general": 100,
}
STARTER_VARIANT_DOMAINS = {
    "docs/00-overview/best-practices/seo.md": "seo",
    "docs/00-overview/best-practices/content.md": "content",
    "docs/00-overview/best-practices/research.md": "research",
}
# The visibility a document has when its front matter does not say.
DEFAULT_VISIBILITY = "internal"


def is_indexable(rel_path: str) -> bool:
    path = PurePosixPath(rel_path)
    if rel_path in INDEXABLE_ROOT_FILES:
        return True
    if not rel_path.startswith("docs/"):
        return False
    return path.suffix in INDEXABLE_SUFFIXES


def iter_indexable_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(root).as_posix()
        if is_indexable(rel_path):
            paths.append(file_path)
    return sorted(paths)


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    # Windows checkouts can keep CRLF line endings; normalize so the "---" markers still match.
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    marker = "\n---\n"
    end = text.find(marker, 4)
    if end == -1:
        return {}, text
    front_matter_text = text[4:end]
    body = text[end + len(marker) :]
    data = yaml.safe_load(front_matter_text) or {}
    if not isinstance(data, dict):
        return {}, text
    return data, body


def first_heading(markdown_body: str) -> str | None:
    for line in markdown_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def infer_document_class(rel_path: str) -> str:
    path = PurePosixPath(rel_path)
    if rel_path in {"LICENSE", "CODEOWNERS", "SECURITY.md"}:
        return "governance-doc"
    if "templates" in path.parts:
        return "template-doc"
    if rel_path.endswith(".prompt.md") or "prompts" in path.parts:
        return "prompt-doc"
    return "core-doc"


def infer_phase(rel_path: str) -> str:
    # A document inside a section directory (docs/<section>/...) takes the section as its phase.
    # Files directly under docs/ (for example the docs/README.md index) and root files are "root".
    parts = PurePosixPath(rel_path).parts
    if len(parts) >= 3 and parts[0] == "docs":
        return parts[1]
    return "root"


def infer_doctrine_category(rel_path: str, title: str, body: str) -> str:
    if rel_path in CANONICAL_DOCTRINE_FILES:
        return CANONICAL_DOCTRINE_FILES[rel_path]
    text = "\n".join([rel_path, title, body]).casefold()
    if "principles" in text or "princípios" in text or "principios" in text:
        return "principles"
    if "boas práticas" in text or "best practice" in text or "best practices" in text:
        return "best-practices"
    if "governança" in text or "governance" in text or "decision-rights" in text:
        return "governance"
    if "maturidade" in text or "maturity" in text:
        return "maturity"
    if "implementação" in text or "implementation" in text:
        return "implementation"
    if (
        "treinamento" in text
        or "training" in text
        or "certificação" in text
        or "certification" in text
    ):
        return "training"
    return "general"


def doctrine_priority(category: str) -> int:
    return DOCTRINE_PRIORITY.get(category, 0)


def string_field(front_matter: dict[str, Any], key: str) -> str | None:
    """A metadata field as a stripped string; blank or non-string values count as absent."""
    value = front_matter.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def load_record(root: Path, file_path: Path) -> dict[str, Any]:
    """The index record of one document: every field both components search and filter on."""
    rel_path = file_path.relative_to(root).as_posix()
    raw_text = file_path.read_text(encoding="utf-8")
    front_matter, body = (
        parse_front_matter(raw_text) if file_path.suffix == ".md" else ({}, raw_text)
    )
    title = front_matter.get("title") or first_heading(body) or file_path.stem
    doctrine_category = infer_doctrine_category(rel_path, title, body)
    return {
        "id": front_matter.get("id", rel_path),
        "path": rel_path,
        "title": title,
        "document_class": front_matter.get("document_class", infer_document_class(rel_path)),
        "phase": front_matter.get("phase", infer_phase(rel_path)),
        # Kept as written: an unknown value stays unknown, and each component fails closed on it.
        "visibility": front_matter.get("visibility", DEFAULT_VISIBILITY),
        "namespace": string_field(front_matter, "namespace"),
        "status": front_matter.get("status", "active"),
        "doctrine_category": doctrine_category,
        "canonical_doctrine": rel_path in CANONICAL_DOCTRINE_FILES,
        "doctrine_priority": doctrine_priority(doctrine_category),
        "variant_domain": STARTER_VARIANT_DOMAINS.get(rel_path),
        "pack": string_field(front_matter, "pack"),
        "maturity_level": string_field(front_matter, "maturity_level"),
        "assessment_type": string_field(front_matter, "assessment_type"),
        "ethical_domain": string_field(front_matter, "ethical_domain"),
        "control_type": string_field(front_matter, "control_type"),
        "risk_type": string_field(front_matter, "risk_type"),
        "content": raw_text,
        "body": body,
    }
