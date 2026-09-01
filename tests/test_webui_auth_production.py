from __future__ import annotations

import pytest

from webui.auth import WebAuthManager


def test_production_mode_rejects_disabled_auth(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    monkeypatch.setenv("VULNORAIQ_AUTH_ENABLED", "false")
    manager = WebAuthManager()
    with pytest.raises(RuntimeError, match="local_admin"):
        manager.validate_production()
def test_production_mode_accepts_valid_config(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    manager = WebAuthManager()
    manager.validate_production()
def test_production_mode_rejects_short_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "short")
    manager = WebAuthManager()
    with pytest.raises(RuntimeError, match="at least 20 characters"):
        manager.validate_production()
def test_production_mode_rejects_no_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    manager = WebAuthManager()
    with pytest.raises(RuntimeError, match="VULNORAIQ_ADMIN_TOKEN"):
        manager.validate_production()
def test_production_mode_disables_internal_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    manager = WebAuthManager()
    principal = manager.authenticate_token("vulnoraiq-internal-admin-token")
    assert principal is None
def test_production_mode_rejects_file_fallback(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    manager = WebAuthManager()
    principal = manager.authenticate_token("this-is-a-long-enough-admin-token-12345")
    assert principal is not None
    assert principal.authenticated
    assert principal.role == "admin"
def test_proxy_identity_from_trusted_source(monkeypatch) -> None:
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "alice", "X-VulnoraIQ-Role": "admin"},
        trusted=True,
    )
    assert principal is not None
    assert principal.authenticated
    assert principal.username == "proxy:alice"
    assert principal.role == "admin"
def test_proxy_identity_rejected_from_untrusted_source(monkeypatch) -> None:
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "alice", "X-VulnoraIQ-Role": "admin"},
        trusted=False,
    )
    assert principal is None
def test_proxy_identity_defaults_to_viewer(monkeypatch) -> None:
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "bob"},
        trusted=True,
    )
    assert principal is not None
    assert principal.role == "viewer"
def test_proxy_identity_maps_roles(monkeypatch) -> None:
    manager = WebAuthManager()
    for header_role, expected in [("admin", "admin"), ("analyst", "analyst"), ("viewer", "viewer"), ("unknown", "viewer")]:
        principal = manager.authenticate_proxy_identity(
            {"X-Authenticated-User": "user", "X-VulnoraIQ-Role": header_role},
            trusted=True,
        )
        assert principal is not None
        assert principal.role == expected, f"Expected {expected} for role {header_role}, got {principal.role}"
def test_proxy_identity_permissions(monkeypatch) -> None:
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "admin-user", "X-VulnoraIQ-Role": "admin"},
        trusted=True,
    )
    assert principal is not None
    assert manager.can(principal, "start_configured_scan")
    assert manager.can(principal, "manage_runtime")

    viewer = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "viewer-user", "X-VulnoraIQ-Role": "viewer"},
        trusted=True,
    )
    assert viewer is not None
    assert not manager.can(viewer, "start_configured_scan")
    assert manager.can(viewer, "view_scans")
def test_proxy_identity_requires_username(monkeypatch) -> None:
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-VulnoraIQ-Role": "admin"},
        trusted=True,
    )
    assert principal is None
def test_token_and_proxy_auth_modes(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "real-admin-token-here-12345")
    manager = WebAuthManager()
    assert manager.auth_mode() == "token"
    principal = manager.authenticate_token("real-admin-token-here-12345")
    assert principal is not None
    assert principal.authenticated
def test_auth_fail_closed_by_default() -> None:
    manager = WebAuthManager()
    assert manager.enabled()
def test_constant_time_comparison(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "real-token-value-here")
    monkeypatch.setenv("VULNORAIQ_ANALYST_TOKEN", "analyst-token-here")
    manager = WebAuthManager()
    p1 = manager.authenticate_token("real-token-value-here")
    assert p1 is not None
    assert p1.role == "admin"
    p2 = manager.authenticate_token("wrong-token")
    assert p2 is None
    p3 = manager.authenticate_token("analyst-token-here")
    assert p3 is not None
    assert p3.role == "analyst"
# -- Trusted proxy identity regression tests --
def test_proxy_env_trust_headers_parsing() -> None:
    """TRUST_PROXY_HEADERS env var parsing rejects false values."""
    for false_val in ("false", "0", "no", ""):
        assert false_val.strip().lower() not in ("1", "true", "yes")
    for true_val in ("true", "1", "yes"):
        assert true_val.strip().lower() in ("1", "true", "yes")
def test_spoofed_headers_rejected_from_untrusted_ip(monkeypatch) -> None:
    """Spoofed X-Authenticated-User headers are ignored when not from trusted proxy."""
    monkeypatch.setenv("VULNORAIQ_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    manager = WebAuthManager()
    # Simulate untrusted source (direct IP not in CIDR)
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "attacker", "X-VulnoraIQ-Role": "admin"},
        trusted=False,
    )
    assert principal is None
def test_spoofed_headers_without_proxy_mode(monkeypatch) -> None:
    """When AUTH_MODE is not trusted_proxy, proxy headers are ignored."""
    monkeypatch.setenv("VULNORAIQ_AUTH_MODE", "token")
    manager = WebAuthManager()
    assert manager.auth_mode() == "token"
def test_proxy_identity_respects_cidr_check(monkeypatch) -> None:
    """authenticate_proxy_identity only trusts when trusted=True (CIDR check passes)."""
    manager = WebAuthManager()
    # From trusted source
    trusted = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "alice", "X-VulnoraIQ-Role": "admin"},
        trusted=True,
    )
    assert trusted is not None
    assert trusted.authenticated
    # From untrusted source (same headers, trusted=False)
    untrusted = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "alice", "X-VulnoraIQ-Role": "admin"},
        trusted=False,
    )
    assert untrusted is None
def test_proxy_identity_role_mapping_unknown_to_viewer(monkeypatch) -> None:
    """Unknown roles in proxy headers default to viewer."""
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "bob", "X-VulnoraIQ-Role": "superadmin"},
        trusted=True,
    )
    assert principal is not None
    assert principal.role == "viewer"
    # Verify viewer permissions
    assert "view_scans" in principal.permissions
    assert "start_configured_scan" not in principal.permissions
def test_proxy_identity_viewer_permissions(monkeypatch) -> None:
    """Viewer role has view_scans and download_artifacts only."""
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "viewer-user", "X-VulnoraIQ-Role": "viewer"},
        trusted=True,
    )
    assert principal is not None
    assert manager.can(principal, "view_scans")
    assert manager.can(principal, "download_artifacts")
    assert not manager.can(principal, "start_configured_scan")
    assert not manager.can(principal, "manage_runtime")
def test_proxy_identity_analyst_permissions(monkeypatch) -> None:
    """Analyst is viewer plus starting an already-configured scan."""
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "analyst-user", "X-VulnoraIQ-Role": "analyst"},
        trusted=True,
    )
    assert principal is not None
    assert manager.can(principal, "view_scans")
    assert manager.can(principal, "download_artifacts")
    assert manager.can(principal, "start_configured_scan")
    # Running a configured scan must not imply changing the configuration.
    assert not manager.can(principal, "manage_runtime")
    assert not manager.can(principal, "view_all_scans")
def test_proxy_identity_admin_permissions(monkeypatch) -> None:
    """Admin role has all permissions."""
    manager = WebAuthManager()
    principal = manager.authenticate_proxy_identity(
        {"X-Authenticated-User": "admin-user", "X-VulnoraIQ-Role": "admin"},
        trusted=True,
    )
    assert principal is not None
    assert manager.can(principal, "view_scans")
    assert manager.can(principal, "download_artifacts")
    assert manager.can(principal, "start_configured_scan")
    assert manager.can(principal, "manage_runtime")
def test_proxy_identity_multiple_spoofed_headers(monkeypatch) -> None:
    """Multiple spoofed identity headers are all rejected from untrusted source."""
    manager = WebAuthManager()
    spoofed_headers = {
        "X-Authenticated-User": "admin",
        "X-Authenticated-Email": "admin@evil.com",
        "X-Authenticated-Groups": "group1,group2",
        "X-VulnoraIQ-Role": "admin",
    }
    principal = manager.authenticate_proxy_identity(spoofed_headers, trusted=False)
    assert principal is None
