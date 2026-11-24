"""GET /api/mentor/transcript: the Q&A record for the WebUI panel, behind the status session."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_aidf import webui
from agent_aidf.mentor import MentorInteraction, MentorState, save_mentor_state

PORT = 12345
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(webui, "resolve_mentor_repo_root", lambda _project_root: tmp_path)
    monkeypatch.setattr(webui, "_status_payload", lambda _project, _repo: {"yolo": False})
    return webui.create_app(tmp_path, tmp_path, port=PORT)


def test_the_transcript_lists_answers_and_the_pending_question(app, tmp_path: Path) -> None:
    save_mentor_state(
        tmp_path,
        MentorState(
            step_count=1,
            interactions=[
                MentorInteraction(
                    step=1,
                    category="discovery",
                    document_path="docs/system-map.md",
                    question="Who uses it?",
                    answer="Clinics.",
                    mentor_reply="ok",
                )
            ],
            pending_question="Which data is regulated?",
            pending_category="discovery",
        ),
    )
    client = app.test_client()
    headers = {webui.API_TOKEN_HEADER: app.config["API_TOKEN"]}

    response = client.get("/api/mentor/transcript", base_url=BASE_URL, headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["interactions"][0]["answer"] == "Clinics."
    assert body["pending_question"] == "Which data is regulated?"


def test_the_transcript_needs_a_session_or_the_token(app) -> None:
    response = app.test_client().get("/api/mentor/transcript", base_url=BASE_URL)

    assert response.status_code == 401


def test_the_transcript_is_empty_before_any_question(app) -> None:
    client = app.test_client()
    headers = {webui.API_TOKEN_HEADER: app.config["API_TOKEN"]}

    body = client.get("/api/mentor/transcript", base_url=BASE_URL, headers=headers).get_json()

    assert body["interactions"] == []
    assert body["pending_question"] is None
