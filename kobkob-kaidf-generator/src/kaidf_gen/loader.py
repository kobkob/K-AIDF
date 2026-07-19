from __future__ import annotations

from typing import Any
from pathlib import Path

import yaml

from .errors import KaidfGenError


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise KaidfGenError(f"Spec file not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise KaidfGenError("Spec root must be a mapping/object.")
    return data
