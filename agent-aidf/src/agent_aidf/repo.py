from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from .index import iter_indexable_paths, load_record, parse_front_matter

# Re-exported for callers that parse front matter directly.
_parse_front_matter = parse_front_matter

# Visibility levels the agent reads. "internal" is the operator's own material, so the local agent
# uses it; "private" is withheld unless the caller asks for it. Anything else is unknown and is
# withheld too, the same fail-closed rule the MCP server applies.
OPERATOR_VISIBILITIES = frozenset({"public", "internal"})


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
    namespace: str | None = None
    doctrine_priority: int = 0


def resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path.cwd().resolve()
    path = Path(repo_root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Repository root does not exist or is not a directory: {path}")
    return path


def load_documents(
    repo_root: str | Path | None = None, *, include_private: bool = False
) -> list[Document]:
    """Load the indexable documents of a repository, leaving out the ones the agent must not read.

    Private and unknown-visibility documents are skipped unless ``include_private`` is true, so
    they never reach search results, the shell, or the LLM context.
    """
    root = resolve_repo_root(repo_root)
    names = {field.name for field in fields(Document)}
    documents: list[Document] = []
    for file_path in iter_indexable_paths(root):
        record = load_record(root, file_path)
        if not include_private and record["visibility"] not in OPERATOR_VISIBILITIES:
            continue
        documents.append(Document(**{name: record[name] for name in names}))
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
