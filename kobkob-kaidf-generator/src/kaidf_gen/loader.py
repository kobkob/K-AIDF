from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import KaidfGenError, SpecParsingError


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise KaidfGenError(f"Spec file not found: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise SpecParsingError(f"Spec file is not valid UTF-8: {p}") from exc
    except yaml.YAMLError as exc:
        problem = _yaml_problem(exc)
        raise SpecParsingError(f"Malformed YAML in {p}{_yaml_location(exc)}: {problem}") from exc
    if not isinstance(data, dict):
        raise SpecParsingError("Spec root must be a mapping/object.")
    return data


def _yaml_location(exc: yaml.YAMLError) -> str:
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return ""
    return f" (line {mark.line + 1}, column {mark.column + 1})"


def _yaml_problem(exc: yaml.YAMLError) -> str:
    return getattr(exc, "problem", None) or str(exc).splitlines()[0]
