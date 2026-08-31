from __future__ import annotations

import importlib
import time

import pytest

from webui.auth import AuthPrincipal, WebAuthManager
from webui.persistent_jobs import PersistentJobStore, SqliteJobStore
from webui.web_security import CsrfTokenStore, RateLimiter, csrf_tokens, session_key

# --- Auth ---------------------------------------------------------------------


def test_auth_manager_returns_none_when_auth_enabled_and_no_token() -> None:
    manager = WebAuthManager()
    assert manager.authenticate_token(None) is None


def test_auth_manager_local_admin_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_AUTH_ENABLED", "false")
    manager = WebAuthManager()
    principal = manager.authenticate_token(None)

    assert principal is not None
    assert principal.username == "local-admin"
    assert principal.role == "admin"
    assert manager.can(principal, "view_scans")
    assert manager.can(principal, "start_configured_scan")
    assert manager.can(principal, "manage_runtime")


def test_env_token_auth_works(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "super-secret-admin-token-12345")
    principal = WebAuthManager().authenticate_token("super-secret-admin-token-12345")

    assert principal is not None
    assert principal.authenticated
    assert principal.role == "admin"


def test_env_token_auth_rejects_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "super-secret-admin-token-12345")
    assert WebAuthManager().authenticate_token("wrong-token") is None


def test_no_builtin_token_is_accepted_outside_production() -> None:
    """There must be no shipped token that authenticates without configuration."""
    manager = WebAuthManager()
    for candidate in ("vulnoraiq-internal-admin-token", "admin", "changeme", "internal"):
        assert manager.authenticate_token(candidate) is None


def test_auth_fail_closed_by_default() -> None:
    assert WebAuthManager().enabled()


def test_production_mode_rejects_no_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    with pytest.raises(RuntimeError, match="VULNORAIQ_ADMIN_TOKEN"):
        WebAuthManager().validate_production()


def test_production_mode_rejects_short_admin_token(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 20 characters"):
        WebAuthManager().validate_production()


def test_production_mode_rejects_disabled_auth(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_AUTH_ENABLED", "false")
    with pytest.raises(RuntimeError, match="local_admin"):
        WebAuthManager().validate_production()


def test_production_mode_accepts_valid_config(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    WebAuthManager().validate_production()


def test_production_mode_authenticates_from_env_not_file(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ENV", "production")
    monkeypatch.setenv("VULNORAIQ_ADMIN_TOKEN", "this-is-a-long-enough-admin-token-12345")
    manager = WebAuthManager()

    assert manager.authenticate_token("this-is-a-long-enough-admin-token-12345") is not None


def test_role_permissions_include_expected_admin_permissions() -> None:
    permissions = WebAuthManager().permissions_for_role("admin")

    assert {"view_scans", "download_artifacts", "start_configured_scan"} <= permissions


# --- CSRF ---------------------------------------------------------------------


def _principal(name: str) -> AuthPrincipal:
    return AuthPrincipal(name, "admin", {"view_scans"}, authenticated=True)


def test_csrf_token_is_unique_per_session() -> None:
    key1 = session_key(_principal("alice"), "10.0.0.1")
    key2 = session_key(_principal("bob"), "10.0.0.2")
    token1 = csrf_tokens.token_for(key1)
    token2 = csrf_tokens.token_for(key2)

    assert token1 != token2
    assert csrf_tokens.validate(key1, token1)
    assert not csrf_tokens.validate(key1, token2)


def test_csrf_rejects_missing_token() -> None:
    key = session_key(_principal("admin"), "10.0.0.1")
    csrf_tokens.token_for(key)

    assert not csrf_tokens.validate(key, None)
    assert not csrf_tokens.validate(key, "")


def test_csrf_rejects_invalid_token() -> None:
    key = session_key(_principal("admin"), "10.0.0.1")
    csrf_tokens.token_for(key)

    assert not csrf_tokens.validate(key, "invalid-token")


def test_csrf_token_expires() -> None:
    store = CsrfTokenStore(ttl_seconds=0)
    token = store.token_for("session")
    time.sleep(0.01)

    assert not store.validate("session", token)


def test_csrf_purge_drops_expired_entries() -> None:
    store = CsrfTokenStore(ttl_seconds=0)
    store.token_for("session")
    time.sleep(0.01)
    store.purge_expired()

    assert not store.validate("session", "anything")


# --- Rate limiting ------------------------------------------------------------


def test_rate_limit_allows_within_limit() -> None:
    limiter = RateLimiter(window_seconds=60, maximum=10)

    for _ in range(10):
        assert limiter.allow("client")


def test_rate_limit_blocks_after_limit() -> None:
    limiter = RateLimiter(window_seconds=60, maximum=3)

    for _ in range(3):
        assert limiter.allow("client")
    assert not limiter.allow("client")


def test_rate_limit_is_per_key() -> None:
    limiter = RateLimiter(window_seconds=60, maximum=1)

    assert limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("a")


def test_rate_limit_window_expiry_releases_the_key() -> None:
    limiter = RateLimiter(window_seconds=0, maximum=1)
    limiter.allow("client")
    limiter.purge_expired()

    assert limiter.allow("client")


# --- Proxy IP resolution ------------------------------------------------------


def _reload_web_security():
    import webui.web_security as web_security

    return importlib.reload(web_security)


class _FakeHandler:
    def __init__(self, address: str, forwarded: str | None = None) -> None:
        self.client_address = (address, 54321)
        self.headers = {"X-Forwarded-For": forwarded} if forwarded else {}


def test_proxy_ip_resolution_direct(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_TRUST_PROXY_HEADERS", "false")
    web_security = _reload_web_security()

    assert web_security.resolve_client_ip(_FakeHandler("10.0.0.5")) == "10.0.0.5"


def test_proxy_ip_trusts_forwarded_from_trusted_proxy(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    web_security = _reload_web_security()

    assert web_security.resolve_client_ip(_FakeHandler("10.0.0.1", "203.0.113.5")) == "203.0.113.5"


def test_proxy_ip_ignores_spoofed_forwarded_from_untrusted(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    web_security = _reload_web_security()

    assert web_security.resolve_client_ip(_FakeHandler("203.0.113.99", "1.2.3.4")) == "203.0.113.99"


def test_proxy_ip_rejects_malformed_forwarded(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    web_security = _reload_web_security()

    assert web_security.resolve_client_ip(_FakeHandler("10.0.0.1", "not-an-ip")) == "10.0.0.1"


@pytest.fixture(autouse=True)
def _restore_web_security_module():
    yield
    _reload_web_security()


# --- Job stores ---------------------------------------------------------------


def test_persistent_job_store_round_trip(tmp_path) -> None:
    store = PersistentJobStore(tmp_path / "jobs.json")
    job = store.create("demo", "baseline", True)

    assert store.get(job.id) is not None


def test_sqlite_job_store_round_trip(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.db")
    job = store.create("demo", "baseline", True)

    assert store.get(job.id) is not None
