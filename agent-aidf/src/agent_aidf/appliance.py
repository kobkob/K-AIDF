"""Appliance bootstrap from notebooks: `kob appliance init --from-notebook <file.ipynb>`.

A K-AIDF Appliance Notebook carries its workspace settings in a cell tagged `kaidf-config`. The tag
is set in the cell's metadata (in JupyterLab: Cell Tags; in Colab and Kaggle: the same tag in the
cell metadata). That cell holds one fenced YAML block:

    ```yaml
    project_name: acme-pilot
    model: local-quantized        # optional label, recorded only
    audit_fail_under: 80          # 0-100
    ```

The notebook's first Markdown heading is its title. Only the tagged cell is read. No cell is
executed, and the notebook is never run to find its settings.

`init` makes sure `.kaidf/` exists (running `kob init` when it does not), then writes the settings
and the notebook's name, title and SHA-256 to `.kaidf/appliance.yaml`. An existing `.kaidf/` is
kept, unless `--force` is given. Secrets are refused: a notebook must not carry API keys, so they
come from the environment at run time.

`template` writes a starter notebook that runs on Google Colab, Kaggle and JupyterLab.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .project import init_project_repo, project_repo_root, resolve_project_root

CONFIG_TAG = "kaidf-config"
APPLIANCE_RECORD = "appliance.yaml"
RECORD_SCHEMA = 1
TEMPLATE_TITLE = "K-AIDF Appliance"

# The only settings a notebook may set. Anything else is refused, so a typo cannot pass silently.
_SETTING_RULES: dict[str, str] = {
    "project_name": "text",
    "model": "text",
    "audit_fail_under": "score",
}
_SECRET_HINTS = ("key", "token", "secret", "password", "credential")
_PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_FENCED_YAML = re.compile(r"```ya?ml[ \t]*\n(.*?)\n```", re.DOTALL)


class ApplianceError(ValueError):
    """The notebook, its settings, or the target workspace cannot be used as requested."""


@dataclass(frozen=True)
class NotebookBootstrap:
    notebook_name: str
    notebook_sha256: str
    title: str | None
    settings: dict


@dataclass(frozen=True)
class ApplianceResult:
    repo_root: Path
    record_path: Path
    created_workspace: bool
    bootstrap: NotebookBootstrap


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _first_heading(cells: list[dict]) -> str | None:
    for cell in cells:
        if cell.get("cell_type") != "markdown":
            continue
        for line in _cell_text(cell).splitlines():
            if line.startswith("# "):
                return line[2:].strip() or None
    return None


def _validate_settings(raw: object) -> dict:
    if raw is None:
        raise ApplianceError("the kaidf-config cell has an empty YAML block")
    if not isinstance(raw, dict):
        raise ApplianceError("the kaidf-config YAML must be a mapping of setting names to values")
    settings: dict = {}
    for key, value in raw.items():
        if not isinstance(key, str) or key not in _SETTING_RULES:
            lowered = str(key).lower()
            if any(hint in lowered for hint in _SECRET_HINTS):
                raise ApplianceError(
                    f"{key!r} looks like a secret. Do not store secrets in a notebook; set it "
                    "as an environment variable for the session instead"
                )
            allowed = ", ".join(sorted(_SETTING_RULES))
            raise ApplianceError(f"unknown setting {key!r}; allowed settings: {allowed}")
        rule = _SETTING_RULES[key]
        if rule == "text":
            if not isinstance(value, str) or not value.strip() or "\n" in value:
                raise ApplianceError(f"{key} must be a single line of text")
            if key == "project_name" and not _PROJECT_NAME.match(value.strip()):
                raise ApplianceError(
                    "project_name may use letters, digits, '.', '_' and '-' (max 100 characters)"
                )
            if key == "model" and len(value) > 200:
                raise ApplianceError("model must be at most 200 characters")
            settings[key] = value.strip()
        else:  # score
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ApplianceError("audit_fail_under must be an integer from 0 to 100")
            settings[key] = value
    return settings


def parse_notebook(path: Path) -> NotebookBootstrap:
    """Read the bootstrap settings from a notebook file without executing anything in it."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ApplianceError(f"cannot read notebook {path}: {exc}") from exc
    try:
        notebook = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApplianceError(f"{path.name} is not a valid notebook (JSON): {exc}") from exc
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        raise ApplianceError(f"{path.name} is not a notebook: no cells list")
    if not isinstance(notebook.get("nbformat"), int) or notebook["nbformat"] < 4:
        raise ApplianceError(f"{path.name} must be an nbformat 4 notebook")

    cells = [cell for cell in notebook["cells"] if isinstance(cell, dict)]
    tagged = [
        cell for cell in cells if CONFIG_TAG in (cell.get("metadata", {}) or {}).get("tags", [])
    ]
    if not tagged:
        raise ApplianceError(f"{path.name} has no cell tagged {CONFIG_TAG!r}")
    if len(tagged) > 1:
        raise ApplianceError(f"{path.name} has {len(tagged)} cells tagged {CONFIG_TAG!r}; use one")

    fence = _FENCED_YAML.search(_cell_text(tagged[0]))
    if fence is None:
        raise ApplianceError(f"the {CONFIG_TAG!r} cell needs a fenced ```yaml block")
    try:
        parsed = yaml.safe_load(fence.group(1))
    except yaml.YAMLError as exc:
        raise ApplianceError(f"the {CONFIG_TAG!r} YAML is invalid: {exc}") from exc

    return NotebookBootstrap(
        notebook_name=path.name,
        notebook_sha256=hashlib.sha256(raw).hexdigest(),
        title=_first_heading(cells),
        settings=_validate_settings(parsed),
    )


def apply_notebook(
    notebook: Path, project_root: str | Path | None = None, *, force: bool = False
) -> ApplianceResult:
    """Configure the project's .kaidf/ workspace from a notebook's settings."""
    bootstrap = parse_notebook(notebook)
    project = resolve_project_root(project_root)
    target = project_repo_root(project)

    created = False
    if not target.exists() or force:
        init_project_repo(project, force=force)
        created = True
    elif not target.is_dir():
        raise ApplianceError(f"{target} exists and is not a directory")

    record = {
        "schema": RECORD_SCHEMA,
        "notebook": {
            "name": bootstrap.notebook_name,
            "title": bootstrap.title,
            "sha256": bootstrap.notebook_sha256,
        },
        "settings": bootstrap.settings,
    }
    record_path = target / APPLIANCE_RECORD
    header = "# Written by `kob appliance init --from-notebook`. Re-run the command to change it.\n"
    record_path.write_text(
        header + yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return ApplianceResult(
        repo_root=target,
        record_path=record_path,
        created_workspace=created,
        bootstrap=bootstrap,
    )


# --- Template generator -------------------------------------------------------------------------

_TEMPLATE_CONFIG = """\
```yaml
project_name: my-kaidf-project
# model: optional label, recorded in .kaidf/appliance.yaml
audit_fail_under: 80
```"""


def _source(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _markdown(cell_id: str, text: str, tags: list[str] | None = None) -> dict:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {"tags": tags} if tags else {},
        "source": _source(text),
    }


def _code(cell_id: str, text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {},
        "outputs": [],
        "source": _source(text),
    }


def build_template(notebook_filename: str) -> dict:
    """A starter Appliance Notebook (nbformat 4.5) for Colab, Kaggle and JupyterLab."""
    cells = [
        _markdown(
            "kaidf-intro",
            f"# {TEMPLATE_TITLE}\n\n"
            "Bootstraps a K-AIDF workspace (`.kaidf/`) and prints its audit report. "
            "Runs on Google Colab, Kaggle and JupyterLab.\n\n"
            "1. Edit the configuration cell below.\n"
            "2. Run all cells.\n\n"
            "Do not put API keys in this notebook. Set them as environment variables for the "
            "session.",
        ),
        _code(
            "kaidf-install",
            "# Installs the CLI. Needs internet access in the runtime.\n"
            "!pip install -q agent-aidf\n",
        ),
        _markdown(
            "kaidf-config-help",
            "## Configuration\n\nThe cell below is read by `kob appliance init`. Only these "
            "settings are accepted: `project_name`, `model`, `audit_fail_under`.",
        ),
        _markdown("kaidf-config", _TEMPLATE_CONFIG, tags=[CONFIG_TAG]),
        _code(
            "kaidf-init",
            f'!kob appliance init --from-notebook "{notebook_filename}"\n',
        ),
        _code(
            "kaidf-audit",
            "# Express diagnostic: the KAIDF-AMM audit as JSON.\n!kob audit --json\n",
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_template(out: Path, *, force: bool = False) -> Path:
    if out.exists() and not force:
        raise ApplianceError(f"{out} already exists; pass --force to overwrite it")
    out.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_template(out.name)
    out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


__all__ = [
    "APPLIANCE_RECORD",
    "CONFIG_TAG",
    "ApplianceError",
    "ApplianceResult",
    "NotebookBootstrap",
    "apply_notebook",
    "build_template",
    "parse_notebook",
    "write_template",
]
