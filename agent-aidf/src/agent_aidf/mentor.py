from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

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

MENTOR_STATE_FILENAME = "mentor-workflow.json"
WORKFLOW_CATEGORY_ORDER = [
    "manifesto",
    "principles",
    "best-practices",
    "governance",
    "implementation",
    "maturity",
    "training",
    "general",
]

QUESTION_TEMPLATES = {
    "manifesto": "What is the main outcome this project should achieve, and why does it matter?",
    "principles": "Which principles from this framework must remain non-negotiable in this project?",
    "best-practices": "Which operating practices should the team adopt first to reduce risk quickly?",
    "governance": "Who will review, approve, and remain accountable for important AI-assisted decisions?",
    "implementation": "What is the smallest useful implementation step the mentor should help create next?",
    "maturity": "How mature is the current process today, and what evidence supports that assessment?",
    "training": "What training or onboarding will people need before this workflow is used seriously?",
    "general": "What is the most important unresolved point the mentor should clarify next?",
}


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


@dataclass(frozen=True)
class MentorTurn:
    message: str
    state: MentorState


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
        f"pending_category: {state.pending_category or 'none'}",
        f"pending_document: {state.pending_document_path or 'none'}",
        f"pending_question: {state.pending_question or 'none'}",
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
    if not documents:
        raise ValueError(f"No K-AIDF documents found in repository: {repo}")

    pending_question = state.pending_question or _default_question(documents)
    pending_category = state.pending_category or _document_category(_select_next_document(documents, state))
    pending_document_path = state.pending_document_path or _select_next_document(documents, state).path

    if not answer:
        if state.pending_question:
            return MentorTurn(
                message=_format_pending_question(state.pending_question, state.pending_category, state.pending_document_path),
                state=state,
            )
        next_document = _select_next_document(documents, state)
        next_question = _question_for_document(next_document)
        next_state = MentorState(
            version=state.version,
            step_count=state.step_count,
            previous_response_id=state.previous_response_id,
            pending_question=next_question,
            pending_category=_document_category(next_document),
            pending_document_path=next_document.path,
            current_app_id=state.current_app_id,
            last_action_summary=state.last_action_summary,
            interactions=state.interactions,
        )
        save_mentor_state(repo, next_state)
        return MentorTurn(
            message=_format_pending_question(next_question, next_state.pending_category, next_state.pending_document_path),
            state=next_state,
        )

    mentor_reply, previous_response_id = _build_mentor_reply(
        repo,
        state,
        documents,
        pending_question,
        pending_category,
        pending_document_path,
        answer,
    )
    action_summary, current_app_id = _apply_answer_actions(
        repo,
        state,
        pending_category=pending_category,
        pending_question=pending_question,
        answer=answer,
        mentor_reply=mentor_reply,
    )
    updated_interactions = [
        *state.interactions,
        MentorInteraction(
            step=state.step_count + 1,
            category=pending_category,
            document_path=pending_document_path,
            question=pending_question,
            answer=answer,
            mentor_reply=mentor_reply,
            action_summary=action_summary,
            app_id=current_app_id,
        ),
    ]
    next_document = _select_next_document(documents, MentorState(interactions=updated_interactions, step_count=len(updated_interactions)))
    next_question = _choose_next_question(documents, updated_interactions, answer, next_document)
    next_state = MentorState(
        version=state.version,
        step_count=len(updated_interactions),
        previous_response_id=previous_response_id,
        pending_question=next_question,
        pending_category=_document_category(next_document),
        pending_document_path=next_document.path,
        current_app_id=current_app_id,
        last_action_summary=action_summary,
        interactions=updated_interactions,
    )
    save_mentor_state(repo, next_state)
    message = "\n".join(
        [
            mentor_reply.strip(),
            "",
            f"Action: {action_summary}",
            f"Next focus: {next_state.pending_category} :: {next_state.pending_document_path}",
            f"Next question: {next_state.pending_question}",
        ]
    ).strip()
    return MentorTurn(message=message, state=next_state)


def _build_mentor_reply(
    repo_root: Path,
    state: MentorState,
    documents: list[Document],
    pending_question: str,
    pending_category: str,
    pending_document_path: str,
    answer: str,
) -> tuple[str, str | None]:
    from .controller import build_controller

    controller = build_controller()
    if hasattr(controller, "previous_response_id"):
        setattr(controller, "previous_response_id", state.previous_response_id)
    prompt = _build_mentor_prompt(
        documents,
        state,
        pending_question=pending_question,
        pending_category=pending_category,
        pending_document_path=pending_document_path,
        answer=answer,
    )
    raw_reply = controller.chat(prompt, repo_root)
    next_response_id = getattr(controller, "previous_response_id", state.previous_response_id)
    if raw_reply.startswith("AI chat controller is not configured yet."):
        raw_reply = _offline_reply(documents, state, pending_question, pending_category, pending_document_path, answer)
        next_response_id = state.previous_response_id
    return raw_reply, next_response_id


def _build_mentor_prompt(
    documents: list[Document],
    state: MentorState,
    *,
    pending_question: str,
    pending_category: str,
    pending_document_path: str,
    answer: str,
) -> str:
    from .controller import select_context_documents

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
    matched = select_context_documents(documents, f"{pending_category} {answer}", limit=4)
    doc_lines = []
    if not matched:
        doc_lines.append("- none")
    else:
        for doc in matched:
            doc_lines.append(f"- {doc.path} :: {doc.title}")
            excerpt = " ".join(doc.body.splitlines()[:3]).strip()
            if excerpt:
                doc_lines.append(f"  excerpt={excerpt[:280]}")
    return "\n".join(
        [
            "Continue the K-AIDF mentor workflow as a quiz-style guided process.",
            "Use the framework documents, the existing workflow state, and the user's latest answer.",
            "Analyze the answer, say what should be clarified, decided, or modified next, and keep the guidance pragmatic.",
            "Do not restart the workflow. Continue from the current point.",
            "Ask exactly one next question at the end.",
            "",
            f"Current pending category: {pending_category}",
            f"Current pending document: {pending_document_path}",
            f"Current question: {pending_question}",
            "",
            "Recent workflow history:",
            *history_lines,
            "",
            "Relevant framework excerpts:",
            *doc_lines,
            "",
            "User answer:",
            answer,
        ]
    )


def _offline_reply(
    documents: list[Document],
    state: MentorState,
    pending_question: str,
    pending_category: str,
    pending_document_path: str,
    answer: str,
) -> str:
    from .controller import select_context_documents

    matched = select_context_documents(documents, f"{pending_category} {answer}", limit=1)
    focus = matched[0].path if matched else pending_document_path
    assessment = _classify_answer(answer)
    prior = "no prior answers yet" if not state.interactions else f"{len(state.interactions)} prior answers recorded"
    return (
        f"Mentor assessment: {assessment}. "
        f"Current focus remains {pending_category} using {focus}. "
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


def _select_next_document(documents: list[Document], state: MentorState) -> Document:
    answered_categories = {item.category for item in state.interactions}
    for category in WORKFLOW_CATEGORY_ORDER:
        if category in answered_categories:
            continue
        for doc in documents:
            if _document_category(doc) == category:
                return doc
    return documents[0]


def _choose_next_question(
    documents: list[Document],
    interactions: list[MentorInteraction],
    answer: str,
    fallback_document: Document,
) -> str:
    from .controller import select_context_documents

    matched = select_context_documents(documents, answer, limit=1)
    if matched and _document_category(matched[0]) not in {item.category for item in interactions}:
        return _question_for_document(matched[0])
    return _question_for_document(fallback_document)


def _question_for_document(doc: Document) -> str:
    category = _document_category(doc)
    return QUESTION_TEMPLATES.get(category, QUESTION_TEMPLATES["general"])


def _document_category(doc: Document) -> str:
    return doc.doctrine_category if doc.doctrine_category in QUESTION_TEMPLATES else "general"


def _default_question(documents: list[Document]) -> str:
    return _question_for_document(documents[0])


def _format_pending_question(question: str, category: str | None, document_path: str | None) -> str:
    lines = ["Mentor workflow is active."]
    if category:
        lines.append(f"Current focus: {category}")
    if document_path:
        lines.append(f"Reference: {document_path}")
    lines.append(f"Question: {question}")
    return "\n".join(lines)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
