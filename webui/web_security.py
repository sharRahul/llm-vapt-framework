"""Request-level security controls shared by every VulnoraIQ HTTP handler.

Rate limiting, CSRF tokens, proxy trust, audit logging, counters, and response
security headers live here rather than inside one handler module, so composed
servers enforce the same rules instead of reaching into another module's
private helpers.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any, Protocol

AUDIT_LOG = logging.getLogger("vulnoraiq.audit")

RATE_LIMIT_WINDOW = int(os.getenv("VULNORAIQ_RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX = int(os.getenv("VULNORAIQ_RATE_LIMIT_MAX", "60"))
CSRF_TOKEN_TTL = int(os.getenv("VULNORAIQ_CSRF_TOKEN_TTL", "300"))
TRUST_PROXY_HEADERS = os.getenv("VULNORAIQ_TRUST_PROXY_HEADERS", "false").strip().lower() in ("1", "true", "yes")

TRUSTED_PROXY_NETS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
if TRUST_PROXY_HEADERS:
    for _entry in os.getenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "").split(","):
        _entry = _entry.strip()
        if _entry:
            TRUSTED_PROXY_NETS.append(ipaddress.ip_network(_entry, strict=False))

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; form-action 'self'; "
    "base-uri 'self'; frame-ancestors 'none'"
)


class Principal(Protocol):
    """The subset of an authenticated principal this module records."""

    username: str
    role: str
    authenticated: bool


class MetricsRegistry:
    """Process-local counters exposed on ``/metrics``."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def increment(self, name: str) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


class RateLimiter:
    """Sliding-window per-key request limiter."""

    def __init__(self, window_seconds: int, maximum: int) -> None:
        self.window_seconds = window_seconds
        self.maximum = maximum
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            recent = [t for t in self._hits.get(key, []) if now - t < self.window_seconds]
            if len(recent) >= self.maximum:
                self._hits[key] = recent
                return False
            recent.append(now)
            self._hits[key] = recent
        return True

    def purge_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            for key in list(self._hits):
                self._hits[key] = [t for t in self._hits[key] if now - t < self.window_seconds]
                if not self._hits[key]:
                    del self._hits[key]


class CsrfTokenStore:
    """Per-session CSRF tokens with a bounded lifetime."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._tokens: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def token_for(self, key: str) -> str:
        now = time.monotonic()
        with self._lock:
            entry = self._tokens.get(key)
            if entry and entry["expires"] > now:
                return str(entry["token"])
            token = secrets.token_urlsafe(32)
            self._tokens[key] = {"token": token, "expires": now + self.ttl_seconds}
            return token

    def validate(self, key: str, provided_token: str | None) -> bool:
        if not provided_token:
            return False
        now = time.monotonic()
        with self._lock:
            entry = self._tokens.get(key)
            if not entry:
                return False
            if entry["expires"] <= now:
                del self._tokens[key]
                return False
            return secrets.compare_digest(str(entry["token"]), provided_token)

    def purge_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            for key in [k for k, v in self._tokens.items() if v["expires"] <= now]:
                del self._tokens[key]


metrics = MetricsRegistry()
rate_limiter = RateLimiter(RATE_LIMIT_WINDOW, RATE_LIMIT_MAX)
csrf_tokens = CsrfTokenStore(CSRF_TOKEN_TTL)


def session_key(principal: Principal, client_ip: str) -> str:
    """Scope CSRF tokens to the authenticated user, or to the IP when anonymous."""
    return f"user:{principal.username}" if principal.authenticated else f"ip:{client_ip}"


def is_trusted_proxy(handler: BaseHTTPRequestHandler) -> bool:
    """True when the immediate peer sits inside a configured trusted-proxy CIDR."""
    if not TRUST_PROXY_HEADERS:
        return False
    try:
        address = ipaddress.ip_address(handler.client_address[0])
    except ValueError:
        return False
    return any(address in net for net in TRUSTED_PROXY_NETS)


def resolve_client_ip(handler: BaseHTTPRequestHandler) -> str:
    """Return the caller's IP, honouring X-Forwarded-For only from trusted proxies."""
    direct_ip = handler.client_address[0]
    if not is_trusted_proxy(handler):
        return direct_ip
    forwarded = handler.headers.get("X-Forwarded-For", "").strip()
    if not forwarded:
        return direct_ip
    candidate = forwarded.split(",")[0].strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return direct_ip
    return candidate


def generate_request_id() -> str:
    return uuid.uuid4().hex[:16]


def safe_log_field(value: str | None, max_len: int = 200) -> str:
    """Truncate and de-newline a value so it cannot forge extra audit records."""
    if value is None:
        return ""
    return value[:max_len].replace("\n", "\\n").replace("\r", "\\r")


def audit_event(
    event: str,
    principal: Principal,
    request_id: str = "",
    client_ip: str = "",
    method: str = "",
    path: str = "",
    status: int = 0,
    detail: str = "",
) -> None:
    """Emit one structured audit record. Never called with secret material."""
    AUDIT_LOG.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": safe_log_field(event),
                "request_id": safe_log_field(request_id),
                "user": safe_log_field(principal.username),
                "role": safe_log_field(principal.role),
                "authenticated": str(principal.authenticated).lower(),
                "client_ip": safe_log_field(client_ip),
                "method": safe_log_field(method),
                "path": safe_log_field(path),
                "status": status,
                "detail": safe_log_field(detail),
            },
            default=str,
        )
    )


def security_headers(*, include_hsts: bool) -> list[tuple[str, str]]:
    """Response headers applied to every reply, error replies included."""
    headers = [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("X-XSS-Protection", "0"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
        ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
    ]
    if include_hsts:
        headers.append(("Strict-Transport-Security", "max-age=31536000; includeSubDomains"))
    return headers


def configure_audit_logging() -> None:
    """Route audit records to their own stream, separate from application logs."""
    if AUDIT_LOG.handlers:
        return
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s AUDIT %(message)s"))
    AUDIT_LOG.addHandler(handler)
    AUDIT_LOG.propagate = False


def start_maintenance_thread() -> threading.Thread:
    """Periodically drop expired rate-limit and CSRF entries so they cannot grow."""

    def loop() -> None:
        while True:
            time.sleep(RATE_LIMIT_WINDOW)
            rate_limiter.purge_expired()
            csrf_tokens.purge_expired()

    thread = threading.Thread(target=loop, name="vulnoraiq-security-maintenance", daemon=True)
    thread.start()
    return thread
