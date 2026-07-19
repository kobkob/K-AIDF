from __future__ import annotations

import json
import importlib.resources as pkgres
from typing import Any

import jsonschema
from jsonschema import validators

from .errors import SpecValidationError


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
