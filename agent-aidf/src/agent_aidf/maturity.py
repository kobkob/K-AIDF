from __future__ import annotations

from .contracts import basic_phase_definitions
from .project import ProjectStatus

TOTAL_PHASES = len(basic_phase_definitions())


def phase_progress(status: ProjectStatus) -> tuple[int, int]:
    """How many of the 5 K-AIDF Basic phases have been explicitly accepted.

    A phase only counts once its artifact files are actually filled in AND the user has
    explicitly accepted it - never from raw question/step count (see mentor.py).
    """
    if not status.has_kaidf:
        return 0, TOTAL_PHASES
    accepted = len(status.mentor_accepted_phases)
    return min(TOTAL_PHASES, accepted), TOTAL_PHASES


def phase_snapshot(status: ProjectStatus) -> list[dict]:
    """The 5 phases annotated with a "done"/"current"/"pending" state for the current status."""
    accepted_orders = set(status.mentor_accepted_phases)
    completed, total = phase_progress(status)
    snapshot = []
    for phase in basic_phase_definitions():
        order = phase["order"]
        if order in accepted_orders:
            state = "done"
        elif order == completed + 1 and status.has_kaidf and completed < total:
            state = "current"
        else:
            state = "pending"
        snapshot.append({**phase, "state": state})
    return snapshot
