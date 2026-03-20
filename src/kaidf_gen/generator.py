from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import GenerationError
from .schema import validate_spec
from .template_loader import load_template_by_key
from .utils import safe_join, write_text


@dataclass(frozen=True)
class GenerateOptions:
    force: bool = False


FRONT_MATTER_FIELDS = ("id", "title", "document_class", "phase", "visibility", "status")


def _ensure_empty_or_force(out_dir: Path, force: bool) -> None:
    if out_dir.exists():
        if not out_dir.is_dir():
            raise GenerationError(f"Output path exists and is not a directory: {out_dir}")
        # If non-empty and not forced -> error
        if any(out_dir.iterdir()) and not force:
            raise GenerationError(f"Output directory is not empty: {out_dir} (use --force to overwrite)")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)


def _resolve_content(file_spec: dict[str, Any]) -> str:
    content_spec = file_spec.get("content")
    content_inline = file_spec.get("inline")

    if content_inline is not None:
        return str(content_inline)
    if isinstance(content_spec, str) and content_spec.startswith("library:"):
        key = content_spec.split("library:", 1)[1].strip()
        return load_template_by_key(key)
    return ""


def _resolve_front_matter(
    rel_path: str,
    repo_metadata_defaults: dict[str, Any],
    section_metadata_defaults: dict[str, Any],
    file_spec: dict[str, Any],
) -> dict[str, Any]:
    front_matter: dict[str, Any] = {}
    front_matter.update(repo_metadata_defaults)
    front_matter.update(section_metadata_defaults)
    front_matter.update(file_spec.get("front_matter") or {})

    if not front_matter:
        return {}

    if not rel_path.endswith(".md"):
        raise GenerationError(f"Front matter is only supported for markdown files: {rel_path}")

    missing = [field for field in FRONT_MATTER_FIELDS if field not in front_matter]
    if missing:
        raise GenerationError(f"Missing front matter fields for {rel_path}: {', '.join(missing)}")

    return {field: front_matter[field] for field in FRONT_MATTER_FIELDS}


def _render_front_matter(front_matter: dict[str, Any]) -> str:
    if not front_matter:
        return ""
    body = yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=False).strip()
    return f"---\n{body}\n---\n\n"


def _write_file(
    out_dir: Path,
    file_spec: dict[str, Any],
    repo_metadata_defaults: dict[str, Any],
    section_metadata_defaults: dict[str, Any],
) -> None:
    rel_path = file_spec["path"]
    out_path = safe_join(out_dir, rel_path)
    front_matter = _resolve_front_matter(rel_path, repo_metadata_defaults, section_metadata_defaults, file_spec)
    content = _render_front_matter(front_matter) + _resolve_content(file_spec)

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
    repo_metadata_defaults = repo.get("metadata_defaults") or {}

    # Root files
    for f in repo.get("files", []):
        _write_file(target, f, repo_metadata_defaults, {})

    # Sections
    for section in spec.get("sections", []):
        base = section["path"].rstrip("/") + "/"
        section_metadata_defaults = section.get("metadata_defaults") or {}
        for f in section.get("files", []):
            f2 = dict(f)
            f2["path"] = base + f["path"].lstrip("/")
            _write_file(target, f2, repo_metadata_defaults, section_metadata_defaults)

    return target
