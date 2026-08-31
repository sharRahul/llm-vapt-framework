from __future__ import annotations

from pathlib import Path

import pytest

from core.runtime_targets import save as save_runtime_target
from webui.hosted_server import validate_scan_request


def test_validate_scan_request_requires_explicit_target() -> None:
    with pytest.raises(ValueError, match="target is required"):
        validate_scan_request({})
def test_validate_scan_request_accepts_explicit_test_fixture_target() -> None:
    target, profile, authorised = validate_scan_request({"target": "demo", "profile": "baseline", "authorised": True})

    assert target == "demo"
    assert profile == "baseline"
    assert authorised is True
def test_validate_scan_request_rejects_unknown_target() -> None:
    with pytest.raises(ValueError):
        validate_scan_request({"target": "missing", "profile": "baseline"})


def test_target_readiness_marks_placeholder_as_unavailable() -> None:
    from webui.hosted_server import target_readiness

    readiness = target_readiness({
        "demo": {"name": "Demo", "type": "test_fixture"},
        "placeholder": {"name": "Placeholder", "type": "http_json", "base_url": "https://example.invalid"},
    })

    assert readiness["demo"]["ready"] is True
    assert readiness["placeholder"]["ready"] is False
    assert "placeholder" in readiness["placeholder"]["reason"].lower()
def test_run_scan_job_generates_webui_outputs(tmp_path, monkeypatch) -> None:
    from webui.hosted_server import run_scan_job

    monkeypatch.setattr("webui.hosted_server.OUTPUT_ROOT", Path(tmp_path))
    from webui.persistent_jobs import PersistentJobStore

    store = PersistentJobStore(tmp_path / "jobs.json")
    monkeypatch.setattr("webui.hosted_server.JOB_STORE", store)
    job = store.create("demo", "baseline", True)

    run_scan_job(job.id)

    completed = store.get(job.id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.summary["finding_count"] >= 1
    assert set(completed.outputs) == {"markdown", "json", "sarif", "dashboard_markdown", "dashboard_html"}
    assert all(Path(path).exists() for path in completed.outputs.values())
def test_save_runtime_target_rejects_invalid_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VULNORAIQ_RUNTIME_TARGETS_PATH", str(tmp_path / "runtime_targets.yaml"))

    with pytest.raises(ValueError, match="target id"):
        save_runtime_target("../bad", {"name": "Bad", "type": "http_json", "base_url": "http://127.0.0.1:8080"})
def test_save_runtime_target_rejects_invalid_target_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VULNORAIQ_RUNTIME_TARGETS_PATH", str(tmp_path / "runtime_targets.yaml"))

    with pytest.raises(ValueError, match="model is required"):
        save_runtime_target(
            "local_agent",
            {
                "name": "Local Agent",
                "type": "chat_completions",
                "base_url": "http://127.0.0.1:8080",
            },
        )
