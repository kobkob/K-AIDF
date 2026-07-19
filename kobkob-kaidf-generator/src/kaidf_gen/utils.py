from __future__ import annotations

import os
from pathlib import Path

from .errors import UnsafePathError


def safe_join(root: Path, rel: str) -> Path:
    """Join root + rel and prevent path traversal."""
    # Normalize separators
    rel = rel.replace('\\', '/')
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise UnsafePathError(f"Unsafe path (escapes output dir): {rel}") from e
    return candidate


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding='utf-8')


def write_bytes(path: Path, content: bytes) -> None:
    ensure_parent(path)
    path.write_bytes(content)
