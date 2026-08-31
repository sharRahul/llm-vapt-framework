from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AuthPrincipal:
    username: str
    role: str
    permissions: set[str]
    authenticated: bool


_ENV_AUTH_ENABLED = "VULNORAIQ_AUTH_ENABLED"
_ENV_ADMIN_TOKEN = "VULNORAIQ_ADMIN_TOKEN"
_ENV_ANALYST_TOKEN = "VULNORAIQ_ANALYST_TOKEN"
_ENV_VIEWER_TOKEN = "VULNORAIQ_VIEWER_TOKEN"
_ENV_PRODUCTION = "VULNORAIQ_ENV"
_ENV_AUTH_MODE = "VULNORAIQ_AUTH_MODE"
_ENV_RUN_MODE = "VULNORAIQ_RUN_MODE"
_ENV_LOCAL_ADMIN_BIND_OK = "VULNORAIQ_LOCAL_ADMIN_BIND_OK"

_AUTH_MODE_LOCAL_ADMIN = "local_admin"
_AUTH_MODE_TOKEN = "token"
_AUTH_MODE_TRUSTED_PROXY = "trusted_proxy"
_VALID_AUTH_MODES = {_AUTH_MODE_LOCAL_ADMIN, _AUTH_MODE_TOKEN, _AUTH_MODE_TRUSTED_PROXY}

_DEFAULT_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"view_scans", "download_artifacts", "view_own_scans", "download_own_artifacts"},
    # analyst currently carries the same capabilities as viewer; it exists as a
    # separate configurable identity, not as an extra permission level.
    "analyst": {"view_scans", "download_artifacts", "view_own_scans", "download_own_artifacts"},
    "admin": {
        "view_scans",
        "download_artifacts",
        "view_own_scans",
        "download_own_artifacts",
        "view_all_scans",
        "download_all_artifacts",
        "start_configured_scan",
        "manage_runtime",
    },
}

_MIN_TOKEN_LENGTH = 20

_PROXY_HEADER_USER = "X-Authenticated-User"
_PROXY_HEADER_EMAIL = "X-Authenticated-Email"
_PROXY_HEADER_GROUPS = "X-Authenticated-Groups"
_PROXY_HEADER_ROLE = "X-VulnoraIQ-Role"

_DEFAULT_ROLE_MAPPING: dict[str, str] = {
    "admin": "admin",
    "analyst": "analyst",
    "viewer": "viewer",
}


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def _normalise_auth_mode(value: str) -> str:
    return value.strip().lower().replace("-", "_")


class WebAuthManager:
    """Role-aware auth manager with an explicit local single-user admin mode."""

    def __init__(self, path: str | Path = "config/web_users.yaml") -> None:
        self.path = Path(path)
        self._config: dict[str, Any] | None = None
        self._env_tokens: dict[str, str] | None = None

    def is_production(self) -> bool:
        return os.getenv(_ENV_PRODUCTION, "").strip().lower() == "production"

    def run_mode(self) -> str:
        return os.getenv(_ENV_RUN_MODE, "").strip().lower().replace("-", "_")

    def auth_mode(self) -> str:
        explicit_mode = os.getenv(_ENV_AUTH_MODE, "").strip()
        if explicit_mode:
            return _normalise_auth_mode(explicit_mode)

        env_val = os.getenv(_ENV_AUTH_ENABLED)
        if env_val is not None and env_val.strip().lower() in ("0", "false", "no"):
            # Backward-compatible alias for older launcher/Compose configs.
            return _AUTH_MODE_LOCAL_ADMIN

        cfg = self.load()
        if cfg and cfg.get("auth", {}).get("enabled") is False:
            return _AUTH_MODE_LOCAL_ADMIN

        return _AUTH_MODE_TOKEN

    def validate_production(self) -> None:
        if not self.is_production():
            return
        if self.auth_mode() == _AUTH_MODE_LOCAL_ADMIN:
            raise RuntimeError(
                "Production mode does not allow VULNORAIQ_AUTH_MODE=local_admin. "
                "Use VULNORAIQ_AUTH_MODE=token with VULNORAIQ_ADMIN_TOKEN."
            )
        if not self.enabled():
            raise RuntimeError(
                "Production mode requires authentication. "
                "Set VULNORAIQ_AUTH_MODE=token and VULNORAIQ_ADMIN_TOKEN."
            )
        env_tokens = self._load_env_tokens()
        if not env_tokens or "admin" not in env_tokens.values():
            raise RuntimeError(
                "Production mode requires at least VULNORAIQ_ADMIN_TOKEN to be set "
                "with a value of 20 characters or more."
            )
        for token, role in env_tokens.items():
            if role == "admin" and len(token) < _MIN_TOKEN_LENGTH:
                raise RuntimeError(
                    f"VULNORAIQ_ADMIN_TOKEN must be at least {_MIN_TOKEN_LENGTH} characters "
                    f"in production mode (got {len(token)})."
                )

    def validate_runtime_auth(self, host: str) -> None:
        mode = self.auth_mode()
        if mode not in _VALID_AUTH_MODES:
            raise RuntimeError(
                f"Unsupported VULNORAIQ_AUTH_MODE={mode!r}. "
                f"Use one of: {', '.join(sorted(_VALID_AUTH_MODES))}."
            )
        if mode == _AUTH_MODE_LOCAL_ADMIN:
            if self.is_production():
                raise RuntimeError("VULNORAIQ_AUTH_MODE=local_admin is not allowed when VULNORAIQ_ENV=production.")
            if self._local_admin_container_bind_allowed():
                return
            if not self._is_loopback_host(host):
                raise RuntimeError(
                    "VULNORAIQ_AUTH_MODE=local_admin requires the WebUI host to be loopback "
                    "(127.0.0.1, ::1, or localhost). Refusing to start on a network-facing bind."
                )

    def _local_admin_container_bind_allowed(self) -> bool:
        return self.run_mode() in {"docker_lab", "lab"} and _env_true(_ENV_LOCAL_ADMIN_BIND_OK)

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        candidate = host.strip().lower().strip("[]")
        if candidate == "localhost":
            return True
        try:
            return ipaddress.ip_address(candidate).is_loopback
        except ValueError:
            return False

    def _load_env_tokens(self) -> dict[str, str]:
        if self._env_tokens is None:
            tokens: dict[str, str] = {}
            for key, role in [
                (_ENV_ADMIN_TOKEN, "admin"),
                (_ENV_ANALYST_TOKEN, "analyst"),
                (_ENV_VIEWER_TOKEN, "viewer"),
            ]:
                val = os.getenv(key, "").strip()
                if val:
                    tokens[val] = role
            self._env_tokens = tokens
        return self._env_tokens

    def has_file_auth(self) -> bool:
        if not self.path.exists():
            return False
        users = self.load().get("users", [])
        return any(u.get("status") == "active" for u in users)

    def load(self) -> dict[str, Any]:
        if self._config is None:
            if self.path.exists():
                self._config = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            else:
                self._config = {}
        return self._config

    def enabled(self) -> bool:
        return self.auth_mode() != _AUTH_MODE_LOCAL_ADMIN

    def header_name(self) -> str:
        return str(self.load().get("auth", {}).get("header_name", "X-VulnoraIQ-Token"))

    def local_admin(self) -> AuthPrincipal:
        return AuthPrincipal("local-admin", "admin", _DEFAULT_PERMISSIONS["admin"], authenticated=False)

    def anonymous(self) -> AuthPrincipal:
        """The unauthenticated identity recorded against rejected requests."""
        return AuthPrincipal("anonymous", "viewer", _DEFAULT_PERMISSIONS["viewer"], authenticated=False)

    def authenticate_token(self, token: str | None) -> AuthPrincipal | None:
        if self.auth_mode() == _AUTH_MODE_LOCAL_ADMIN:
            return self.local_admin()

        if not token:
            return None

        env_tokens = self._load_env_tokens()
        if env_tokens:
            for candidate, role in env_tokens.items():
                if hmac.compare_digest(candidate, token):
                    return AuthPrincipal(f"env-{role}", role, _DEFAULT_PERMISSIONS[role], authenticated=True)
            return None

        if self.is_production() and self.has_file_auth():
            raise RuntimeError("File-based web_users.yaml auth is not allowed in production mode; use environment tokens.")

        for user in self.load().get("users", []):
            if user.get("status") != "active":
                continue
            token_hash = str(user.get("token_sha256", ""))
            if token and hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), token_hash):
                role = str(user.get("role", "viewer"))
                return AuthPrincipal(str(user.get("username", "user")), role, _DEFAULT_PERMISSIONS.get(role, set()), True)
        return None

    def authenticate_proxy_identity(self, headers: dict[str, str], trusted: bool) -> AuthPrincipal | None:
        if not trusted:
            return None
        username = (headers.get(_PROXY_HEADER_USER) or headers.get(_PROXY_HEADER_EMAIL) or "").strip()
        if not username:
            return None
        raw_role = (headers.get(_PROXY_HEADER_ROLE) or "").strip().lower()
        if not raw_role:
            groups = (headers.get(_PROXY_HEADER_GROUPS) or "").lower()
            if "admin" in groups:
                raw_role = "admin"
            elif "analyst" in groups:
                raw_role = "analyst"
            else:
                raw_role = "viewer"
        role = _DEFAULT_ROLE_MAPPING.get(raw_role, "viewer")
        return AuthPrincipal(f"proxy:{username}", role, _DEFAULT_PERMISSIONS.get(role, _DEFAULT_PERMISSIONS["viewer"]), True)

    def permissions_for_role(self, role: str) -> set[str]:
        return set(_DEFAULT_PERMISSIONS.get(role, set()))

    @staticmethod
    def can(principal: AuthPrincipal | None, permission: str) -> bool:
        return bool(principal and permission in principal.permissions)
