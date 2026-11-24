"""The WebUI status payload carries the active model-setup profile, so its panel can show it."""

from __future__ import annotations

import json
from pathlib import Path

from agent_aidf import webui


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / ".kaidf"
    repo.mkdir()
    return repo


def test_the_status_payload_has_no_model_setup_without_a_profile(tmp_path: Path) -> None:
    payload = webui._status_payload(tmp_path, _repo(tmp_path))

    assert payload["model_setup"] is None


def test_the_status_payload_shows_the_active_profile(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "model-setup.json").write_text(
        json.dumps({"name": "demo-model", "mood": "strict-auditor"}), encoding="utf-8"
    )

    summary = webui._status_payload(tmp_path, repo)["model_setup"]

    assert summary["valid"] is True
    assert summary["name"] == "demo-model"
    assert summary["mood"] == "strict-auditor"
    assert "fallback_active" in summary


def test_an_invalid_profile_is_reported_not_raised(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "model-setup.json").write_text('{"name": "x"}', encoding="utf-8")

    summary = webui._status_payload(tmp_path, repo)["model_setup"]

    assert summary["valid"] is False
    assert "mood" in summary["error"]
