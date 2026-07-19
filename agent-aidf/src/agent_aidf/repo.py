from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

INDEXABLE_ROOT_FILES = {"README.md", "MANIFESTO.md"}
INDEXABLE_SUFFIXES = {".md", ".csv"}
CANONICAL_DOCTRINE_FILES = {
    "docs/00-overview/manifesto.md": "manifesto",
    "docs/00-overview/principles.md": "principles",
    "docs/00-overview/best-practices.md": "best-practices",
    "docs/00-overview/governance.md": "governance",
    "docs/00-overview/maturity.md": "maturity",
    "docs/00-overview/implementation.md": "implementation",
    "MANIFESTO.md": "manifesto",
}
STARTER_VARIANT_DOMAINS = {
    "docs/00-overview/best-practices/seo.md": "seo",
    "docs/00-overview/best-practices/content.md": "content",
    "docs/00-overview/best-practices/research.md": "research",
}


@dataclass(frozen=True)
class Document:
    id: str
    path: str
    title: str
    document_class: str
    phase: str
    visibility: str
    status: str
    doctrine_category: str
    canonical_doctrine: bool
    variant_domain: str | None
    pack: str | None
    maturity_level: str | None
    assessment_type: str | None
    ethical_domain: str | None
    control_type: str | None
    risk_type: str | None
    content: str
    body: str


def resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path.cwd().resolve()
    path = Path(repo_root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Repository root does not exist or is not a directory: {path}")
    return path


def _is_indexable(rel_path: str) -> bool:
    path = PurePosixPath(rel_path)
    if rel_path in INDEXABLE_ROOT_FILES:
        return True
    if not rel_path.startswith("docs/"):
        return False
    return path.suffix in INDEXABLE_SUFFIXES


def _iter_indexable_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(root).as_posix()
        if _is_indexable(rel_path):
            paths.append(file_path)
    return sorted(paths)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
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


def _first_heading(markdown_body: str) -> str | None:
    for line in markdown_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            return title or None
    return None


def _infer_document_class(rel_path: str) -> str:
    path = PurePosixPath(rel_path)
    if rel_path in {"LICENSE", "CODEOWNERS", "SECURITY.md"}:
        return "governance-doc"
    if "templates" in path.parts:
        return "template-doc"
    if rel_path.endswith(".prompt.md") or "prompts" in path.parts:
        return "prompt-doc"
    return "core-doc"


def _infer_phase(rel_path: str) -> str:
    if rel_path == "README.md":
        return "root"
    parts = PurePosixPath(rel_path).parts
    if len(parts) >= 2 and parts[0] == "docs":
        return parts[1]
    return "root"


def _infer_doctrine_category(rel_path: str, title: str, body: str) -> str:
    if rel_path in CANONICAL_DOCTRINE_FILES:
        return CANONICAL_DOCTRINE_FILES[rel_path]
    text = "\n".join([rel_path, title, body]).casefold()
    if "principles" in text or "principles" in rel_path:
        return "principles"
    if "best practice" in text or "best practices" in text:
        return "best-practices"
    if "governance" in text or "decision-rights" in text:
        return "governance"
    if "maturity" in text:
        return "maturity"
    if "implementation" in text:
        return "implementation"
    if "training" in text or "certification" in text:
        return "training"
    return "general"


def load_documents(repo_root: str | Path | None = None) -> list[Document]:
    root = resolve_repo_root(repo_root)
    documents: list[Document] = []
    for file_path in _iter_indexable_paths(root):
        rel_path = file_path.relative_to(root).as_posix()
        raw_text = file_path.read_text(encoding="utf-8")
        front_matter, body = _parse_front_matter(raw_text) if file_path.suffix == ".md" else ({}, raw_text)
        title = front_matter.get("title") or _first_heading(body) or file_path.stem
        documents.append(
            Document(
                id=front_matter.get("id", rel_path),
                path=rel_path,
                title=title,
                document_class=front_matter.get("document_class", _infer_document_class(rel_path)),
                phase=front_matter.get("phase", _infer_phase(rel_path)),
                visibility=front_matter.get("visibility", "internal"),
                status=front_matter.get("status", "active"),
                doctrine_category=_infer_doctrine_category(rel_path, title, body),
                canonical_doctrine=rel_path in CANONICAL_DOCTRINE_FILES,
                variant_domain=STARTER_VARIANT_DOMAINS.get(rel_path),
                pack=front_matter.get("pack"),
                maturity_level=front_matter.get("maturity_level"),
                assessment_type=front_matter.get("assessment_type"),
                ethical_domain=front_matter.get("ethical_domain"),
                control_type=front_matter.get("control_type"),
                risk_type=front_matter.get("risk_type"),
                content=raw_text,
                body=body,
            )
        )
    return documents


def filter_documents(
    documents: list[Document],
    *,
    pack: str | None = None,
    phase: str | None = None,
    ethical_domain: str | None = None,
    maturity_level: str | None = None,
    assessment_type: str | None = None,
    risk_type: str | None = None,
) -> list[Document]:
    filtered = documents
    if pack:
        filtered = [doc for doc in filtered if doc.pack == pack]
    if phase:
        filtered = [doc for doc in filtered if doc.phase == phase]
    if ethical_domain:
        filtered = [doc for doc in filtered if doc.ethical_domain == ethical_domain]
    if maturity_level:
        filtered = [doc for doc in filtered if doc.maturity_level == maturity_level]
    if assessment_type:
        filtered = [doc for doc in filtered if doc.assessment_type == assessment_type]
    if risk_type:
        filtered = [doc for doc in filtered if doc.risk_type == risk_type]
    return filtered


def find_documents(documents: list[Document], query: str) -> list[Document]:
    query_norm = query.strip().casefold()
    if not query_norm:
        return []
    query_terms = [term for term in query_norm.replace("-", " ").split() if len(term) >= 3]
    matches: list[Document] = []
    for doc in documents:
        haystack = "\n".join(
            [
                doc.id,
                doc.path,
                doc.title,
                doc.doctrine_category,
                doc.pack or "",
                doc.ethical_domain or "",
                doc.maturity_level or "",
                doc.assessment_type or "",
                doc.risk_type or "",
                doc.body,
            ]
        ).casefold()
        if query_norm in haystack or any(term in haystack for term in query_terms):
            matches.append(doc)
    return matches


def get_document(documents: list[Document], ref: str) -> Document | None:
    for doc in documents:
        if doc.id == ref or doc.path == ref:
            return doc
    return None


def list_packs(documents: list[Document]) -> list[str]:
    return sorted({doc.pack for doc in documents if doc.pack})
