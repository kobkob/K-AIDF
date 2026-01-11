from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import GenerationError
from .schema import validate_spec
from .template_loader import load_template_by_key
from .utils import safe_join, write_text


@dataclass(frozen=True)
class GenerateOptions:
    force: bool = False


def _ensure_empty_or_force(out_dir: Path, force: bool) -> None:
    if out_dir.exists():
        if not out_dir.is_dir():
            raise GenerationError(f"Output path exists and is not a directory: {out_dir}")
        # If non-empty and not forced -> error
        if any(out_dir.iterdir()) and not force:
            raise GenerationError(f"Output directory is not empty: {out_dir} (use --force to overwrite)")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)


def _write_file(out_dir: Path, file_spec: dict[str, Any]) -> None:
    rel_path = file_spec["path"]
    content_spec = file_spec.get("content")
    content_inline = file_spec.get("inline")

    out_path = safe_join(out_dir, rel_path)

    # Determine content
    if content_inline is not None:
        content = str(content_inline)
    elif isinstance(content_spec, str) and content_spec.startswith("library:"):
        key = content_spec.split("library:", 1)[1].strip()
        content = load_template_by_key(key)
    else:
        # Default: empty file
        content = ""

    write_text(out_path, content)


def generate(spec: dict[str, Any], out_dir: str | Path, options: GenerateOptions) -> Path:
    validate_spec(spec)

    out_dir = Path(out_dir)
    _ensure_empty_or_force(out_dir, options.force)

    repo = spec["repo"]
    repo_name = repo.get("name", "kobkob-kaidf")
    # Generate into out_dir/repo_name unless out_dir already points to that folder.
    target = out_dir
    if target.name != repo_name:
        target = out_dir / repo_name

    _ensure_empty_or_force(target, options.force)

    # Root files
    for f in repo.get("files", []):
        _write_file(target, f)

    # Sections
    for section in spec.get("sections", []):
        base = section["path"].rstrip("/") + "/"
        for f in section.get("files", []):
            f2 = dict(f)
            f2["path"] = base + f["path"].lstrip("/")
            _write_file(target, f2)

    return target
