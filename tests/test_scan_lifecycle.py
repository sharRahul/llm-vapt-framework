"""The scan run lifecycle: states, transitions, cancellation, and recovery.

A scan run used to have no modelled lifecycle at all: ``status`` was a plain
string assigned from several call sites, nothing could be cancelled, a timeout
was indistinguishable from a failure, and a restart stranded in-flight rows in
``running`` forever. These tests pin each of those down.
"""

from __future__ import annotations

import threading

import pytest

from core.cancellation import CancellationRegistry, CancellationToken, ScanCancelled, ScanTimedOut
from core.scan_state import (
    InvalidScanTransition,
    ScanRunState,
    coerce,
    is_terminal,
    transition,
)
from webui import hosted_server
from webui.persistent_jobs import PersistedScanJob, PersistentJobStore, SqliteJobStore


def _stored(store, job_id: str) -> PersistedScanJob:
    """Fetch a job that must exist, so assertions read against a concrete record."""
    job = store.get(job_id)
    assert job is not None
    return job


# --- the state machine ------------------------------------------------------------


def test_a_legal_transition_returns_the_target_state() -> None:
    assert transition("queued", "running") is ScanRunState.RUNNING
    assert transition(ScanRunState.RUNNING, ScanRunState.ANALYSING) is ScanRunState.ANALYSING
    assert transition("analysing", "completed") is ScanRunState.COMPLETED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("completed", "running"),
        ("failed", "completed"),
        ("cancelled", "running"),
        ("timed_out", "analysing"),
        ("queued", "analysing"),
        ("queued", "completed"),
        ("running", "queued"),
    ],
)
def test_an_illegal_transition_raises(current: str, target: str) -> None:
    with pytest.raises(InvalidScanTransition):
        transition(current, target)


def test_every_terminal_state_is_a_dead_end() -> None:
    for state in ScanRunState:
        if not is_terminal(state):
            continue
        for other in ScanRunState:
            with pytest.raises(InvalidScanTransition):
                transition(state, other)


def test_an_unknown_stored_status_reads_as_terminal() -> None:
    """A corrupt status must not be resurrected into a run nothing is executing."""
    assert coerce("not-a-real-state") is ScanRunState.FAILED
    assert is_terminal("not-a-real-state")


def test_cancelled_and_timed_out_are_distinct_from_failed() -> None:
    assert ScanRunState.CANCELLED.value != ScanRunState.FAILED.value
    assert ScanRunState.TIMED_OUT.value != ScanRunState.FAILED.value


# --- cancellation tokens ------------------------------------------------------------


def test_a_cancelled_token_raises_at_the_next_boundary() -> None:
    token = CancellationToken()
    token.raise_if_stopped()
    token.cancel("cancelled by operator", actor="alice")

    with pytest.raises(ScanCancelled):
        token.raise_if_stopped()
    assert token.actor == "alice"


def test_an_exhausted_budget_raises_a_timeout_not_a_cancellation() -> None:
    token = CancellationToken(budget_seconds=0)

    with pytest.raises(ScanTimedOut):
        token.raise_if_stopped()


def test_the_registry_reaches_a_token_by_run_id() -> None:
    registry = CancellationRegistry()
    token = registry.create("run-1")

    assert registry.cancel("run-1", reason="stop", actor="bob") is True
    assert token.cancelled is True
    assert registry.cancel("no-such-run") is False

    registry.discard("run-1")
    assert registry.get("run-1") is None


# --- persistence --------------------------------------------------------------------


def _store(store_factory, tmp_path):
    name = "jobs.db" if store_factory is SqliteJobStore else "jobs.json"
    return store_factory(tmp_path / name)


@pytest.mark.parametrize("store_factory", [SqliteJobStore, PersistentJobStore])
def test_transitions_are_recorded_as_first_class_rows(store_factory, tmp_path) -> None:
    store = _store(store_factory, tmp_path)
    job = store.create("demo", "baseline", True, created_by="alice")

    store.update(job.id, lambda item: item.apply_transition("running", actor="alice", reason="started"))
    store.update(job.id, lambda item: item.apply_transition("analysing", actor="system"))

    stored = _stored(store, job.id)
    assert stored.status == "analysing"
    assert [entry["to_state"] for entry in stored.transitions] == ["running", "analysing"]
    assert stored.transitions[0]["from_state"] == "queued"
    assert stored.transitions[0]["actor"] == "alice"
    assert stored.transitions[0]["reason"] == "started"


@pytest.mark.parametrize("store_factory", [SqliteJobStore, PersistentJobStore])
def test_an_illegal_transition_is_refused_by_the_stored_job(store_factory, tmp_path) -> None:
    store = _store(store_factory, tmp_path)
    job = store.create("demo", "baseline", True)
    store.update(job.id, lambda item: item.apply_transition("running"))
    store.update(job.id, lambda item: item.apply_transition("analysing"))
    store.update(job.id, lambda item: item.apply_transition("completed"))

    with pytest.raises(InvalidScanTransition):
        store.update(job.id, lambda item: item.apply_transition("running"))


@pytest.mark.parametrize("store_factory", [SqliteJobStore, PersistentJobStore])
def test_a_restart_leaves_no_job_stuck_in_running(store_factory, tmp_path) -> None:
    """In-flight scans died with the process and their rows stayed ``running``."""
    store = _store(store_factory, tmp_path)
    stranded = store.create("demo", "baseline", True)
    store.update(stranded.id, lambda item: item.apply_transition("running"))
    finished = store.create("demo", "baseline", True)
    store.update(finished.id, lambda item: item.apply_transition("running"))
    store.update(finished.id, lambda item: item.apply_transition("analysing"))
    store.update(finished.id, lambda item: item.apply_transition("completed"))

    recovered = store.reconcile_interrupted("interrupted by a server restart")

    assert recovered == [stranded.id]
    assert _stored(store, stranded.id).status == "failed"
    assert "restart" in (_stored(store, stranded.id).error or "")
    assert _stored(store, finished.id).status == "completed"


# --- the runner ---------------------------------------------------------------------


def _prepare(monkeypatch, tmp_path):
    store = SqliteJobStore(tmp_path / "jobs.db")
    monkeypatch.setattr(hosted_server, "JOB_STORE", store)
    monkeypatch.setattr(hosted_server, "OUTPUT_ROOT", tmp_path / "out")
    return store


def test_a_completed_run_walks_the_whole_state_machine(monkeypatch, tmp_path) -> None:
    store = _prepare(monkeypatch, tmp_path)
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    stored = _stored(store, job.id)
    assert stored.status == "completed", stored.error
    assert [entry["to_state"] for entry in stored.transitions] == ["running", "analysing", "completed"]


def test_a_run_cancelled_before_it_starts_ends_cancelled(monkeypatch, tmp_path) -> None:
    store = _prepare(monkeypatch, tmp_path)
    job = store.create("demo", "baseline", True)
    hosted_server.CANCELLATIONS.create(job.id).cancel("cancelled by operator", actor="alice")

    hosted_server.run_scan_job(job.id)

    stored = _stored(store, job.id)
    assert stored.status == "cancelled"
    assert "cancel" in (stored.error or "").lower()


def test_a_run_that_exceeds_its_budget_ends_timed_out_not_failed(monkeypatch, tmp_path) -> None:
    """A timed-out scan used to be recorded as ``failed`` with a message."""
    store = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(hosted_server, "SCAN_BUDGET_SECONDS", 0.0)
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    stored = _stored(store, job.id)
    assert stored.status == "timed_out"
    assert "budget" in (stored.error or "")


def test_the_stream_carries_the_precise_state_for_a_terminal_run(monkeypatch, tmp_path) -> None:
    store = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(hosted_server, "SCAN_BUDGET_SECONDS", 0.0)
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    terminal = _stored(store, job.id).events[-1]
    assert terminal.type == "scan_failed", "existing clients still receive the terminal event type"
    assert terminal.data["state"] == "timed_out", "the precise state travels in the event payload"


def test_a_cancelled_run_stops_between_modules() -> None:
    """Cancelling must stop traffic to the target, not merely mark the record."""
    from core.test_runner import TestRunner
    from core.types import ScanContext

    token = CancellationToken()
    token.cancel("stop now")
    runner = TestRunner()
    context = ScanContext(target_name="demo", profile_name="baseline", config={})

    with pytest.raises(ScanCancelled):
        runner.run_modules(["prompt_injection"], context, cancellation=token)


def test_cancellation_registry_is_cleared_after_a_run(monkeypatch, tmp_path) -> None:
    store = _prepare(monkeypatch, tmp_path)
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    assert hosted_server.CANCELLATIONS.get(job.id) is None


def test_concurrent_transitions_stay_consistent(tmp_path) -> None:
    """Only one of two racing transitions may win; the loser must raise."""
    store = SqliteJobStore(tmp_path / "jobs.db")
    job = store.create("demo", "baseline", True)
    store.update(job.id, lambda item: item.apply_transition("running"))
    store.update(job.id, lambda item: item.apply_transition("analysing"))
    outcomes: list[str] = []

    def finish(state: str) -> None:
        try:
            store.update(job.id, lambda item: item.apply_transition(state))
            outcomes.append(state)
        except InvalidScanTransition:
            outcomes.append(f"rejected:{state}")

    threads = [threading.Thread(target=finish, args=(state,)) for state in ("completed", "cancelled")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(1 for item in outcomes if not item.startswith("rejected")) == 1
    assert is_terminal(_stored(store, job.id).status)
