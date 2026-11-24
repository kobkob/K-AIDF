from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_aidf.artifacts import document_problems
from agent_aidf.scan import (
    ScanError,
    chunks_for,
    compute,
    extract,
    qlora_rows,
    rag_files,
    write_outputs,
)

cli_main = importlib.import_module("agent_aidf.cli.main")

FAKE_KEY = "sk-proj-AbCdEf1234567890GhIjKlMnOp"  # matches the audit's key pattern, not an example


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with a .kaidf/ scaffold, some code, a README and an app."""
    root = tmp_path / "demo"
    _write(
        root / "app/main.py",
        'def greet(name):\n    return "hi " + name\n\n\nclass Store:\n    pass\n',
    )
    _write(root / "pyproject.toml", '[project]\nname = "demo"\n')
    _write(root / "README.md", "# Demo\n\nA small demo service.\n\n## Usage\nRun it.\n")
    _write(root / "apps/notes/main.py", 'print("x")\n')
    scaffold = root / ".kaidf"
    _write(scaffold / "README.md", "# scaffold\n")
    return root


def _scaffold(root: Path) -> Path:
    return root / ".kaidf"


# --- stage 1: extract ---------------------------------------------------------------------------


def test_extract_detects_languages_manifests_and_apps(project: Path) -> None:
    plan = extract(project, _scaffold(project))

    assert plan.languages.get("Python", 0) >= 2
    assert "pyproject.toml" in plan.manifests
    assert plan.apps == ["notes"]
    assert not plan.is_blocked
    assert plan.files_seen == 4  # the scaffold itself is not part of the project


def test_extract_respects_gitignore_in_a_repository(project: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
    _write(project / ".gitignore", "secret_notes.md\n")
    _write(project / "secret_notes.md", "# Private plans\n\nKeep out of the corpus.\n")

    plan = extract(project, _scaffold(project))

    assert "secret_notes.md" not in {chunk.source for chunk in plan.chunks}
    assert "README.md" in {chunk.source for chunk in plan.chunks}


def test_a_credential_blocks_the_plan_and_only_its_kind_is_reported(project: Path) -> None:
    _write(project / "app/config.py", f'OPENAI = "{FAKE_KEY}"\n')

    plan = extract(project, _scaffold(project))

    assert plan.is_blocked
    assert "app/config.py" in plan.blocked
    assert FAKE_KEY not in json.dumps(plan.to_dict())


def test_a_private_document_is_withheld_from_the_model(project: Path) -> None:
    _write(project / "board-notes.md", "---\nvisibility: private\n---\n# Board\n\nConfidential.\n")

    plan = extract(project, _scaffold(project))

    assert "board-notes.md" in plan.withheld
    assert "board-notes.md" not in {chunk.source for chunk in plan.chunks}


# --- stage 2: chunk -----------------------------------------------------------------------------


def test_python_is_chunked_by_top_level_definition() -> None:
    text = "import os\n\n\ndef one():\n    return 1\n\n\nclass Two:\n    pass\n"

    chunks = chunks_for("mod.py", text)

    headings = [chunk.heading for chunk in chunks]
    assert any("def one" in heading for heading in headings)
    assert any("def Two" in heading for heading in headings)
    assert any("def one" in chunk.heading and "return 1" in chunk.text for chunk in chunks)


def test_markdown_is_chunked_by_heading() -> None:
    chunks = chunks_for("doc.md", "# Top\n\nIntro.\n\n## Part\n\nDetail.\n")

    assert [chunk.heading for chunk in chunks] == ["Top", "Top > Part"]


def test_other_code_is_chunked_in_windows() -> None:
    text = "\n".join(f"line {n}" for n in range(1, 151))

    chunks = chunks_for("script.sh", text)

    assert len(chunks) == 3  # 150 lines in windows of 60
    assert chunks[0].heading.startswith("script.sh L1-60")


# --- stage 3: drafts ----------------------------------------------------------------------------


def test_drafts_pass_the_mentor_document_checks(project: Path) -> None:
    plan = extract(project, _scaffold(project))
    compute(plan, _scaffold(project))

    assert set(plan.drafts) == {
        "docs/02_discovery_mapping/system-map.md",
        "docs/03_design_simulation/blueprint.md",
    }
    for rel, text in plan.drafts.items():
        phase = rel.split("/")[1]
        assert document_problems(rel, text, _scaffold(project), phase) == []


def test_an_existing_draft_is_never_overwritten(project: Path) -> None:
    target = _scaffold(project) / "docs/02_discovery_mapping/system-map.md"
    _write(target, "# my own map\n")

    plan = extract(project, _scaffold(project))
    compute(plan, _scaffold(project))

    assert "docs/02_discovery_mapping/system-map.md" not in plan.drafts
    assert "exists" in plan.skipped_drafts["docs/02_discovery_mapping/system-map.md"]


# --- stage 4: fork ------------------------------------------------------------------------------


def test_the_dataset_rows_are_traceable_to_their_source(project: Path) -> None:
    plan = extract(project, _scaffold(project))

    rows = qlora_rows(plan)

    assert rows
    for row in rows:
        assert row["synthetic"] is True
        assert row["source"]
        assert len(row["source_sha256"]) == 64
        assert row["output"]


def test_the_rag_corpus_is_one_file_per_source(project: Path) -> None:
    plan = extract(project, _scaffold(project))

    files = rag_files(plan)

    assert "rag/corpus/readme-md.md" in files
    assert "visibility: internal" in files["rag/corpus/readme-md.md"]


def test_write_outputs_writes_the_drafts_corpus_dataset_and_inventory(project: Path) -> None:
    scaffold = _scaffold(project)
    plan = extract(project, scaffold)
    compute(plan, scaffold)

    written = write_outputs(plan, scaffold)

    assert (scaffold / "docs/02_discovery_mapping/system-map.md").is_file()
    assert (scaffold / "rag/corpus/readme-md.md").is_file()
    dataset = (scaffold / "datasets/qlora-corpus.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(dataset) == len(plan.chunks)
    assert json.loads(dataset[0])["synthetic"] is True
    assert (scaffold / "scan/inventory.json").is_file()
    assert "datasets/qlora-corpus.jsonl" in written


def test_write_outputs_points_an_existing_profile_at_the_new_layers(project: Path) -> None:
    scaffold = _scaffold(project)
    _write(scaffold / "model-setup.json", json.dumps({"name": "demo", "mood": "pragmatic-auditor"}))
    plan = extract(project, scaffold)
    compute(plan, scaffold)

    write_outputs(plan, scaffold)

    profile = json.loads((scaffold / "model-setup.json").read_text(encoding="utf-8"))
    assert {"path": "rag/corpus"} in profile["rag"]["sources"]
    assert profile["qlora"]["dataset_manifest"] == "datasets/qlora-corpus.jsonl"


def test_a_profile_that_would_not_validate_stops_the_write(project: Path) -> None:
    scaffold = _scaffold(project)
    original = json.dumps({"name": "demo", "mood": "pragmatic-auditor", "rag": {"top_k": 0}})
    _write(scaffold / "model-setup.json", original)
    plan = extract(project, scaffold)
    compute(plan, scaffold)

    with pytest.raises(ScanError, match="would not validate"):
        write_outputs(plan, scaffold)

    assert (scaffold / "model-setup.json").read_text(encoding="utf-8") == original
    assert not (scaffold / "datasets/qlora-corpus.jsonl").exists()


def test_a_blocked_plan_writes_nothing(project: Path) -> None:
    _write(project / "app/config.py", f'OPENAI = "{FAKE_KEY}"\n')
    scaffold = _scaffold(project)
    plan = extract(project, scaffold)
    compute(plan, scaffold)

    with pytest.raises(ScanError, match="credentials"):
        write_outputs(plan, scaffold)

    assert not (scaffold / "docs/02_discovery_mapping/system-map.md").exists()
    assert not (scaffold / "datasets").exists()


# --- CLI ----------------------------------------------------------------------------------------


def _snapshot(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def test_dry_run_writes_nothing(project: Path, capsys) -> None:
    before = _snapshot(_scaffold(project))

    assert cli_main._run_cli(["--project", str(project), "scan", "--dry-run"]) == 0

    assert _snapshot(_scaffold(project)) == before
    assert "Dry run: nothing was written." in capsys.readouterr().out


def test_json_without_yes_prints_the_plan_and_writes_nothing(project: Path, capsys) -> None:
    before = _snapshot(_scaffold(project))

    assert cli_main._run_cli(["--project", str(project), "scan", "--json"]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["blocked"] is False
    assert "docs/02_discovery_mapping/system-map.md" in plan["drafts"]
    assert _snapshot(_scaffold(project)) == before


def test_without_a_terminal_or_yes_nothing_is_written(project: Path, capsys) -> None:
    before = _snapshot(_scaffold(project))

    assert cli_main._run_cli(["--project", str(project), "scan"]) == 2

    assert _snapshot(_scaffold(project)) == before
    assert "--yes" in capsys.readouterr().err


def test_yes_writes_and_reports_what_it_wrote(project: Path, capsys) -> None:
    assert cli_main._run_cli(["--project", str(project), "scan", "--yes"]) == 0

    assert (_scaffold(project) / "rag/corpus/readme-md.md").is_file()
    assert "Wrote:" in capsys.readouterr().out


def test_a_credential_returns_exit_1_and_names_only_the_file(project: Path, capsys) -> None:
    _write(project / "app/config.py", f'OPENAI = "{FAKE_KEY}"\n')

    assert cli_main._run_cli(["--project", str(project), "scan", "--yes"]) == 1

    out = capsys.readouterr().out
    assert "app/config.py" in out
    assert FAKE_KEY not in out


def test_scan_needs_a_kaidf_scaffold(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "main.py", "x = 1\n")

    assert cli_main._run_cli(["--project", str(tmp_path), "scan", "--dry-run"]) == 2
    assert "kob init" in capsys.readouterr().err
