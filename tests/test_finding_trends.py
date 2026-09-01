"""The findings burn-down series that backs the console's trend card."""

from __future__ import annotations

from datetime import date

from core.finding_trends import MAX_WINDOW_DAYS, build_trend

TODAY = date(2026, 9, 1)


def _job(day: str, statuses: list[str], status: str = "completed", **extra):
    return {
        "status": status,
        "completed_at": f"{day}T12:00:00+00:00",
        "summary": {"findings": [{"remediation_state": {"status": item}} for item in statuses]},
        **extra,
    }


def test_no_completed_scans_produces_no_series() -> None:
    """An empty chart is honest; a fabricated flat line would not be."""
    assert build_trend([], days=7, today=TODAY) == []
    assert build_trend([_job("2026-08-30", ["open"], status="failed")], days=7, today=TODAY) == []


def test_open_and_remediated_are_counted_from_the_persisted_status() -> None:
    points = build_trend([_job("2026-09-01", ["open", "fixed", "triaged"])], days=1, today=TODAY)
    assert [point.to_dict() for point in points] == [{"date": "2026-09-01", "open": 2, "remediated": 1}]


def test_deliberate_closures_leave_open_without_counting_as_remediated() -> None:
    """`wont_fix` and friends are resolved, not repaired."""
    points = build_trend(
        [_job("2026-09-01", ["false_positive", "wont_fix", "accepted_risk", "open"])],
        days=1,
        today=TODAY,
    )
    assert points[0].open == 1
    assert points[0].remediated == 0


def test_a_quiet_day_carries_the_previous_posture_forward() -> None:
    points = build_trend([_job("2026-08-30", ["open", "open"])], days=3, today=TODAY)
    assert [(point.date, point.open) for point in points] == [
        ("2026-08-30", 2),
        ("2026-08-31", 2),
        ("2026-09-01", 2),
    ]


def test_days_before_the_first_scan_are_not_emitted() -> None:
    points = build_trend([_job("2026-08-31", ["open"])], days=5, today=TODAY)
    assert [point.date for point in points] == ["2026-08-31", "2026-09-01"]


def test_a_scan_before_the_window_still_seeds_the_opening_day() -> None:
    """Opening on a quiet day must show the real posture, not an empty chart."""
    points = build_trend([_job("2026-07-01", ["open", "fixed"])], days=2, today=TODAY)
    assert [(point.date, point.open, point.remediated) for point in points] == [
        ("2026-08-31", 1, 1),
        ("2026-09-01", 1, 1),
    ]


def test_the_last_run_of_a_day_is_that_day_s_posture() -> None:
    early = _job("2026-09-01", ["open", "open"])
    late = {**_job("2026-09-01", ["fixed", "fixed"]), "completed_at": "2026-09-01T18:00:00+00:00"}
    assert build_trend([early, late], days=1, today=TODAY)[0].open == 0
    # Arrival order must not change the answer.
    assert build_trend([late, early], days=1, today=TODAY)[0].open == 0


def test_the_window_is_clamped_to_a_sane_range() -> None:
    jobs = [_job("2026-09-01", ["open"])]
    assert len(build_trend(jobs, days=0, today=TODAY)) == 1
    assert len(build_trend(jobs, days=100_000, today=TODAY)) <= MAX_WINDOW_DAYS


def test_an_unparseable_timestamp_is_skipped_rather_than_crashing() -> None:
    broken = {"status": "completed", "completed_at": "not-a-date", "summary": {"findings": []}}
    assert build_trend([broken, _job("2026-09-01", ["open"])], days=1, today=TODAY)[0].open == 1
