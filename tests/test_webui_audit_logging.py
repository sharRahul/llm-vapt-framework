from __future__ import annotations

import json
import logging

from webui.auth import AuthPrincipal
from webui.web_security import AUDIT_LOG, audit_event


def _setup_caplog(caplog) -> None:
    caplog.set_level(logging.INFO, logger="vulnoraiq.audit")
    AUDIT_LOG.propagate = True
def test_audit_includes_required_fields(caplog) -> None:
    _setup_caplog(caplog)
    p = AuthPrincipal("alice", "admin", {"view_scans"}, authenticated=True)
    audit_event("test_event", p, request_id="req123", client_ip="10.0.0.1",
                      method="GET", path="/api/scans", status=200, detail="test")
    records = [r for r in caplog.records if r.name == "vulnoraiq.audit"]
    assert len(records) >= 1
    log_msg = records[-1].message
    data = json.loads(log_msg)
    assert data["event"] == "test_event"
    assert data["request_id"] == "req123"
    assert data["user"] == "alice"
    assert data["role"] == "admin"
    assert data["authenticated"] == "true"
    assert data["client_ip"] == "10.0.0.1"
    assert data["method"] == "GET"
    assert data["path"] == "/api/scans"
    assert data["status"] == 200
    assert data["detail"] == "test"
def test_audit_does_not_leak_tokens(caplog) -> None:
    _setup_caplog(caplog)
    p = AuthPrincipal("admin_user", "admin", {"view_scans"}, authenticated=True)
    audit_event("auth_failure", p, request_id="req1", detail="token attempt with value=secret123")
    records = [r for r in caplog.records if r.name == "vulnoraiq.audit"]
    assert len(records) >= 1
    log_msg = records[-1].message
    data = json.loads(log_msg)
    assert "secret123" in data.get("detail", "")
    for field in ("user", "role", "method", "path"):
        assert "secret123" not in str(data.get(field, ""))
def test_audit_sanitizes_newlines(caplog) -> None:
    _setup_caplog(caplog)
    p = AuthPrincipal("test_user", "analyst", {"view_scans"}, authenticated=True)
    audit_event("test_event", p, detail="multi\nline\rdetail")
    records = [r for r in caplog.records if r.name == "vulnoraiq.audit"]
    assert len(records) >= 1
    data = json.loads(records[-1].message)
    assert "\\n" in data["detail"]
    assert "\\r" in data["detail"]
    assert "\n" not in data["detail"]
    assert "\r" not in data["detail"]
def test_audit_event_names(caplog) -> None:
    _setup_caplog(caplog)
    p = AuthPrincipal("admin", "admin", {"view_scans"}, authenticated=True)
    events = [
        "server_start", "auth_success", "auth_failure", "authz_failure",
        "csrf_failure", "rate_limit_exceeded", "oversized_request",
        "malformed_json", "scan_created", "scan_failed",
        "artifact_download", "production_config_validation_failed",
    ]
    for ev in events:
        audit_event(ev, p, request_id="req1", detail=ev)
    records = [r for r in caplog.records if r.name == "vulnoraiq.audit"]
    logged_events = set()
    for r in records:
        data = json.loads(r.message)
        logged_events.add(data["event"])
    for ev in events:
        assert ev in logged_events, f"Event {ev} not found in audit logs"
