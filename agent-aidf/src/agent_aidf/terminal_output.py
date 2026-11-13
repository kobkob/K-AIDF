"""Rich terminal output for `kob status` and `kob mentor`, with plain fallbacks.

Rich layouts are used only on an interactive terminal that can show them: a TTY, UTF-8 output,
and neither NO_COLOR nor TERM=dumb set. Everywhere else (pipes, CI logs, redirected output) the
commands print the plain text they always printed, and `kob status --json` prints JSON. The data
behind all three is built by the functions in this module, so the outputs cannot drift apart.
"""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .audit import STATUS_STYLES, TIER_STYLES, AuditResult, _progress_bar, _status
from .controller import resolve_local_model
from .project import ProjectStatus
from .tools import is_yolo_enabled

PHASE_TOTAL = 5
CHEVRON = "❯"
CHEVRON_ASCII = ">"
# Background chips for the maturity tag at the top of the mentor panel, by KAIDF-AMM tier.
TIER_TAG_STYLES = {
    "Platinum": "bold black on bright_green",
    "Gold": "bold black on green",
    "Silver": "bold black on yellow",
}
UNRATED_TAG_STYLE = "bold white on red"


def use_rich(console: Console) -> bool:
    """True when the Rich layout can be shown as designed; False selects the plain fallback."""
    if not console.is_terminal:
        return False
    if os.environ.get("NO_COLOR") or os.environ.get("TERM", "").lower() == "dumb":
        return False
    return "utf" in (console.encoding or "").lower()


def active_model() -> dict[str, str]:
    """The provider and model the next controller will use, resolved the way build_controller()
    resolves them."""
    provider = os.environ.get("AIDF_CHAT_PROVIDER", "").strip().lower() or "ollama"
    if provider == "none":
        return {"provider": "none", "model": "-"}
    if provider == "openai":
        return {"provider": "openai", "model": os.environ.get("OPENAI_MODEL", "gpt-5")}
    return {"provider": "ollama", "model": resolve_local_model()}


def extension_summary(inventory: dict[str, Any]) -> dict[str, int]:
    counts = {"loaded": 0, "failed": 0, "disabled": 0}
    for row in inventory.get("extensions", []):
        state = row.get("state")
        if state in counts:
            counts[state] += 1
    counts["total"] = len(inventory.get("extensions", []))
    return counts


def scorecard_payload(result: AuditResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "score": result.score,
        "max_score": result.max_score,
        "tier": result.tier,
        "scaffold": result.scaffold_label,
        "dimensions": [
            {
                "id": dimension.id,
                "name": dimension.name,
                "points": dimension.points,
                "max_points": dimension.max_points,
                "status": _status(dimension.points, dimension.max_points),
            }
            for dimension in result.dimensions
        ],
    }


def status_payload(
    status: ProjectStatus,
    *,
    phases: list[dict],
    scorecard: AuditResult | None,
    extensions: dict[str, int],
    model: dict[str, str],
) -> dict[str, Any]:
    accepted = len(status.mentor_accepted_phases)
    return {
        "project_root": str(status.project_root),
        "repo_root": str(status.repo_root),
        "has_kaidf": status.has_kaidf,
        "packs": status.packs,
        "instant_apps": status.instant_apps,
        "mentor": {
            "step_count": status.mentor_step_count,
            "pending_category": status.mentor_pending_category,
            "accepted_phases": status.mentor_accepted_phases,
        },
        "phases": {
            "accepted": accepted,
            "total": PHASE_TOTAL,
            "items": [
                {"order": phase["order"], "name": phase["name"], "state": phase["state"]}
                for phase in phases
            ],
        },
        "scorecard": scorecard_payload(scorecard),
        "extensions": extensions,
        "model": model,
        "yolo": is_yolo_enabled(),
    }


def plain_status_lines(
    status: ProjectStatus, *, phases: list[dict], extensions: dict[str, int], model: dict[str, str]
) -> list[str]:
    """The key: value lines `kob status` always printed, with the new fields appended."""
    accepted = len(status.mentor_accepted_phases)
    return [
        f"project_root: {status.project_root}",
        f"repo_root: {status.repo_root}",
        f"has_kaidf: {'yes' if status.has_kaidf else 'no'}",
        f"pack_count: {status.pack_count}",
        f"mentor_step_count: {status.mentor_step_count}",
        f"phases_accepted: {accepted}/{PHASE_TOTAL}",
        f"model: {model['provider']} {model['model']}",
        f"extensions: {extensions['loaded']} loaded, {extensions['failed']} failed, "
        f"{extensions['disabled']} disabled",
    ]


def pipeline_text(phases: list[dict], *, ascii_only: bool = False) -> Text:
    """The five phases as a horizontal chevron pipeline. The current phase is highlighted, done
    phases are green with a check, and pending phases are dim."""
    chevron = CHEVRON_ASCII if ascii_only else CHEVRON
    text = Text()
    for index, phase in enumerate(phases):
        if index:
            text.append(f" {chevron} ", style="dim")
        state = phase["state"]
        label = f" {phase['order']}. {phase['name']} "
        if state == "done":
            text.append(("[x]" if ascii_only else "✔") + label, style="bold green")
        elif state == "current":
            text.append(("[>]" if ascii_only else "▶") + label, style="bold black on yellow")
        else:
            text.append(label, style="dim")
    return text


def _scorecard_table(result: AuditResult) -> Table:
    table = Table("Dimension", "Score", "Status", "Progress")
    for dimension in result.dimensions:
        state = _status(dimension.points, dimension.max_points)
        table.add_row(
            Text(dimension.name),
            f"{dimension.points}/{dimension.max_points}",
            Text(state, style=STATUS_STYLES[state]),
            Text(
                _progress_bar(dimension.points, dimension.max_points),
                style=STATUS_STYLES[state],
            ),
        )
    return table


def render_status(
    console: Console,
    status: ProjectStatus,
    *,
    phases: list[dict],
    scorecard: AuditResult | None,
    extensions: dict[str, int],
    model: dict[str, str],
) -> None:
    accepted = len(status.mentor_accepted_phases)
    facts = Table.grid(padding=(0, 2))
    facts.add_column(style="bold")
    facts.add_column()
    facts.add_row("Project", str(status.project_root))
    facts.add_row("Repository", str(status.repo_root) if status.has_kaidf else "not initialized")
    facts.add_row("Model", Text(f"{model['provider']} · {model['model']}", style="cyan"))
    facts.add_row(
        "Extensions",
        Text(
            f"{extensions['loaded']} loaded, {extensions['failed']} failed, "
            f"{extensions['disabled']} disabled",
            style="red" if extensions["failed"] else "green",
        ),
    )
    console.print(Panel(facts, title="K-AIDF status", title_align="left"))

    progress = Text(f"{accepted}/{PHASE_TOTAL} accepted", style="bold")
    console.print(
        Panel(
            pipeline_text(phases),
            title="Delivery phases",
            subtitle=progress,
            subtitle_align="right",
            title_align="left",
        )
    )

    if scorecard is None:
        console.print(Text("KAIDF-AMM scorecard unavailable for this project.", style="dim"))
        return
    tier_style = TIER_STYLES[scorecard.tier]
    headline = Text()
    headline.append(f"Score {scorecard.score}/{scorecard.max_score}", style=tier_style)
    headline.append("    ")
    headline.append(f"Tier {scorecard.tier}", style=tier_style)
    headline_grid = Table.grid()
    headline_grid.add_row(headline)
    console.print(
        Panel(
            headline_grid,
            title="KAIDF-AMM v1.0",
            subtitle=f"Scaffold: {scorecard.scaffold_label}",
            title_align="left",
        )
    )
    console.print(_scorecard_table(scorecard))


def mentor_tags(scorecard: AuditResult | None, status: ProjectStatus) -> Text:
    """The maturity and ethics context shown at the top of the mentor panel."""
    tags = Text()
    if scorecard is None:
        tags.append(" Maturity: unscored ", style="bold white on grey37")
    else:
        chip = TIER_TAG_STYLES.get(scorecard.tier, UNRATED_TAG_STYLE)
        tags.append(
            f" Maturity {scorecard.score}/{scorecard.max_score} · {scorecard.tier} ", style=chip
        )
    tags.append("  ")
    has_ethics = "ethical-model" in status.packs
    if has_ethics:
        tags.append(" Ethics: ethical-model pack ", style="bold black on green")
    else:
        tags.append(" Ethics: no ethical-model pack ", style="bold black on yellow")
    return tags


def mentor_body(message: str, pending_question: str | None) -> str:
    """The mentor's message without the question the panel is about to show."""
    if not pending_question:
        return message
    question = pending_question.strip()
    # The question appears bare, or after one of the labels the mentor uses for it.
    shown_as = {question, f"Question: {question}", f"Next question: {question}"}
    kept = [line for line in message.splitlines() if line.strip() not in shown_as]
    return "\n".join(kept).strip()


def render_mentor_turn(
    console: Console,
    *,
    message: str,
    pending_question: str | None,
    pending_category: str | None,
    phase_order: int,
    scorecard: AuditResult | None,
    status: ProjectStatus,
) -> None:
    body = mentor_body(message, pending_question)
    if body:
        console.print(Text(body))
    if not pending_question:
        return
    title = f"Mentor · phase {phase_order}/{PHASE_TOTAL}"
    if pending_category:
        title += f" · {pending_category}"
    content = Table.grid()
    content.add_row(mentor_tags(scorecard, status))
    content.add_row(Text(""))
    content.add_row(Text(pending_question))
    console.print(Panel(content, title=title, title_align="left", border_style="cyan"))
