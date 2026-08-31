from __future__ import annotations

import pytest

from integrations.target_adapters import validate_url
from webui.auth import AuthPrincipal
from webui.hosted_server import _can_download_job_artifact, _can_view_job
from webui.persistent_jobs import PersistedScanJob


def test_non_admin_cannot_view_another_users_scan() -> None:
    principal = AuthPrincipal("alice", "analyst", {"view_scans", "download_artifacts"}, authenticated=True)
    job = PersistedScanJob("job-1", "demo", "baseline", False, created_by="bob")
    assert not _can_view_job(principal, job)


def test_non_admin_can_view_own_scan() -> None:
    principal = AuthPrincipal("alice", "analyst", {"view_scans", "download_artifacts"}, authenticated=True)
    job = PersistedScanJob("job-1", "demo", "baseline", False, created_by="alice")
    assert _can_view_job(principal, job)


def test_admin_can_view_all_scans() -> None:
    principal = AuthPrincipal("admin", "admin", {"view_all_scans", "download_all_artifacts"}, authenticated=True)
    job = PersistedScanJob("job-1", "demo", "baseline", False, created_by="bob")
    assert _can_view_job(principal, job)


def test_non_admin_cannot_download_another_users_artifact() -> None:
    principal = AuthPrincipal("alice", "analyst", {"view_scans", "download_artifacts"}, authenticated=True)
    job = PersistedScanJob("job-1", "demo", "baseline", False, created_by="bob")
    assert not _can_download_job_artifact(principal, job)


def _target(endpoint: str) -> dict:
    from urllib.parse import urlparse

    parsed = urlparse(endpoint)
    return {
        "base_url": f"{parsed.scheme}://{parsed.netloc}",
        "endpoint_path": parsed.path or "/",
        "safety_profile": "local_lab_safe",
        "allow_external": True,
    }


def test_target_endpoint_requires_http_scheme() -> None:
    with pytest.raises(ValueError, match="only http"):
        validate_url({"base_url": "file:///etc", "endpoint_path": "/passwd"})


def test_target_endpoint_rejects_url_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        validate_url(_target("https://user:secret@example.com/api"))


def test_target_endpoint_allows_configured_host(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ALLOWED_TARGET_HOSTS", "api.internal.example.com,*.lab.example.com")
    assert validate_url(_target("https://api.internal.example.com/agent")).endswith("/agent")
    assert validate_url(_target("https://red.lab.example.com/agent")).endswith("/agent")


def test_target_endpoint_blocks_unlisted_host(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ALLOWED_TARGET_HOSTS", "api.internal.example.com")
    with pytest.raises(ValueError, match="not in"):
        validate_url(_target("https://other.example.com/agent"))


def test_external_targets_are_blocked_without_opt_in() -> None:
    with pytest.raises(ValueError, match="external targets are blocked"):
        validate_url({"base_url": "https://example.com", "endpoint_path": "/", "safety_profile": "local_lab_safe"})


def test_loopback_targets_are_allowed_by_default() -> None:
    assert validate_url({"base_url": "http://127.0.0.1:8080", "endpoint_path": "/ask", "safety_profile": "local_lab_safe"})
