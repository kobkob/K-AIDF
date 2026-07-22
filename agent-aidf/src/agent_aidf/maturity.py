from __future__ import annotations

from .contracts import basic_phase_definitions
from .project import ProjectStatus

TOTAL_PHASES = len(basic_phase_definitions())


def phase_progress(status: ProjectStatus) -> tuple[int, int]:
    """How many of the 5 K-AIDF Basic phases the mentor workflow has stepped through."""
    if not status.has_kaidf:
        return 0, TOTAL_PHASES
    return min(TOTAL_PHASES, status.mentor_step_count), TOTAL_PHASES


def phase_snapshot(status: ProjectStatus) -> list[dict]:
    """The 5 phases annotated with a "done"/"current"/"pending" state for the current status."""
    completed, total = phase_progress(status)
    snapshot = []
    for phase in basic_phase_definitions():
        order = phase["order"]
        if order <= completed:
            state = "done"
        elif order == completed + 1 and status.has_kaidf and completed < total:
            state = "current"
        else:
            state = "pending"
        snapshot.append({**phase, "state": state})
    return snapshot
