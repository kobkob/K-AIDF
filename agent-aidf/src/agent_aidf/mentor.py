from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath

from .instant_apps import (
    append_mentor_note,
    apply_mentor_update,
    ensure_persistent_instant_app,
    get_instant_app,
    list_instant_apps,
    load_instant_app_runtime,
    run_instant_app,
    stop_instant_app,
)
from .repo import Document, load_documents, resolve_repo_root
from .tools import (
    ACTION_PROTOCOL_INSTRUCTIONS,
    ProposedAction,
    apply_action,
    describe_action,
    extract_proposed_action,
    is_affirmative,
    is_yolo_enabled,
)

MENTOR_STATE_FILENAME = "mentor-workflow.json"

# The mentor workflow always operates on repo_root == <project_root>/.kaidf (see
# project.resolve_mentor_repo_root). File actions sandbox to the project root, one level up,
# so drafts can land at .kaidf/docs/... or elsewhere in the project - not just inside .kaidf/.
# Duplicated here (rather than imported from project.py) to avoid a circular import; see the
# deferred `from .contracts import ...` imports below for the same reason with contracts.py.
_KAIDF_DIRNAME = ".kaidf"


def _project_root_for(repo_root: Path) -> Path:
    return repo_root.parent if repo_root.name == _KAIDF_DIRNAME else repo_root


@dataclass(frozen=True)
class MentorInteraction:
    step: int
    category: str
    document_path: str
    question: str
    answer: str
    mentor_reply: str
    action_summary: str | None = None
    app_id: str | None = None


@dataclass(frozen=True)
class MentorState:
    version: int = 1
    step_count: int = 0
    previous_response_id: str | None = None
    pending_question: str | None = None
    pending_category: str | None = None
    pending_document_path: str | None = None
    current_app_id: str | None = None
    last_action_summary: str | None = None
    interactions: list[MentorInteraction] = field(default_factory=list)
    # The 5 K-AIDF Basic phases (see contracts.basic_phase_definitions()) are walked strictly
    # in order. A phase only ever enters accepted_phases once its artifact files are filled in
    # AND the user has explicitly confirmed - never from raw step/question count.
    pending_phase_order: int = 1
    accepted_phases: list[int] = field(default_factory=list)
    awaiting_acceptance: bool = False
    pending_file_action: dict | None = None


@dataclass(frozen=True)
class MentorTurn:
    message: str
    state: MentorState
    token_usage: dict[str, int] | None = None


def mentor_state_path(repo_root: str | Path | None) -> Path:
    repo = resolve_repo_root(repo_root)
    return repo / MENTOR_STATE_FILENAME


def load_mentor_state(repo_root: str | Path | None) -> MentorState:
    path = mentor_state_path(repo_root)
    if not path.is_file():
        return MentorState()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return MentorState()
    interactions_raw = data.get("interactions", [])
    interactions: list[MentorInteraction] = []
    if isinstance(interactions_raw, list):
        for item in interactions_raw:
            if not isinstance(item, dict):
                continue
            try:
                interactions.append(
                    MentorInteraction(
                        step=int(item["step"]),
                        category=str(item["category"]),
                        document_path=str(item["document_path"]),
                        question=str(item["question"]),
                        answer=str(item["answer"]),
                        mentor_reply=str(item["mentor_reply"]),
                        action_summary=_optional_str(item.get("action_summary")),
                        app_id=_optional_str(item.get("app_id")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    accepted_phases_raw = data.get("accepted_phases", [])
    accepted_phases = (
        sorted({int(order) for order in accepted_phases_raw if isinstance(order, (int, float))})
        if isinstance(accepted_phases_raw, list)
        else []
    )
    pending_file_action_raw = data.get("pending_file_action")
    pending_file_action = pending_file_action_raw if isinstance(pending_file_action_raw, dict) else None
    return MentorState(
        version=int(data.get("version", 1)),
        step_count=int(data.get("step_count", len(interactions))),
        previous_response_id=_optional_str(data.get("previous_response_id")),
        pending_question=_optional_str(data.get("pending_question")),
        pending_category=_optional_str(data.get("pending_category")),
        pending_document_path=_optional_str(data.get("pending_document_path")),
        current_app_id=_optional_str(data.get("current_app_id")),
        last_action_summary=_optional_str(data.get("last_action_summary")),
        interactions=interactions,
        pending_phase_order=int(data.get("pending_phase_order", 1)),
        accepted_phases=accepted_phases,
        awaiting_acceptance=bool(data.get("awaiting_acceptance", False)),
        pending_file_action=pending_file_action,
    )


def save_mentor_state(repo_root: str | Path | None, state: MentorState) -> Path:
    path = mentor_state_path(repo_root)
    payload = {
        "version": state.version,
        "step_count": state.step_count,
        "previous_response_id": state.previous_response_id,
        "pending_question": state.pending_question,
        "pending_category": state.pending_category,
        "pending_document_path": state.pending_document_path,
        "current_app_id": state.current_app_id,
        "last_action_summary": state.last_action_summary,
        "interactions": [asdict(item) for item in state.interactions],
        "pending_phase_order": state.pending_phase_order,
        "accepted_phases": state.accepted_phases,
        "awaiting_acceptance": state.awaiting_acceptance,
        "pending_file_action": state.pending_file_action,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def reset_mentor_state(repo_root: str | Path | None) -> Path:
    path = mentor_state_path(repo_root)
    if path.exists():
        path.unlink()
    return path


def mentor_status_text(repo_root: str | Path | None) -> str:
    state = load_mentor_state(repo_root)
    lines = [
        f"step_count: {state.step_count}",
        f"pending_phase: {state.pending_phase_order}/{_total_phases()}",
        f"accepted_phases: {state.accepted_phases or 'none'}",
        f"pending_category: {state.pending_category or 'none'}",
        f"pending_document: {state.pending_document_path or 'none'}",
        f"pending_question: {state.pending_question or 'none'}",
        f"awaiting_acceptance: {state.awaiting_acceptance}",
        f"pending_file_action: {'yes' if state.pending_file_action else 'none'}",
        f"previous_response_id: {state.previous_response_id or 'none'}",
        f"current_app_id: {state.current_app_id or 'none'}",
        f"last_action_summary: {state.last_action_summary or 'none'}",
    ]
    return "\n".join(lines)


def continue_mentor_workflow(
    repo_root: str | Path | None,
    *,
    answer: str | None = None,
) -> MentorTurn:
    repo = resolve_repo_root(repo_root)
    state = load_mentor_state(repo)
    documents = load_documents(repo)

    if state.pending_phase_order > _total_phases():
        return MentorTurn(message=_all_phases_complete_message(state), state=state)

    phase = _phase_by_order(state.pending_phase_order)
    phase_dir = _phase_directory_name(phase)

    if not answer:
        if state.pending_question:
            return MentorTurn(message=_format_pending_question(state), state=state)
        next_state = replace(
            state,
            pending_question=_first_quiz_question(phase),
            pending_category=phase["name"],
            pending_document_path=f"docs/{phase_dir}",
        )
        save_mentor_state(repo, next_state)
        return MentorTurn(message=_format_pending_question(next_state), state=next_state)

    if state.pending_file_action:
        return _handle_file_action_response(repo, state, documents, answer, phase=phase, phase_dir=phase_dir)

    if state.awaiting_acceptance:
        return _handle_acceptance_response(repo, state, documents, answer, phase=phase, phase_dir=phase_dir)

    return _handle_normal_answer(repo, state, documents, answer, phase=phase, phase_dir=phase_dir)


def _handle_normal_answer(
    repo: Path,
    state: MentorState,
    documents: list[Document],
    answer: str,
    *,
    phase: dict,
    phase_dir: str,
    check_acceptance: bool = True,
) -> MentorTurn:
    pending_question = state.pending_question or _first_quiz_question(phase)
    mentor_reply, previous_response_id, token_usage = _build_mentor_reply(
        repo, state, documents, pending_question, phase, phase_dir, answer
    )
    cleaned_reply, proposed_action = extract_proposed_action(mentor_reply)

    action_summary, current_app_id = _apply_answer_actions(
        repo,
        state,
        pending_category=phase["name"],
        pending_question=pending_question,
        answer=answer,
        mentor_reply=cleaned_reply,
    )
    updated_interactions = [
        *state.interactions,
        MentorInteraction(
            step=state.step_count + 1,
            category=phase["name"],
            document_path=f"docs/{phase_dir}",
            question=pending_question,
            answer=answer,
            mentor_reply=cleaned_reply,
            action_summary=action_summary,
            app_id=current_app_id,
        ),
    ]
    base_next_state = replace(
        state,
        step_count=len(updated_interactions),
        previous_response_id=previous_response_id,
        current_app_id=current_app_id,
        last_action_summary=action_summary,
        interactions=updated_interactions,
        pending_category=phase["name"],
        pending_document_path=f"docs/{phase_dir}",
    )

    yolo_action_note: str | None = None
    if proposed_action is not None:
        if is_yolo_enabled():
            yolo_action_note = f"[--yolo] {apply_action(_project_root_for(repo), proposed_action)}"
        else:
            next_state = replace(
                base_next_state,
                pending_file_action=asdict(proposed_action),
                pending_question=describe_action(proposed_action),
            )
            save_mentor_state(repo, next_state)
            message = "\n".join(
                [
                    cleaned_reply.strip(),
                    "",
                    f"Action: {action_summary}",
                    "",
                    describe_action(proposed_action),
                ]
            ).strip()
            return MentorTurn(message=message, state=next_state, token_usage=token_usage)

    documents_after = load_documents(repo)
    message_lines = [cleaned_reply.strip(), "", f"Action: {action_summary}"]
    if yolo_action_note:
        message_lines.extend(["", yolo_action_note])

    if (
        check_acceptance
        and phase["order"] not in state.accepted_phases
        and _phase_ready_for_acceptance(documents_after, phase_dir)
    ):
        acceptance_question = _acceptance_question(phase, phase_dir)
        next_state = replace(base_next_state, awaiting_acceptance=True, pending_question=acceptance_question)
        message_lines.extend(["", acceptance_question])
    else:
        next_question = _next_quiz_question(phase, updated_interactions)
        next_state = replace(base_next_state, pending_question=next_question)
        message_lines.extend(
            [
                f"Next focus: {next_state.pending_category} :: {next_state.pending_document_path}",
                f"Next question: {next_state.pending_question}",
            ]
        )

    save_mentor_state(repo, next_state)
    return MentorTurn(message="\n".join(message_lines).strip(), state=next_state, token_usage=token_usage)


def _handle_file_action_response(
    repo: Path,
    state: MentorState,
    documents: list[Document],
    answer: str,
    *,
    phase: dict,
    phase_dir: str,
) -> MentorTurn:
    assert state.pending_file_action is not None
    action = ProposedAction(**state.pending_file_action)
    cleared_state = replace(state, pending_file_action=None, pending_question=None)

    if not is_affirmative(answer):
        return _handle_normal_answer(
            repo, cleared_state, documents, answer, phase=phase, phase_dir=phase_dir, check_acceptance=False
        )

    write_summary = apply_action(_project_root_for(repo), action)

    documents_after = load_documents(repo)
    if phase["order"] not in cleared_state.accepted_phases and _phase_ready_for_acceptance(documents_after, phase_dir):
        acceptance_question = _acceptance_question(phase, phase_dir)
        next_state = replace(
            cleared_state,
            awaiting_acceptance=True,
            pending_question=acceptance_question,
            last_action_summary=write_summary,
        )
        message = "\n".join([write_summary, "", acceptance_question]).strip()
    else:
        next_question = _next_quiz_question(phase, cleared_state.interactions)
        next_state = replace(cleared_state, pending_question=next_question, last_action_summary=write_summary)
        message = "\n".join(
            [
                write_summary,
                "",
                f"Next focus: {next_state.pending_category} :: {next_state.pending_document_path}",
                f"Next question: {next_state.pending_question}",
            ]
        ).strip()

    save_mentor_state(repo, next_state)
    return MentorTurn(message=message, state=next_state)


def _handle_acceptance_response(
    repo: Path,
    state: MentorState,
    documents: list[Document],
    answer: str,
    *,
    phase: dict,
    phase_dir: str,
) -> MentorTurn:
    if not is_affirmative(answer):
        cleared_state = replace(state, awaiting_acceptance=False, pending_question=None)
        return _handle_normal_answer(
            repo, cleared_state, documents, answer, phase=phase, phase_dir=phase_dir, check_acceptance=False
        )

    accepted_phases = sorted({*state.accepted_phases, phase["order"]})
    next_order = state.pending_phase_order + 1
    if next_order > _total_phases():
        next_state = replace(
            state,
            accepted_phases=accepted_phases,
            awaiting_acceptance=False,
            pending_phase_order=next_order,
            pending_question=None,
            pending_category=phase["name"],
        )
        save_mentor_state(repo, next_state)
        return MentorTurn(message=_all_phases_complete_message(next_state), state=next_state)

    next_phase = _phase_by_order(next_order)
    next_phase_dir = _phase_directory_name(next_phase)
    next_state = replace(
        state,
        accepted_phases=accepted_phases,
        awaiting_acceptance=False,
        pending_phase_order=next_order,
        pending_category=next_phase["name"],
        pending_document_path=f"docs/{next_phase_dir}",
        pending_question=_first_quiz_question(next_phase),
    )
    save_mentor_state(repo, next_state)
    message = "\n".join(
        [
            f"Phase {phase['order']} ({phase['name']}) accepted.",
            "",
            _format_pending_question(next_state),
        ]
    ).strip()
    return MentorTurn(message=message, state=next_state)


def _build_mentor_reply(
    repo_root: Path,
    state: MentorState,
    documents: list[Document],
    pending_question: str,
    phase: dict,
    phase_dir: str,
    answer: str,
) -> tuple[str, str | None, dict[str, int] | None]:
    from .controller import build_controller

    controller = build_controller()
    if hasattr(controller, "previous_response_id"):
        setattr(controller, "previous_response_id", state.previous_response_id)
    prompt = _build_mentor_prompt(
        documents,
        state,
        pending_question=pending_question,
        phase=phase,
        phase_dir=phase_dir,
        answer=answer,
    )
    raw_reply = controller.chat(prompt, repo_root)
    next_response_id = getattr(controller, "previous_response_id", state.previous_response_id)
    token_usage = getattr(controller, "last_usage", None)
    if raw_reply.startswith("AI chat controller is not configured yet."):
        raw_reply = _offline_reply(state, pending_question, phase, phase_dir, answer)
        next_response_id = state.previous_response_id
        token_usage = None
    return raw_reply, next_response_id, token_usage


def _build_mentor_prompt(
    documents: list[Document],
    state: MentorState,
    *,
    pending_question: str,
    phase: dict,
    phase_dir: str,
    answer: str,
) -> str:
    recent = state.interactions[-3:]
    history_lines = []
    if not recent:
        history_lines.append("- none")
    else:
        for item in recent:
            history_lines.append(f"- {item.category} :: {item.document_path}")
            history_lines.append(f"  q={item.question}")
            history_lines.append(f"  a={item.answer}")
            history_lines.append(f"  mentor={item.mentor_reply[:220]}")

    artifacts = _phase_artifact_documents(documents, phase_dir)
    artifact_lines = []
    if not artifacts:
        artifact_lines.append(f"- none found yet under docs/{phase_dir}/")
    else:
        for doc in artifacts:
            status_label = "filled in" if _is_artifact_filled_in(doc) else "still a blank scaffold"
            artifact_lines.append(f"- {_KAIDF_DIRNAME}/{doc.path} ({status_label})")
            excerpt = " ".join(doc.body.splitlines()[:5]).strip()
            if excerpt:
                artifact_lines.append(f"  current content={excerpt[:400]}")

    return "\n".join(
        [
            "Continue the K-AIDF mentor workflow as a guided, conversational process.",
            f"You are on phase {phase['order']}/{_total_phases()}: {phase['name']}.",
            f"Human role this phase: {phase['human_role']}",
            f"Your role this phase: {phase['ai_role']}",
            f"Deliverables expected this phase: {', '.join(phase['deliverables'])}",
            "Use the workflow history and this phase's artifact files below, and the user's latest "
            "answer, to decide what to clarify, decide, or draft next. Keep guidance pragmatic.",
            "Do not restart the workflow. Continue from the current point. Ask exactly one next "
            "question at the end, unless you are proposing a file action instead.",
            "",
            ACTION_PROTOCOL_INSTRUCTIONS,
            "",
            f"Current question: {pending_question}",
            "",
            "Recent workflow history:",
            *history_lines,
            "",
            f"This phase's artifact files (paths relative to the project root):",
            *artifact_lines,
            "",
            "User answer:",
            answer,
        ]
    )


def _offline_reply(
    state: MentorState,
    pending_question: str,
    phase: dict,
    phase_dir: str,
    answer: str,
) -> str:
    assessment = _classify_answer(answer)
    prior = "no prior answers yet" if not state.interactions else f"{len(state.interactions)} prior answers recorded"
    return (
        f"Mentor assessment: {assessment}. "
        f"Current focus remains phase {phase['order']} ({phase['name']}) using docs/{phase_dir}/. "
        f"The workflow now has {prior}. "
        "The next step should refine the project direction before implementation expands."
    )


def _classify_answer(answer: str) -> str:
    answer_norm = answer.strip()
    if not answer_norm:
        return "the answer is empty and the workflow cannot advance cleanly"
    if len(answer_norm.split()) < 6:
        return "the answer is still too short and needs more operational detail"
    if any(term in answer_norm.casefold() for term in ["risk", "privacy", "transparent", "validation", "human"]):
        return "the answer already includes governance or safety signals worth preserving"
    if any(term in answer_norm.casefold() for term in ["web", "shell", "app", "prototype", "localhost"]):
        return "the answer points toward a concrete instant-app implementation path"
    return "the answer is directionally useful but still needs tighter scope and accountability"


def _apply_answer_actions(
    repo_root: Path,
    state: MentorState,
    *,
    pending_category: str,
    pending_question: str,
    answer: str,
    mentor_reply: str,
) -> tuple[str, str | None]:
    action = _infer_app_action(answer)
    if action is None:
        return "no instant app change was needed yet", state.current_app_id
    app_id, spawn_mode = _choose_app_target(repo_root, state, action=action, answer=answer)
    previous_app_id = state.current_app_id
    app, created = ensure_persistent_instant_app(repo_root, app_id=app_id, kind=action)
    notes_path = append_mentor_note(
        repo_root,
        app.app_id,
        heading=f"Step {state.step_count + 1} :: {pending_category}",
        body="\n".join(
            [
                f"Question: {pending_question}",
                f"Answer: {answer}",
                f"Mentor reply: {mentor_reply}",
            ]
        ),
    )
    brief_path = apply_mentor_update(
        repo_root,
        app.app_id,
        step=state.step_count + 1,
        category=pending_category,
        question=pending_question,
        answer=answer,
        mentor_reply=mentor_reply,
    )
    runtime_summary = ""
    if app.kind == "web":
        runtime = load_instant_app_runtime(repo_root, app.app_id)
        if runtime is not None and runtime.status == "running":
            port = runtime.port
            stop_instant_app(repo_root, app.app_id)
            runtime = run_instant_app(repo_root, app.app_id, port=port)
            runtime_summary = f" and restarted it at http://127.0.0.1:{runtime.port}"
        else:
            runtime = run_instant_app(repo_root, app.app_id)
            runtime_summary = f" and started it at http://127.0.0.1:{runtime.port}"
    previous_runtime_summary = _stop_superseded_app(repo_root, previous_app_id, app.app_id)
    if created:
        return (
            f"{spawn_mode} persistent {app.kind} instant app '{app.app_id}', wrote mentor notes to {notes_path}, "
            f"and refreshed app files from {brief_path}{runtime_summary}{previous_runtime_summary}",
            app.app_id,
        )
    return (
        f"{spawn_mode} persistent {app.kind} instant app '{app.app_id}', appended mentor notes to {notes_path}, "
        f"and refreshed app files from {brief_path}{runtime_summary}{previous_runtime_summary}",
        app.app_id,
    )


def _infer_app_action(answer: str) -> str | None:
    answer_norm = answer.casefold()
    if not any(term in answer_norm for term in ["app", "prototype", "localhost", "interface", "workflow", "screen"]):
        return None
    if any(term in answer_norm for term in ["web", "browser", "page", "site", "server", "http", "ui"]):
        return "web"
    if any(term in answer_norm for term in ["shell", "terminal", "cli", "console"]):
        return "shell"
    return "web"


def _choose_app_target(
    repo_root: Path,
    state: MentorState,
    *,
    action: str,
    answer: str,
) -> tuple[str, str]:
    current = get_instant_app(repo_root, state.current_app_id) if state.current_app_id else None
    if current is None:
        return f"mentor-{action}-app", "created"
    if _should_spawn_new_app(current.kind, action=action, answer=answer):
        return _next_app_id(repo_root, action), "spawned new"
    return current.app_id, "reused"


def _should_spawn_new_app(current_kind: str, *, action: str, answer: str) -> bool:
    if current_kind != action:
        return True
    answer_norm = answer.casefold()
    return any(term in answer_norm for term in ["separate", "another", "second", "new app", "new interface"])


def _next_app_id(repo_root: Path, action: str) -> str:
    base = f"mentor-{action}-app"
    existing_ids = {app.app_id for app in list_instant_apps(repo_root)}
    if base not in existing_ids:
        return base
    index = 2
    while f"{base}-{index}" in existing_ids:
        index += 1
    return f"{base}-{index}"


def _stop_superseded_app(repo_root: Path, previous_app_id: str | None, current_app_id: str) -> str:
    if not previous_app_id or previous_app_id == current_app_id:
        return ""
    previous_app = get_instant_app(repo_root, previous_app_id)
    if previous_app is None or previous_app.kind != "web":
        return ""
    runtime = load_instant_app_runtime(repo_root, previous_app_id)
    if runtime is None or runtime.status != "running":
        return ""
    stop_instant_app(repo_root, previous_app_id)
    return f" and stopped superseded app '{previous_app_id}'"


def _total_phases() -> int:
    from .contracts import basic_phase_definitions

    return len(basic_phase_definitions())


def _phase_by_order(order: int) -> dict:
    from .contracts import basic_phase_definitions

    for phase in basic_phase_definitions():
        if phase["order"] == order:
            return phase
    raise ValueError(f"Unknown phase order: {order}")


def _phase_slug(name: str) -> str:
    return name.casefold().replace(" & ", "_").replace(" ", "_")


def _phase_directory_name(phase: dict) -> str:
    return f"0{phase['order']}_{_phase_slug(phase['name'])}"


def _first_quiz_question(phase: dict) -> str:
    prompts = phase.get("quiz_prompts") or []
    return prompts[0] if prompts else f"What should the mentor know first about {phase['name']}?"


def _next_quiz_question(phase: dict, interactions: list[MentorInteraction]) -> str:
    prompts = phase.get("quiz_prompts") or []
    if not prompts:
        return f"What else should the mentor know about {phase['name']}?"
    turns_in_phase = sum(1 for item in interactions if item.category == phase["name"])
    return prompts[turns_in_phase % len(prompts)]


def _acceptance_question(phase: dict, phase_dir: str) -> str:
    return (
        f"Phase {phase['order']} ({phase['name']}) artifacts under docs/{phase_dir}/ look filled in. "
        "Do you accept this phase as complete? (yes/no)"
    )


def _all_phases_complete_message(state: MentorState) -> str:
    return (
        f"All {_total_phases()} K-AIDF Basic phases are accepted. The mentor workflow is complete - "
        "use kob status to review, or kob mentor --reset to start a new workflow."
    )


def _phase_artifact_documents(documents: list[Document], phase_dir: str) -> list[Document]:
    return [
        doc
        for doc in documents
        if doc.phase == phase_dir
        and doc.document_class != "prompt-doc"
        and PurePosixPath(doc.path).name not in {"README.md", "exit-criteria.md"}
    ]


def _is_artifact_filled_in(doc: Document) -> bool:
    if doc.path.endswith(".csv"):
        lines = [line for line in doc.body.splitlines() if line.strip()]
        return len(lines) > 1
    body_lines = [line.strip() for line in doc.body.splitlines() if line.strip()]
    return any(not line.startswith("#") for line in body_lines)


def _phase_ready_for_acceptance(documents: list[Document], phase_dir: str) -> bool:
    artifacts = _phase_artifact_documents(documents, phase_dir)
    if not artifacts:
        return False
    return all(_is_artifact_filled_in(doc) for doc in artifacts)


def _format_pending_question(state: MentorState) -> str:
    lines = ["Mentor workflow is active."]
    if state.pending_category:
        lines.append(f"Current focus: {state.pending_category}")
    if state.pending_document_path:
        lines.append(f"Reference: {state.pending_document_path}")
    lines.append(f"Question: {state.pending_question}")
    return "\n".join(lines)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
