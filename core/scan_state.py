from __future__ import annotations

from enum import Enum


class ScanRunState(str, Enum):
    """Explicit states a scan run can occupy.

    Only states that correspond to something the runner actually does. The four
    original informal values keep their stored names so persisted rows written
    before the state machine existed stay valid.
    """

    QUEUED = "queued"
    RUNNING = "running"
    ANALYSING = "analysing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


TERMINAL_STATES: frozenset[ScanRunState] = frozenset(
    {
        ScanRunState.COMPLETED,
        ScanRunState.CANCELLED,
        ScanRunState.TIMED_OUT,
        ScanRunState.FAILED,
    }
)

#: Every legal move. A state absent from a value set cannot be reached from that
#: key, and terminal states have no outgoing moves at all.
ALLOWED_TRANSITIONS: dict[ScanRunState, frozenset[ScanRunState]] = {
    ScanRunState.QUEUED: frozenset(
        {
            ScanRunState.RUNNING,
            ScanRunState.CANCELLED,
            ScanRunState.TIMED_OUT,
            ScanRunState.FAILED,
        }
    ),
    ScanRunState.RUNNING: frozenset(
        {
            ScanRunState.ANALYSING,
            ScanRunState.CANCELLED,
            ScanRunState.TIMED_OUT,
            ScanRunState.FAILED,
        }
    ),
    ScanRunState.ANALYSING: frozenset(
        {
            ScanRunState.COMPLETED,
            ScanRunState.CANCELLED,
            ScanRunState.TIMED_OUT,
            ScanRunState.FAILED,
        }
    ),
    ScanRunState.COMPLETED: frozenset(),
    ScanRunState.CANCELLED: frozenset(),
    ScanRunState.TIMED_OUT: frozenset(),
    ScanRunState.FAILED: frozenset(),
}


class InvalidScanTransition(ValueError):
    """Raised when a scan is asked to move to a state it cannot reach."""


def coerce(value: str | ScanRunState) -> ScanRunState:
    """Read a stored status string as a state, defaulting unknown text to FAILED.

    An unrecognised status is a corrupt record, not a new state: treating it as
    terminal stops it being resurrected into a run that nothing is executing.
    """
    if isinstance(value, ScanRunState):
        return value
    try:
        return ScanRunState(str(value).strip().lower())
    except ValueError:
        return ScanRunState.FAILED


def is_terminal(value: str | ScanRunState) -> bool:
    return coerce(value) in TERMINAL_STATES


def transition(current: str | ScanRunState, target: str | ScanRunState) -> ScanRunState:
    """Return ``target`` if the move is legal, otherwise raise.

    Every status change goes through here so an illegal move fails loudly rather
    than silently corrupting the record.
    """
    source_state = coerce(current)
    target_state = coerce(target)
    if target_state not in ALLOWED_TRANSITIONS[source_state]:
        raise InvalidScanTransition(f"cannot move a scan from '{source_state.value}' to '{target_state.value}'")
    return target_state
