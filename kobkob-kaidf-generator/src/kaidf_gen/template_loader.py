from __future__ import annotations

import importlib.resources as pkgres
from pathlib import Path

from .errors import TemplateNotFoundError
from .utils import safe_join

LIB_ROOT = "kaidf_gen.templates.library"


def list_library_keys() -> list[str]:
    keys: list[str] = []
    with pkgres.as_file(pkgres.files(LIB_ROOT)) as libdir:
        for p in Path(libdir).rglob("*"):
            if p.is_file():
                # key format: relative path without extension group
                # e.g., templates/ICB.md -> template:templates/ICB.md
                rel = p.relative_to(libdir).as_posix()
                keys.append(rel)
    return sorted(keys)


def load_template_by_key(key: str) -> str:
    """Load a template from the packaged library by relative path key.

    Raises UnsafePathError when the key resolves outside the library (e.g. ``../`` segments).
    """
    key = key.lstrip("/").replace("\\", "/")
    with pkgres.as_file(pkgres.files(LIB_ROOT)) as libdir:
        path = safe_join(Path(libdir), key)
        if not path.is_file():
            raise TemplateNotFoundError(f"Template key not found in library: {key}")
        return path.read_text(encoding="utf-8")
