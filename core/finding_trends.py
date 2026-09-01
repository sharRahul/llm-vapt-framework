"""Findings burn-down aggregated across scans over time.

The console's burn-down card had no data source: every scan was read in
isolation, so nothing knew how many findings were open yesterday. This module
turns the persisted scan history into one series — open versus remediated per
day — which is the only claim the stored data actually supports.

A day with no completed scan carries the previous day's counts forward: the
posture did not change because nothing was assessed, and drawing a drop to zero
would be a lie. Days before the first completed scan are not emitted at all.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

#: Statuses that mean the finding no longer counts as open work. ``fixed`` is
#: the only one that is remediation; the rest are closures the operator made
#: deliberately, and lumping them into "open" would never let a burn-down land.
CLOSED_STATUSES = frozenset({"fixed", "false_positive", "wont_fix", "accepted_risk"})

#: Only ``fixed`` is counted as remediated. The other closed statuses are
#: resolved but not repaired, and the chart must not imply otherwise.
REMEDIATED_STATUSES = frozenset({"fixed"})

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """One day of the burn-down series."""

    date: str
    open: int
    remediated: int

    def to_dict(self) -> dict[str, Any]:
        return {"date": self.date, "open": self.open, "remediated": self.remediated}


def _finding_status(finding: Mapping[str, Any]) -> str:
    state = finding.get("remediation_state")
    if isinstance(state, Mapping) and state.get("status"):
        return str(state["status"]).strip().lower()
    return str(finding.get("status") or "open").strip().lower()


def _scan_day(job: Mapping[str, Any]) -> date | None:
    """The day a run's results belong to, or None when it never produced any."""
    stamp = job.get("completed_at") or job.get("started_at") or job.get("created_at")
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def _counts(findings: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    open_count = 0
    remediated = 0
    for finding in findings:
        status = _finding_status(finding)
        if status in REMEDIATED_STATUSES:
            remediated += 1
        if status not in CLOSED_STATUSES:
            open_count += 1
    return open_count, remediated


def build_trend(
    jobs: Iterable[Mapping[str, Any]],
    days: int = DEFAULT_WINDOW_DAYS,
    today: date | None = None,
) -> list[TrendPoint]:
    """Build the open/remediated series for the last ``days`` days.

    ``jobs`` are scan records as ``to_dict`` returns them. Only runs that
    finished successfully contribute: a cancelled or failed run stopped early,
    so its finding count is not a measurement of the target.
    """
    window = max(1, min(int(days or DEFAULT_WINDOW_DAYS), MAX_WINDOW_DAYS))
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=window - 1)

    # Several runs can land on one day; the latest one is that day's posture,
    # so the record is keyed by its own timestamp rather than by arrival order.
    latest: dict[date, tuple[str, tuple[int, int]]] = {}
    for job in jobs:
        if str(job.get("status") or "").strip().lower() != "completed":
            continue
        day = _scan_day(job)
        if day is None:
            continue
        stamp = str(job.get("completed_at") or job.get("started_at") or job.get("created_at") or "")
        summary = job.get("summary")
        findings = summary.get("findings") if isinstance(summary, Mapping) else None
        counts = _counts(findings or [])
        if day not in latest or stamp >= latest[day][0]:
            latest[day] = (stamp, counts)
    per_day = {day: counts for day, (_, counts) in latest.items()}

    if not per_day:
        return []

    first_measured = min(per_day)
    carried: tuple[int, int] | None = None
    # Seed the carry-forward with the most recent measurement before the window
    # so a window that opens on a quiet day still starts at the real posture.
    for day in sorted(per_day):
        if day < start:
            carried = per_day[day]

    points: list[TrendPoint] = []
    for offset in range(window):
        day = start + timedelta(days=offset)
        if day in per_day:
            carried = per_day[day]
        if carried is None or day < first_measured:
            continue
        points.append(TrendPoint(day.isoformat(), carried[0], carried[1]))
    return points
