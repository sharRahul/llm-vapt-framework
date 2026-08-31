"""Regressions for defects found during the platform refactor.

Each test here corresponds to a specific bug that shipped: the comment on each
one states what used to happen, so a future change that reintroduces the fault
fails with an explanation rather than a bare assertion.
"""

from __future__ import annotations

import threading

import pytest

from webui import hosted_server
from webui.agent_host import AgentHost
from webui.docker_cli import loopback_publish
from webui.persistent_jobs import PersistedScanJob, PersistentJobStore, SqliteJobStore

# --- HTTP verb routing ----------------------------------------------------------


def test_handler_implements_every_verb_it_routes() -> None:
    """PATCH used to fall through to the stdlib handler and answer 501.

    `_do_PATCH_routes` existed and the console called PATCH for finding triage,
    but no `do_PATCH` method was defined, so every triage update silently failed.
    """
    handler = hosted_server.HostedWebUiHandler
    for verb in ("GET", "POST", "PATCH"):
        assert hasattr(handler, f"do_{verb}"), f"do_{verb} is missing but {verb} routes exist"
        assert hasattr(handler, f"_do_{verb}_routes")


def test_composed_server_inherits_the_patch_verb() -> None:
    from webui.server import VulnoraIQWebHandler

    assert hasattr(VulnoraIQWebHandler, "do_PATCH")


# --- Scan admission and concurrency ---------------------------------------------


def test_queued_scan_waits_for_a_slot_instead_of_being_dropped(monkeypatch) -> None:
    """A queued scan used to vanish when the runner was busy.

    `run_scan_job` returned immediately if no concurrency slot was free, leaving
    the job marked `queued` forever with no worker and no error.
    """
    monkeypatch.setattr(hosted_server, "MAX_CONCURRENT_SCANS", 1)
    hosted_server._active_scans.clear()
    hosted_server._queued_scans.clear()

    assert hosted_server._acquire_scan_slot("first") is True

    released = threading.Event()

    def waiter() -> None:
        assert hosted_server._acquire_scan_slot("second", timeout=5) is True
        released.set()

    thread = threading.Thread(target=waiter, daemon=True)
    thread.start()
    assert not released.wait(0.2), "the second scan should still be waiting"

    hosted_server._release_scan_slot("first")
    assert released.wait(5), "releasing a slot must wake a waiting scan"
    hosted_server._release_scan_slot("second")


def test_scan_that_never_gets_a_slot_is_failed_not_abandoned(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hosted_server, "MAX_CONCURRENT_SCANS", 0)
    monkeypatch.setattr(hosted_server, "SCAN_SLOT_WAIT_SECONDS", 0.1)
    store = SqliteJobStore(tmp_path / "jobs.db")
    monkeypatch.setattr(hosted_server, "JOB_STORE", store)
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    updated = store.get(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "capacity" in (updated.error or "")


def test_queue_limit_counts_waiting_scans(monkeypatch) -> None:
    """Admission control used to compare the limit against running scans only."""
    hosted_server._active_scans.clear()
    hosted_server._queued_scans.clear()
    hosted_server._queued_scans.update({"a", "b"})
    hosted_server._active_scans.add("c")

    try:
        admitted = len(hosted_server._active_scans) + len(hosted_server._queued_scans)
        assert admitted == 3, "waiting scans count against the queue limit"
    finally:
        hosted_server._active_scans.clear()
        hosted_server._queued_scans.clear()


# --- Event stream integrity -----------------------------------------------------


def _advance(store, job_id: str, message: str) -> None:
    store.update(job_id, lambda job: job.add_event("phase_started", message, 10))


def test_event_ids_are_stable_across_job_updates(tmp_path) -> None:
    """Every job update used to delete and re-insert the whole event list.

    The AUTOINCREMENT ids were renumbered underneath an in-flight SSE stream, so
    a client resuming from Last-Event-ID replayed or skipped events.
    """
    store = SqliteJobStore(tmp_path / "jobs.db")
    job = store.create("demo", "baseline", True)

    _advance(store, job.id, "first")
    first_ids = [event.event_id for event in store.list_events_after(job.id, 0)]

    _advance(store, job.id, "second")
    second_ids = [event.event_id for event in store.list_events_after(job.id, 0)]

    assert second_ids[: len(first_ids)] == first_ids, "existing event ids must never change"
    assert len(second_ids) == len(first_ids) + 1
    assert second_ids == sorted(second_ids)


def test_events_after_a_cursor_return_only_newer_events(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.db")
    job = store.create("demo", "baseline", True)
    _advance(store, job.id, "first")
    seen = [event.event_id for event in store.list_events_after(job.id, 0)]

    _advance(store, job.id, "second")
    new_events = store.list_events_after(job.id, max(seen))

    assert [event.message for event in new_events] == ["second"]


def test_json_store_emits_events_to_the_stream(tmp_path) -> None:
    """The JSON backend left every event_id at 0, so `list_events_after(0)`
    returned nothing and the progress stream stayed empty."""
    store = PersistentJobStore(tmp_path / "jobs.json")
    job = store.create("demo", "baseline", True)

    events = store.list_events_after(job.id, 0)

    assert events, "the JSON backend must emit its queued event"
    assert all(event.event_id > 0 for event in events)


# --- Job store parity -----------------------------------------------------------


def _job_with_finding(store) -> str:
    job = store.create("demo", "baseline", True)

    def attach(item: PersistedScanJob) -> None:
        item.summary = {"findings": [{"id": "LLM01", "title": "example"}]}

    store.update(job.id, attach)
    return job.id


@pytest.mark.parametrize("backend", ["sqlite", "json"])
def test_both_job_stores_support_finding_triage(tmp_path, backend: str) -> None:
    """The JSON backend advertised the triage API but always answered
    "finding not found", so the console's PATCH returned 404 against it."""
    store = SqliteJobStore(tmp_path / "jobs.db") if backend == "sqlite" else PersistentJobStore(tmp_path / "jobs.json")
    job_id = _job_with_finding(store)

    updated = store.update_finding(job_id, "LLM01", {"status": "accepted_risk", "accepted_risk_reason": "known"}, "alice")

    assert updated is not None
    assert updated["status"] == "accepted_risk"
    assert updated["updated_by"] == "alice"
    history = store.finding_history(job_id, "LLM01")
    assert len(history) == 1
    assert history[0]["actor"] == "alice"


@pytest.mark.parametrize("backend", ["sqlite", "json"])
def test_triage_ignores_fields_outside_the_remediation_set(tmp_path, backend: str) -> None:
    store = SqliteJobStore(tmp_path / "jobs.db") if backend == "sqlite" else PersistentJobStore(tmp_path / "jobs.json")
    job_id = _job_with_finding(store)

    updated = store.update_finding(job_id, "LLM01", {"status": "triaged", "severity_override": "critical"}, "alice")

    assert updated is not None
    assert "severity_override" not in updated


@pytest.mark.parametrize("backend", ["sqlite", "json"])
def test_triage_of_an_unknown_finding_reports_not_found(tmp_path, backend: str) -> None:
    store = SqliteJobStore(tmp_path / "jobs.db") if backend == "sqlite" else PersistentJobStore(tmp_path / "jobs.json")
    job_id = _job_with_finding(store)

    assert store.update_finding(job_id, "does-not-exist", {"status": "triaged"}, "alice") is None


# --- Agent container hardening --------------------------------------------------


def test_port_mappings_are_pinned_to_loopback() -> None:
    """`-p 5000:5000` binds 0.0.0.0, exposing a deliberately weak assessment
    target to the whole network."""
    assert loopback_publish("5000:5000") == "127.0.0.1:5000:5000"
    assert loopback_publish("8080") == "127.0.0.1:8080"


def test_an_explicit_bind_address_is_left_alone() -> None:
    assert loopback_publish("0.0.0.0:5000:5000") == "0.0.0.0:5000:5000"
    assert loopback_publish("192.168.1.5:80:80") == "192.168.1.5:80:80"


def test_agent_containers_run_with_capabilities_dropped(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run_docker(args, timeout=None):
        commands.append(args)
        if args[:2] == ["ps", "-a"]:
            return "", ""
        return "container-id", ""

    monkeypatch.setattr("webui.agent_host.run_docker", fake_run_docker)
    AgentHost().deploy("probe", image="example/agent:latest", port=8080)

    run_cmd = next(cmd for cmd in commands if cmd[0] == "run")
    assert "--cap-drop" in run_cmd and "ALL" in run_cmd
    assert "no-new-privileges:true" in run_cmd
    assert "127.0.0.1:8080:8080" in run_cmd


# --- Target scope enforcement ----------------------------------------------------


def test_a_private_address_target_is_in_scope() -> None:
    from integrations.target_adapters import validate_url

    assert validate_url({"base_url": "http://10.1.2.3:8000", "endpoint_path": "/chat"})


def test_a_hostname_that_merely_looks_internal_is_out_of_scope() -> None:
    """The old check allowed any host ending in `.internal` or `.local` without
    resolving it, so an attacker-controlled public name passed the scope gate."""
    from integrations.target_adapters import validate_url

    with pytest.raises(ValueError, match="external targets are blocked"):
        validate_url({"base_url": "http://totally-not-real.example.internal", "endpoint_path": "/"})


def test_an_explicit_allowlist_admits_a_host_that_cannot_be_resolved(monkeypatch) -> None:
    """Declaring an allowlist is the operator's scope statement, and must work
    for a container name that only resolves once the container is running."""
    from integrations.target_adapters import validate_url

    url = validate_url(
        {
            "base_url": "http://vulnoraiq-agent-lab-example:8000",
            "endpoint_path": "/chat",
            "allowed_host_pattern": "vulnoraiq-agent-lab-example",
        }
    )
    assert url == "http://vulnoraiq-agent-lab-example:8000/chat"


# --- Event stream termination ----------------------------------------------------


def test_event_stream_closes_the_connection() -> None:
    """The stream declared `Connection: keep-alive` and sent no Content-Length,
    so a client hung waiting for more data after the terminal `done` event."""
    import inspect

    source = inspect.getsource(hosted_server.HostedWebUiHandler._send_events)

    assert 'self.send_header("Connection", "close")' in source
    assert "self.close_connection = True" in source
    assert '"Connection", "keep-alive"' not in source


# --- actionable scan failures ----------------------------------------------------


def _run_job(monkeypatch, tmp_path, target: str, authorised: bool = True):
    store = SqliteJobStore(tmp_path / "jobs.db")
    monkeypatch.setattr(hosted_server, "JOB_STORE", store)
    monkeypatch.setattr(hosted_server, "OUTPUT_ROOT", tmp_path / "out")
    job = store.create(target, "baseline", authorised)
    hosted_server.run_scan_job(job.id)
    return store.get(job.id)


def test_a_placeholder_target_reports_why_it_was_rejected(monkeypatch, tmp_path) -> None:
    """A configuration problem used to surface as "internal scan error".

    The scanner raises a precise, actionable message; the blanket exception
    handler replaced it, so an operator could not tell a misconfigured target
    from a server fault.
    """
    job = _run_job(monkeypatch, tmp_path, "custom_http_agent")

    assert job is not None
    assert job.status == "failed"
    assert "placeholder" in (job.error or "")
    assert job.error != "internal scan error"


def test_an_unauthorised_scan_reports_the_authorisation_gate(monkeypatch, tmp_path) -> None:
    job = _run_job(monkeypatch, tmp_path, "demo", authorised=False)

    assert job is not None
    assert job.status == "failed"
    assert "authorisation" in (job.error or "").lower()


def test_target_validated_is_not_claimed_when_validation_fails(monkeypatch, tmp_path) -> None:
    """The progress stream announced "target validated" and then failed on that
    very validation."""
    job = _run_job(monkeypatch, tmp_path, "custom_http_agent")

    assert job is not None
    types = [event.type for event in job.events]
    assert "target_validated" not in types
    assert types[-1] == "scan_failed"


def test_target_validated_is_emitted_for_a_valid_target(monkeypatch, tmp_path) -> None:
    job = _run_job(monkeypatch, tmp_path, "demo")

    assert job is not None
    assert job.status == "completed", job.error
    types = [event.type for event in job.events]
    assert types.index("target_validated") < types.index("phase_started")


def test_scanner_preflight_matches_what_a_scan_would_reject() -> None:
    from core.scanner import Scanner

    scanner = Scanner()
    scanner.validate_scan("demo", "baseline", authorised=True)

    with pytest.raises(ValueError, match="placeholder"):
        scanner.validate_scan("custom_http_agent", "baseline", authorised=True)
    with pytest.raises(PermissionError):
        scanner.validate_scan("demo", "baseline", authorised=False)
    with pytest.raises(ValueError, match="Unknown assessment profile"):
        scanner.validate_scan("demo", "no-such-profile", authorised=True)


# --- upstream tool failures ------------------------------------------------------


def test_docker_failures_are_reported_as_upstream_not_internal() -> None:
    """A stopped Docker engine used to surface as 500 "internal server error"."""
    import inspect

    from webui.docker_cli import DockerCommandError

    source = inspect.getsource(hosted_server.HostedWebUiHandler._handle_request)

    assert "DockerCommandError" in source
    assert "BAD_GATEWAY" in source
    assert issubclass(DockerCommandError, RuntimeError)
