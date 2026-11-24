"""kob scan registers detected apps by reference: a manifest that points at the project's file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_aidf.instant_apps import get_instant_app, list_instant_apps
from agent_aidf.scan import compute, extract, write_outputs


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "apps" / "notes").mkdir(parents=True)
    (root / "apps" / "notes" / "main.py").write_text('print("notes")\n', encoding="utf-8")
    (root / ".kaidf").mkdir()
    return root


def _write(project: Path) -> None:
    plan = extract(project, project / ".kaidf")
    compute(plan, project / ".kaidf")
    write_outputs(plan, project / ".kaidf")


def test_a_detected_app_gets_a_manifest_that_points_at_the_project_file(project: Path) -> None:
    _write(project)

    manifest = project / ".kaidf" / "apps" / "notes" / "app.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert data["kind"] == "shell"
    assert data["mode"] == "persistent"
    app = get_instant_app(project / ".kaidf", "notes")
    assert app is not None
    assert app.entrypoint.resolve() == (project / "apps" / "notes" / "main.py").resolve()
    assert [item.app_id for item in list_instant_apps(project / ".kaidf")] == ["notes"]


def test_no_source_is_copied_into_the_registry(project: Path) -> None:
    _write(project)

    registry = project / ".kaidf" / "apps" / "notes"
    assert not (registry / "main.py").exists()
    assert sorted(path.name for path in registry.iterdir()) == ["app.json"]


def test_an_existing_manifest_is_never_overwritten(project: Path) -> None:
    registry = project / ".kaidf" / "apps" / "notes"
    registry.mkdir(parents=True)
    edited = {
        "app_id": "notes",
        "mode": "persistent",
        "kind": "shell",
        "title": "Mine",
        "description": "Edited by the operator.",
        "entrypoint": "main.py",
        "url": None,
    }
    (registry / "app.json").write_text(json.dumps(edited), encoding="utf-8")

    _write(project)

    assert json.loads((registry / "app.json").read_text(encoding="utf-8"))["title"] == "Mine"
