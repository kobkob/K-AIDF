from __future__ import annotations

import json
import importlib.resources as pkgres
from typing import Any

import jsonschema

from .errors import SpecValidationError


SCHEMA_PKG = "kaidf_gen.schemas"
SCHEMA_FILE = "kaidf-spec.schema.json"


def load_schema() -> dict[str, Any]:
    with pkgres.open_text(SCHEMA_PKG, SCHEMA_FILE, encoding="utf-8") as f:
        return json.load(f)


def validate_spec(spec: dict[str, Any]) -> None:
    schema = load_schema()
    try:
        jsonschema.validate(instance=spec, schema=schema)
    except jsonschema.ValidationError as e:
        path = ".".join([str(p) for p in e.absolute_path]) if e.absolute_path else "<root>"
        raise SpecValidationError(f"Spec validation error at {path}: {e.message}") from e
