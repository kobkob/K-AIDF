"""Run the K-AIDF generator in-process, for `kob init` and `kob compile`.

The generator (`kaidf_gen`, from kobkob-kaidf-generator) is found in this order:

1. an installed `kaidf_gen` package (pip install of kobkob-kaidf-generator);
2. the checkout named by the KAIDF_GENERATOR_DIR environment variable (its `src/` directory is
   put on sys.path). This is the explicit development override.

Nothing is located by relative path to the workspace, and nothing is installed or bootstrapped at
runtime: a missing generator is one error that says how to provide it.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

GENERATOR_DIR_ENV = "KAIDF_GENERATOR_DIR"
DEFAULT_SPEC_NAME = "kaidf.default.yaml"


class GeneratorUnavailableError(RuntimeError):
    """The generator cannot be imported. The message says how to make it available."""


class GeneratorError(RuntimeError):
    """The generator ran and refused the spec or could not write the output."""


def _import_generator() -> Any:
    try:
        return importlib.import_module("kaidf_gen")
    except ImportError:
        pass
    override = os.environ.get(GENERATOR_DIR_ENV, "").strip()
    if not override:
        raise GeneratorUnavailableError(
            "The K-AIDF generator is not installed. Install kobkob-kaidf-generator, or set "
            f"{GENERATOR_DIR_ENV} to its checkout."
        )
    src = Path(override).expanduser() / "src"
    if not (src / "kaidf_gen" / "__init__.py").is_file():
        raise GeneratorUnavailableError(
            f"{GENERATOR_DIR_ENV}={override} does not contain src/kaidf_gen. Point it at the "
            "kobkob-kaidf-generator checkout."
        )
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    importlib.invalidate_caches()
    try:
        return importlib.import_module("kaidf_gen")
    except ImportError as exc:
        raise GeneratorUnavailableError(
            f"Could not import kaidf_gen from {src}: {exc}. Install its dependencies (PyYAML, "
            "jsonschema) in this Python."
        ) from exc


def default_spec_path() -> Path:
    """The default spec, shipped inside the generator package."""
    package = _import_generator()
    spec = Path(package.__file__).resolve().parent / "specs" / DEFAULT_SPEC_NAME
    if not spec.is_file():
        raise GeneratorUnavailableError(
            f"The generator at {spec.parent.parent} has no {DEFAULT_SPEC_NAME}. Update "
            "kobkob-kaidf-generator to a version that ships it."
        )
    return spec


def generate_repo(spec_path: Path, out_dir: Path, *, force: bool) -> Path:
    """Generate the repository described by `spec_path` into `out_dir`. Returns the repo root."""
    _import_generator()
    from kaidf_gen.errors import KaidfGenError
    from kaidf_gen.generator import GenerateOptions, generate
    from kaidf_gen.loader import load_yaml

    try:
        spec = load_yaml(spec_path)
        return generate(spec, out_dir, GenerateOptions(force=force))
    except KaidfGenError as exc:
        raise GeneratorError(str(exc)) from exc
