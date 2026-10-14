from __future__ import annotations

import importlib.resources as pkgres
import json
from typing import Any

import jsonschema
from jsonschema import validators

from .errors import SpecValidationError
from .utils import normalize_rel_path

SCHEMA_PKG = "kaidf_gen.schemas"
SCHEMA_FILE = "kaidf-spec.schema.json"


def load_schema() -> dict[str, Any]:
    schema_path = pkgres.files(SCHEMA_PKG).joinpath(SCHEMA_FILE)
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_spec(spec: dict[str, Any]) -> None:
    schema = load_schema()
    validator_cls = validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    try:
        validator.validate(spec)
    except jsonschema.ValidationError as e:
        path = ".".join([str(p) for p in e.absolute_path]) if e.absolute_path else "<root>"
        raise SpecValidationError(f"Spec validation error at {path}: {e.message}") from e
    _check_duplicate_paths(spec)


def _output_paths(spec: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (output path, where it is declared) for every file the spec would write."""
    entries: list[tuple[str, str]] = []
    for f in spec["repo"].get("files", []):
        entries.append((normalize_rel_path(f["path"]), "repo.files"))
    for index, section in enumerate(spec.get("sections", [])):
        base = section["path"].rstrip("/") + "/"
        for f in section.get("files", []):
            full = normalize_rel_path(base + f["path"].lstrip("/"))
            entries.append((full, f"sections[{index}] ({section['path']})"))
    return entries


def _check_duplicate_paths(spec: dict[str, Any]) -> None:
    seen: dict[str, str] = {}
    for path, where in _output_paths(spec):
        if path in seen:
            raise SpecValidationError(
                f"Duplicate output path {path!r}: declared in {seen[path]} and again in {where}"
            )
        seen[path] = where
