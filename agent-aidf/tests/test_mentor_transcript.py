"""kob mentor --transcript: the Q&A record of the mentor workflow, as text and as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from agent_aidf.cli.main import _run_cli
from agent_aidf.mentor import (
    MentorInteraction,
    MentorState,
    mentor_transcript_data,
    mentor_transcript_text,
    save_mentor_state,
)


def _interaction(step: int, question: str, answer: str, **extra) -> MentorInteraction:
    return MentorInteraction(
        step=step,
        category=extra.pop("category", "discovery"),
        document_path=extra.pop("document_path", "docs/02_discovery_mapping/system-map.md"),
        question=question,
        answer=answer,
        mentor_reply="ok",
        **extra,
    )


def test_no_state_file_says_nothing_has_been_answered(tmp_path: Path) -> None:
    text = mentor_transcript_text(tmp_path)

    assert "No mentor questions have been answered yet" in text


def test_answered_questions_are_listed_in_order_with_their_answers(tmp_path: Path) -> None:
    save_mentor_state(
        tmp_path,
        MentorState(
            step_count=2,
            interactions=[
                _interaction(1, "Who uses the system?", "Operators in clinics."),
                _interaction(
                    2,
                    "What must never leave the site?",
                    "Patient records.",
                    action_summary="drafted the system map",
                ),
            ],
        ),
    )

    text = mentor_transcript_text(tmp_path)

    assert text.index("Who uses the system?") < text.index("What must never leave the site?")
    assert "A: Operators in clinics." in text
    assert "Action: drafted the system map" in text
    assert "No question is pending." in text


def test_a_pending_question_is_listed_apart_as_unanswered(tmp_path: Path) -> None:
    save_mentor_state(
        tmp_path,
        MentorState(
            step_count=1,
            interactions=[_interaction(1, "Who uses the system?", "Operators.")],
            pending_question="Which data is regulated?",
            pending_category="discovery",
        ),
    )

    data = mentor_transcript_data(tmp_path)
    text = mentor_transcript_text(tmp_path)

    assert data["pending_question"] == "Which data is regulated?"
    assert "[pending] discovery" in text
    assert "A: (not answered yet)" in text


def test_a_completed_workflow_says_so(tmp_path: Path) -> None:
    save_mentor_state(
        tmp_path,
        MentorState(
            step_count=1,
            interactions=[_interaction(1, "Q?", "A.")],
            accepted_phases=[1, 2, 3, 4, 5],
        ),
    )

    data = mentor_transcript_data(tmp_path)
    text = mentor_transcript_text(tmp_path)

    assert data["completed"] is True
    assert "Workflow complete: all phases accepted." in text


def test_the_json_transcript_keeps_every_field_of_an_interaction(tmp_path: Path) -> None:
    save_mentor_state(
        tmp_path,
        MentorState(
            step_count=1,
            interactions=[_interaction(1, "Q?", "A.", app_id="notes-app")],
        ),
    )

    data = mentor_transcript_data(tmp_path)

    assert data["interactions"] == [
        {
            "step": 1,
            "category": "discovery",
            "document_path": "docs/02_discovery_mapping/system-map.md",
            "question": "Q?",
            "answer": "A.",
            "app_id": "notes-app",
            "action_summary": None,
        }
    ]
    assert json.loads(json.dumps(data))["step_count"] == 1


def test_the_cli_prints_the_transcript_as_text_and_as_json(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    (project / ".kaidf").mkdir(parents=True)
    save_mentor_state(
        project / ".kaidf",
        MentorState(step_count=1, interactions=[_interaction(1, "Who uses it?", "Clinics.")]),
    )

    assert _run_cli(["--project", str(project), "mentor", "--transcript"]) == 0
    text_out = capsys.readouterr().out
    assert "Q: Who uses it?" in text_out

    assert _run_cli(["--project", str(project), "mentor", "--transcript", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["interactions"][0]["answer"] == "Clinics."
