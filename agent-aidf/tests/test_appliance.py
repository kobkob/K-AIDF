from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path

import pytest
import yaml

from agent_aidf import appliance
from agent_aidf.appliance import (
    ApplianceError,
    apply_notebook,
    build_template,
    parse_notebook,
    write_template,
)

cli_main = importlib.import_module("agent_aidf.cli.main")

CONFIG_TAGS = ["kaidf-config"]


def _md(text: str, tags: list[str] | None = None) -> dict:
    cell = {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}
    if tags:
        cell["metadata"]["tags"] = tags
    return cell


def _code(text: str, tags: list[str] | None = None) -> dict:
    cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }
    if tags:
        cell["metadata"]["tags"] = tags
    return cell


def _config(yaml_text: str) -> dict:
    return _md("## Config\n\n```yaml\n" + yaml_text + "\n```", tags=CONFIG_TAGS)


def _write_notebook(path: Path, cells: list[dict], nbformat: int = 4) -> Path:
    notebook = {
        "cells": cells,
        "metadata": {},
        "nbformat": nbformat,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
    return path


@pytest.fixture
def nb_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "notebooks"
    directory.mkdir()
    return directory


@pytest.fixture
def project(tmp_path: Path) -> Path:
    directory = tmp_path / "project"
    directory.mkdir()
    return directory


@pytest.fixture
def fake_init(monkeypatch):
    """Stand in for `kob init`, which needs the generator checkout. Records each call."""
    calls: list[dict] = []

    def fake(project_root, *, force: bool = False) -> Path:
        calls.append({"project_root": Path(project_root), "force": force})
        target = Path(project_root) / ".kaidf"
        if target.exists():
            import shutil

            shutil.rmtree(target)
        target.mkdir()
        (target / "README.md").write_text("# scaffold\n", encoding="utf-8")
        return target

    monkeypatch.setattr(appliance, "init_project_repo", fake)
    return calls


def test_parses_settings_title_and_digest(nb_dir: Path) -> None:
    path = _write_notebook(
        nb_dir / "pilot.ipynb",
        [
            _md("# Pilot notebook\n\nIntro."),
            _config("project_name: acme-pilot\nmodel: local-quantized\naudit_fail_under: 80"),
        ],
    )

    parsed = parse_notebook(path)

    assert parsed.notebook_name == "pilot.ipynb"
    assert parsed.title == "Pilot notebook"
    assert parsed.settings == {
        "project_name": "acme-pilot",
        "model": "local-quantized",
        "audit_fail_under": 80,
    }
    assert parsed.notebook_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_reads_only_the_tagged_cell_and_never_runs_code(nb_dir: Path, tmp_path: Path) -> None:
    sentinel = tmp_path / "ran.txt"
    path = _write_notebook(
        nb_dir / "trap.ipynb",
        [
            _code(f"open({str(sentinel)!r}, 'w').write('ran')"),
            _md("```yaml\nproject_name: ignored-here\n```"),
            _config("project_name: real-one"),
        ],
    )

    parsed = parse_notebook(path)

    assert parsed.settings == {"project_name": "real-one"}
    assert not sentinel.exists()


def test_notebook_without_a_tagged_cell_is_rejected(nb_dir: Path) -> None:
    path = _write_notebook(nb_dir / "plain.ipynb", [_md("# Hello")])
    with pytest.raises(ApplianceError, match="no cell tagged 'kaidf-config'"):
        parse_notebook(path)


def test_two_tagged_cells_are_rejected(nb_dir: Path) -> None:
    path = _write_notebook(
        nb_dir / "two.ipynb",
        [_config("project_name: a"), _config("project_name: b")],
    )
    with pytest.raises(ApplianceError, match="2 cells tagged"):
        parse_notebook(path)


def test_tagged_cell_without_a_yaml_fence_is_rejected(nb_dir: Path) -> None:
    path = _write_notebook(nb_dir / "nofence.ipynb", [_md("project_name: x", tags=CONFIG_TAGS)])
    with pytest.raises(ApplianceError, match="fenced ```yaml block"):
        parse_notebook(path)


@pytest.mark.parametrize(
    ("yaml_text", "message"),
    [
        ("project_name: [unclosed", "YAML is invalid"),
        ("- just\n- a list", "must be a mapping"),
        ("project_name: ok\nunknown_knob: 1", "unknown setting 'unknown_knob'"),
        ("api_key: sk-123", "looks like a secret"),
        ("project_name: has spaces", "project_name may use"),
        ("project_name: ''", "single line of text"),
        ("audit_fail_under: 101", "integer from 0 to 100"),
        ("audit_fail_under: true", "integer from 0 to 100"),
        ("audit_fail_under: '80'", "integer from 0 to 100"),
    ],
)
def test_invalid_settings_are_rejected(nb_dir: Path, yaml_text: str, message: str) -> None:
    path = _write_notebook(nb_dir / "bad.ipynb", [_config(yaml_text)])
    with pytest.raises(ApplianceError, match=re.escape(message)):
        parse_notebook(path)


def test_empty_yaml_block_is_rejected(nb_dir: Path) -> None:
    path = _write_notebook(nb_dir / "empty.ipynb", [_md("```yaml\n# nothing\n```", CONFIG_TAGS)])
    with pytest.raises(ApplianceError, match="empty YAML block"):
        parse_notebook(path)


def test_non_notebook_files_are_rejected(nb_dir: Path) -> None:
    broken = nb_dir / "broken.ipynb"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ApplianceError, match="not a valid notebook"):
        parse_notebook(broken)

    old = _write_notebook(nb_dir / "old.ipynb", [_config("project_name: a")], nbformat=3)
    with pytest.raises(ApplianceError, match="nbformat 4"):
        parse_notebook(old)


def test_apply_creates_workspace_and_records_settings(
    nb_dir: Path, project: Path, fake_init
) -> None:
    path = _write_notebook(
        nb_dir / "pilot.ipynb",
        [_md("# Pilot"), _config("project_name: acme-pilot\naudit_fail_under: 90")],
    )

    result = apply_notebook(path, project)

    assert fake_init == [{"project_root": project, "force": False}]
    assert result.created_workspace is True
    assert result.repo_root == project / ".kaidf"
    record = yaml.safe_load(result.record_path.read_text(encoding="utf-8"))
    assert record["schema"] == 1
    assert record["notebook"]["name"] == "pilot.ipynb"
    assert record["notebook"]["title"] == "Pilot"
    assert record["notebook"]["sha256"] == result.bootstrap.notebook_sha256
    assert record["settings"] == {"project_name": "acme-pilot", "audit_fail_under": 90}


def test_apply_keeps_an_existing_workspace_unless_forced(
    nb_dir: Path, project: Path, fake_init
) -> None:
    (project / ".kaidf").mkdir()
    (project / ".kaidf" / "mentor-workflow.json").write_text("{}", encoding="utf-8")
    path = _write_notebook(nb_dir / "pilot.ipynb", [_config("project_name: kept")])

    result = apply_notebook(path, project)

    assert fake_init == []
    assert result.created_workspace is False
    assert (project / ".kaidf" / "mentor-workflow.json").exists()
    assert result.record_path.exists()


def test_apply_with_force_recreates_the_workspace(nb_dir: Path, project: Path, fake_init) -> None:
    (project / ".kaidf").mkdir()
    path = _write_notebook(nb_dir / "pilot.ipynb", [_config("project_name: fresh")])

    result = apply_notebook(path, project, force=True)

    assert fake_init == [{"project_root": project, "force": True}]
    assert result.created_workspace is True


def test_invalid_notebook_creates_nothing(nb_dir: Path, project: Path, fake_init) -> None:
    path = _write_notebook(nb_dir / "bad.ipynb", [_config("api_key: sk-1")])

    with pytest.raises(ApplianceError):
        apply_notebook(path, project)

    assert fake_init == []
    assert not (project / ".kaidf").exists()


def test_template_is_a_valid_nbformat_notebook(tmp_path: Path) -> None:
    out = write_template(tmp_path / "kaidf-appliance.ipynb")
    notebook = json.loads(out.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] >= 5
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    ids = [cell["id"] for cell in notebook["cells"]]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cell_id) for cell_id in ids)
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_template_runs_install_init_and_audit_as_shell_cells() -> None:
    notebook = build_template("kaidf-appliance.ipynb")
    commands = [
        "".join(cell["source"]).strip() for cell in notebook["cells"] if cell["cell_type"] == "code"
    ]
    joined = "\n".join(commands)

    assert "!pip install -q agent-aidf" in joined
    assert '!kob appliance init --from-notebook "kaidf-appliance.ipynb"' in joined
    assert "!kob audit --json" in joined


def test_template_config_parses_and_has_no_secrets(tmp_path: Path) -> None:
    out = write_template(tmp_path / "template.ipynb")
    parsed = parse_notebook(out)

    assert parsed.title == "K-AIDF Appliance"
    assert parsed.settings == {"project_name": "my-kaidf-project", "audit_fail_under": 80}
    text = out.read_text(encoding="utf-8").lower()
    assert "api_key" not in text
    assert "sk-" not in text


def test_template_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    out = tmp_path / "t.ipynb"
    write_template(out)
    with pytest.raises(ApplianceError, match="--force"):
        write_template(out)
    write_template(out, force=True)


def test_cli_init_from_notebook(nb_dir: Path, project: Path, fake_init, capsys) -> None:
    path = _write_notebook(
        nb_dir / "pilot.ipynb", [_md("# Pilot"), _config("project_name: cli-run")]
    )

    code = cli_main._run_cli(
        ["--project", str(project), "appliance", "init", "--from-notebook", str(path)]
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "workspace: created" in out
    assert "project_name=cli-run" in out
    assert (project / ".kaidf" / "appliance.yaml").exists()


def test_cli_init_reports_notebook_errors_on_stderr(nb_dir: Path, project: Path, capsys) -> None:
    path = _write_notebook(nb_dir / "bad.ipynb", [_md("# no config")])

    code = cli_main._run_cli(
        ["--project", str(project), "appliance", "init", "--from-notebook", str(path)]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "kob appliance:" in captured.err
    assert "kaidf-config" in captured.err


def test_cli_init_requires_a_notebook_argument() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main._run_cli(["appliance", "init"])
    assert excinfo.value.code == 2


def test_cli_template_writes_once(tmp_path: Path, capsys) -> None:
    out = tmp_path / "starter.ipynb"

    assert cli_main._run_cli(["appliance", "template", str(out)]) == 0
    assert out.exists()
    assert cli_main._run_cli(["appliance", "template", str(out)]) == 1
    assert "--force" in capsys.readouterr().err
