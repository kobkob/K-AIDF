"""Runtime state under .kaidf/ survives truncation, corruption and interrupted saves (#110)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_aidf import runtime_state
from agent_aidf.contracts import list_contracts
from agent_aidf.instant_apps import create_instant_app, list_instant_apps
from agent_aidf.mentor import MentorState, load_mentor_state, save_mentor_state
from agent_aidf.runtime_state import as_int, atomic_write_text, read_state_object


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    return repo


def _quarantined(directory: Path, name: str) -> list[Path]:
    return sorted(directory.glob(f"{name}.corrupt-*"))


# --- the mentor workflow -------------------------------------------------------------------------


def test_truncated_mentor_state_gives_a_clean_state_and_keeps_the_damaged_copy(
    tmp_path: Path, capsys
) -> None:
    repo = _repo(tmp_path)
    save_mentor_state(repo, MentorState(step_count=3, accepted_phases=[1, 2]))
    state_file = repo / "mentor-workflow.json"
    state_file.write_text(state_file.read_text(encoding="utf-8")[:40], encoding="utf-8")

    state = load_mentor_state(repo)

    assert state.step_count == 0
    assert state.accepted_phases == []
    assert not state_file.exists()
    kept = _quarantined(repo, "mentor-workflow.json")
    assert len(kept) == 1
    assert kept[0].read_text(encoding="utf-8").startswith("{")
    assert "not valid JSON" in capsys.readouterr().err


def test_non_numeric_state_fields_fall_back_to_defaults(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "mentor-workflow.json").write_text(
        json.dumps(
            {
                "version": "two",
                "step_count": None,
                "pending_phase_order": [1],
                "accepted_phases": [1, "x", True, float("nan")],
                "interactions": [
                    {
                        "step": "later",
                        "category": "c",
                        "document_path": "d",
                        "question": "q",
                        "answer": "a",
                        "mentor_reply": "r",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    state = load_mentor_state(repo)

    assert state.version == 1
    assert state.step_count == 0
    assert state.pending_phase_order == 1
    assert state.accepted_phases == [1]
    assert state.interactions == []


def test_a_list_instead_of_an_object_is_a_clean_state_without_quarantine(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "mentor-workflow.json").write_text("[1, 2]", encoding="utf-8")

    assert load_mentor_state(repo) == MentorState()
    assert (repo / "mentor-workflow.json").is_file()


# --- instant apps and contracts ------------------------------------------------------------------


def test_damaged_app_metadata_is_quarantined_and_the_other_apps_still_list(
    tmp_path: Path, capsys
) -> None:
    repo = _repo(tmp_path)
    good = create_instant_app(repo, app_id="good", mode="persistent", kind="shell")
    broken = create_instant_app(repo, app_id="broken", mode="persistent", kind="shell")
    metadata = broken.root / "app.json"
    metadata.write_text(metadata.read_text(encoding="utf-8")[:10], encoding="utf-8")

    apps = list_instant_apps(repo)

    assert [app.app_id for app in apps] == [good.app_id]
    assert _quarantined(broken.root, "app.json")
    assert "not valid JSON" in capsys.readouterr().err


def test_damaged_contract_payload_is_skipped_not_fatal(tmp_path: Path, capsys) -> None:
    repo = _repo(tmp_path)
    contract_root = repo / "contracts" / "damaged"
    contract_root.mkdir(parents=True)
    (contract_root / "contract.json").write_text('{"phases": [', encoding="utf-8")

    assert list_contracts(repo) == []
    assert _quarantined(contract_root, "contract.json")


# --- atomic writes -------------------------------------------------------------------------------


def test_atomic_write_replaces_the_file_and_leaves_no_temporary_files(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]


def test_an_interrupted_write_keeps_the_previous_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"step_count": 1}', encoding="utf-8")

    def _fail_replace(source, destination):
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime_state.os, "replace", _fail_replace)

    with pytest.raises(KeyboardInterrupt):
        save_mentor_state(tmp_path, MentorState(step_count=99))

    assert target.read_text(encoding="utf-8") == '{"step_count": 1}'
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]


def test_read_state_object_refuses_non_objects_and_missing_files(tmp_path: Path) -> None:
    assert read_state_object(tmp_path / "missing.json") is None
    (tmp_path / "scalar.json").write_text("3", encoding="utf-8")
    assert read_state_object(tmp_path / "scalar.json") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(7, 7), (" 12 ", 12), (3.9, 3), ("x", 0), (True, 0), (float("inf"), 0), (None, 0)],
)
def test_as_int_converts_or_falls_back(value, expected) -> None:
    assert as_int(value, 0) == expected
