from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .instant_apps import get_instant_app, load_instant_app_runtime
from .mentor import load_mentor_state
from .repo import resolve_repo_root

CONTRACTS_DIRNAME = "contracts"
CONTRACT_FILENAME = "contract.json"
CONTRACT_MARKDOWN_FILENAME = "contract.md"
QUIZ_FILENAME = "quiz.md"

_BASIC_PHASES = (
    {
        "order": 1,
        "name": "Intent & Constraints",
        "human_role": "Define goals, boundaries, stakeholders, and non-negotiable limits.",
        "ai_role": "Analyze ambiguity, surface risks, and turn intent into a workable brief.",
        "deliverables": ["Brief", "Scope", "Constraints register"],
        "exit_criteria": "Objectives, constraints, and decision boundaries are explicit.",
        "quiz_prompts": [
            "What outcome should this project achieve first, and why does it matter now?",
            "Which constraints are non-negotiable for privacy, governance, cost, or timing?",
        ],
    },
    {
        "order": 2,
        "name": "Discovery & Mapping",
        "human_role": "Provide operational context, current flows, dependencies, and source material.",
        "ai_role": "Map systems, user flows, MCP/tooling touchpoints, and unresolved requirements.",
        "deliverables": ["System map", "Context inventory", "Requirements list"],
        "exit_criteria": "Relevant systems, actors, and requirements are mapped clearly enough to design against.",
        "quiz_prompts": [
            "Which systems, data sources, MCP servers, or repos does this workflow need to touch?",
            "What is unclear in the current process that the mentor should map before design starts?",
        ],
    },
    {
        "order": 3,
        "name": "Design & Simulation",
        "human_role": "Approve direction and reject unsafe or low-value options.",
        "ai_role": "Generate blueprints, simulate flows, and shape instant-app prototypes for review.",
        "deliverables": ["Blueprint", "Prototype plan", "Review checklist"],
        "exit_criteria": "The chosen concept is understandable, reviewable, and safe to execute.",
        "quiz_prompts": [
            "What is the smallest prototype, quiz flow, or instant app that proves the direction?",
            "Which design assumptions need simulation or human review before implementation continues?",
        ],
    },
    {
        "order": 4,
        "name": "Execution & Instrumentation",
        "human_role": "Oversee execution, approve critical changes, and monitor outcomes.",
        "ai_role": "Assist implementation, run guided tasks, and instrument runtime visibility.",
        "deliverables": ["Working system", "Instrumentation plan", "Runtime notes"],
        "exit_criteria": "The system runs, is observable, and is moving toward target metrics.",
        "quiz_prompts": [
            "What should the mentor implement or update first in the active instant app or workflow?",
            "Which metrics, logs, or checkpoints are required to know execution is healthy?",
        ],
    },
    {
        "order": 5,
        "name": "Verification & Transfer",
        "human_role": "Review the result, accept or reject it, and prepare ownership transfer.",
        "ai_role": "Audit the outcome, summarize evidence, and package handover material.",
        "deliverables": ["Verification report", "Handover notes", "Next-step backlog"],
        "exit_criteria": "Acceptance is explicit and ownership is transferred with enough context to continue.",
        "quiz_prompts": [
            "What evidence must exist before this work is considered verified and transferable?",
            "Who owns the result after handover, and what documentation or training do they need?",
        ],
    },
)


@dataclass(frozen=True)
class ContractPhase:
    order: int
    name: str
    human_role: str
    ai_role: str
    deliverables: list[str]
    exit_criteria: str
    quiz_prompts: list[str]


@dataclass(frozen=True)
class BasicContract:
    contract_id: str
    title: str
    root: Path
    brief: str
    source_summary: str
    ai_guidance: str | None
    current_app_id: str | None
    current_app_url: str | None
    phases: list[ContractPhase]


def list_contracts(repo_root: str | Path | None) -> list[BasicContract]:
    contracts_root = _contracts_root(repo_root)
    if not contracts_root.is_dir():
        return []
    contracts: list[BasicContract] = []
    for candidate in sorted(path for path in contracts_root.iterdir() if path.is_dir()):
        contract = load_contract(candidate)
        if contract is not None:
            contracts.append(contract)
    return contracts


def load_contract(ref: str | Path) -> BasicContract | None:
    root = Path(ref).expanduser().resolve()
    payload_path = root / CONTRACT_FILENAME
    if not payload_path.is_file():
        return None
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    phases_raw = data.get("phases", [])
    phases: list[ContractPhase] = []
    if isinstance(phases_raw, list):
        for item in phases_raw:
            if not isinstance(item, dict):
                continue
            try:
                phases.append(
                    ContractPhase(
                        order=int(item["order"]),
                        name=str(item["name"]),
                        human_role=str(item["human_role"]),
                        ai_role=str(item["ai_role"]),
                        deliverables=[str(entry) for entry in item.get("deliverables", [])],
                        exit_criteria=str(item["exit_criteria"]),
                        quiz_prompts=[str(entry) for entry in item.get("quiz_prompts", [])],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    try:
        return BasicContract(
            contract_id=str(data["contract_id"]),
            title=str(data["title"]),
            root=root,
            brief=str(data["brief"]),
            source_summary=str(data["source_summary"]),
            ai_guidance=_optional_str(data.get("ai_guidance")),
            current_app_id=_optional_str(data.get("current_app_id")),
            current_app_url=_optional_str(data.get("current_app_url")),
            phases=phases,
        )
    except (KeyError, TypeError, ValueError):
        return None


def get_contract(repo_root: str | Path | None, ref: str) -> BasicContract | None:
    direct = load_contract(ref)
    if direct is not None:
        return direct
    return load_contract(_contracts_root(repo_root) / _slugify(ref))


def create_basic_contract(
    repo_root: str | Path | None,
    *,
    contract_id: str | None = None,
    brief: str | None = None,
    force: bool = False,
) -> BasicContract:
    repo = resolve_repo_root(repo_root)
    mentor_state = load_mentor_state(repo)
    current_app = get_instant_app(repo, mentor_state.current_app_id) if mentor_state.current_app_id else None
    current_runtime = (
        load_instant_app_runtime(repo, mentor_state.current_app_id)
        if mentor_state.current_app_id
        else None
    )
    source_summary = _build_source_summary(mentor_state, current_app_id=mentor_state.current_app_id)
    effective_brief = _build_contract_brief(brief, mentor_state)
    slug = _slugify(contract_id or _default_contract_id(mentor_state, effective_brief))
    root = _contracts_root(repo) / slug
    if root.exists():
        if not force:
            raise ValueError(f"Contract already exists: {root}")
    else:
        root.mkdir(parents=True, exist_ok=True)
    ai_guidance = _generate_ai_guidance(
        repo,
        brief=effective_brief,
        source_summary=source_summary,
        current_app_id=mentor_state.current_app_id,
    )
    title = _build_title(slug, effective_brief)
    phases = [ContractPhase(**phase) for phase in _BASIC_PHASES]
    contract = BasicContract(
        contract_id=slug,
        title=title,
        root=root,
        brief=effective_brief,
        source_summary=source_summary,
        ai_guidance=ai_guidance,
        current_app_id=current_app.app_id if current_app else None,
        current_app_url=(
            f"http://127.0.0.1:{current_runtime.port}"
            if current_runtime and current_runtime.status == "running" and current_runtime.port
            else None
        ),
        phases=phases,
    )
    _write_contract_files(contract)
    return contract


def _contracts_root(repo_root: str | Path | None) -> Path:
    repo = resolve_repo_root(repo_root)
    root = repo / CONTRACTS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_contract_brief(brief: str | None, mentor_state: object) -> str:
    if isinstance(brief, str) and brief.strip():
        return _normalize_sentence(brief)
    state = mentor_state
    interactions = getattr(state, "interactions", [])
    if interactions:
        recent_answers = [item.answer.strip() for item in interactions[-2:] if item.answer.strip()]
        if recent_answers:
            return _normalize_sentence(" ".join(recent_answers))
    pending_question = getattr(state, "pending_question", None)
    if isinstance(pending_question, str) and pending_question:
        return f"Create a basic K-AIDF contract that resolves: {pending_question}"
    return "Create a basic K-AIDF contract for the current project and mentor workflow."


def _build_source_summary(mentor_state: object, *, current_app_id: str | None) -> str:
    interactions = getattr(mentor_state, "interactions", [])
    parts = [
        f"mentor_step_count={getattr(mentor_state, 'step_count', 0)}",
        f"pending_category={getattr(mentor_state, 'pending_category', None) or 'none'}",
        f"current_app_id={current_app_id or 'none'}",
    ]
    if interactions:
        latest = interactions[-1]
        parts.append(f"latest_answer={_truncate(latest.answer, 140)}")
        parts.append(f"latest_action={_truncate(latest.action_summary or 'none', 140)}")
    else:
        parts.append("latest_answer=none")
        parts.append("latest_action=none")
    return "; ".join(parts)


def _generate_ai_guidance(
    repo_root: Path,
    *,
    brief: str,
    source_summary: str,
    current_app_id: str | None,
) -> str | None:
    from .controller import build_controller

    prompt = "\n".join(
        [
            "Produce a short mentor note for a K-AIDF basic contract.",
            "Keep it pragmatic and under 120 words.",
            "Reference mentor, quizzes, instant apps, and MCP only when they are relevant.",
            f"Brief: {brief}",
            f"Source summary: {source_summary}",
            f"Current app: {current_app_id or 'none'}",
        ]
    )
    raw = build_controller().chat(prompt, repo_root)
    if raw.startswith("AI chat controller is not configured yet."):
        return None
    return raw.strip()


def _write_contract_files(contract: BasicContract) -> None:
    payload = {
        "contract_id": contract.contract_id,
        "title": contract.title,
        "brief": contract.brief,
        "source_summary": contract.source_summary,
        "ai_guidance": contract.ai_guidance,
        "current_app_id": contract.current_app_id,
        "current_app_url": contract.current_app_url,
        "phases": [asdict(phase) for phase in contract.phases],
    }
    (contract.root / CONTRACT_FILENAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (contract.root / CONTRACT_MARKDOWN_FILENAME).write_text(_contract_markdown(contract), encoding="utf-8")
    (contract.root / QUIZ_FILENAME).write_text(_quiz_markdown(contract), encoding="utf-8")


def _contract_markdown(contract: BasicContract) -> str:
    lines = [
        f"# {contract.title}",
        "",
        "## Contract Brief",
        "",
        contract.brief,
        "",
        "## Operating Context",
        "",
        f"- Source summary: {contract.source_summary}",
        f"- Current instant app: {contract.current_app_id or 'none'}",
        f"- Current app URL: {contract.current_app_url or 'none'}",
    ]
    if contract.ai_guidance:
        lines.extend(["", "## AI Guidance", "", contract.ai_guidance])
    lines.extend(["", "## Basic Framework Phases", ""])
    for phase in contract.phases:
        lines.extend(
            [
                f"### {phase.order}. {phase.name}",
                "",
                f"- Human: {phase.human_role}",
                f"- AI: {phase.ai_role}",
                f"- Deliverables: {', '.join(phase.deliverables)}",
                f"- Exit: {phase.exit_criteria}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _quiz_markdown(contract: BasicContract) -> str:
    lines = [f"# {contract.title} Quiz Flow", ""]
    for phase in contract.phases:
        lines.extend([f"## {phase.order}. {phase.name}", ""])
        for prompt in phase.quiz_prompts:
            lines.append(f"- {prompt}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _default_contract_id(mentor_state: object, brief: str) -> str:
    current_app_id = getattr(mentor_state, "current_app_id", None)
    if isinstance(current_app_id, str) and current_app_id:
        return f"{current_app_id}-contract"
    first_sentence = brief.split(".", 1)[0]
    words = [token for token in re.split(r"[^a-z0-9]+", first_sentence.casefold()) if token]
    if not words:
        return "basic-contract"
    return "-".join(words[:6]) + "-contract"


def _build_title(contract_id: str, brief: str) -> str:
    first_sentence = brief.split(".", 1)[0].strip()
    if first_sentence:
        return _truncate(first_sentence, 80)
    return contract_id.replace("-", " ").title()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "basic-contract"


def _normalize_sentence(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return "Create a basic K-AIDF contract for the current project."
    return cleaned


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
