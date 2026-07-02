from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import mimetypes
import os
import re
import secrets
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from core.scanner import Scanner
from dashboards.generate_dashboard import DashboardGenerator
from dashboards.html_dashboard import HtmlDashboardGenerator
from integrations.target_adapters import connectivity_check, validate_target_definition
from reports.json_report_generator import JsonReportGenerator
from reports.report_generator import MarkdownReportGenerator
from reports.sarif_report_generator import SarifReportGenerator
from webui.agent_host import (
    _run_docker,
    agent_logs,
    delete_template,
    deploy_agent,
    list_agents,
    list_templates,
    remove_agent,
    save_template,
    start_agent,
    stop_agent,
    template_targets,
)
from webui.auth import AuthPrincipal, WebAuthManager
from webui.persistent_jobs import JobStore, PersistedScanJob, create_job_store
from webui.production_checks import validate_all
from webui.project_analyzer import analyze_project, generate_dockerfile, list_projects

LOGGER = logging.getLogger("vulnoraiq.webui")
AUDIT_LOG = logging.getLogger("vulnoraiq.audit")
STATIC_DIR = Path(__file__).parent / "static"
CONFIG_ROOT = Path(os.getenv("VULNORAIQ_CONFIG_DIR", "config"))
OUTPUT_ROOT = Path(os.getenv("VULNORAIQ_WEB_OUTPUT_ROOT", "reports/output/webui"))
TERMINAL_STATES = {"completed", "failed"}
RUNTIME_TARGET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")
AUTH_MANAGER = WebAuthManager(os.getenv("VULNORAIQ_WEB_USERS_PATH", str(CONFIG_ROOT / "web_users.yaml")))
JOB_STORE: JobStore = create_job_store()
STARTED_AT = datetime.now(timezone.utc)

MAX_REQUEST_BODY = int(os.getenv("VULNORAIQ_MAX_REQUEST_BODY", str(10 * 1024 * 1024)))
RATE_LIMIT_WINDOW = int(os.getenv("VULNORAIQ_RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX = int(os.getenv("VULNORAIQ_RATE_LIMIT_MAX", "60"))
MAX_CONCURRENT_SCANS = int(os.getenv("VULNORAIQ_MAX_CONCURRENT_SCANS", "5"))
SCAN_QUEUE_LIMIT = int(os.getenv("VULNORAIQ_SCAN_QUEUE_LIMIT", "20"))
CSRF_TOKEN_TTL = int(os.getenv("VULNORAIQ_CSRF_TOKEN_TTL", "300"))
TRUST_PROXY_HEADERS = os.getenv("VULNORAIQ_TRUST_PROXY_HEADERS", "false").strip().lower() in ("1", "true", "yes")

TRUSTED_PROXY_NETS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
if TRUST_PROXY_HEADERS:
    for item in os.getenv("VULNORAIQ_TRUSTED_PROXY_CIDRS", "").split(","):
        item = item.strip()
        if item:
            TRUSTED_PROXY_NETS.append(ipaddress.ip_network(item, strict=False))

_active_scans: set[str] = set()
_active_scans_lock = threading.Lock()
_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()
_csrf_tokens: dict[str, dict[str, Any]] = {}
_csrf_token_lock = threading.Lock()
_metrics: dict[str, int] = {}
_metrics_lock = threading.Lock()


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def _inc_metric(name: str) -> None:
    with _metrics_lock:
        _metrics[name] = _metrics.get(name, 0) + 1


def _get_metrics_snapshot() -> dict[str, int]:
    with _active_scans_lock:
        active_count = len(_active_scans)
    with _metrics_lock:
        snapshot = dict(_metrics)
    snapshot["active_scans"] = active_count
    return snapshot


def _resolve_client_ip(handler: BaseHTTPRequestHandler) -> str:
    direct_ip = handler.client_address[0]
    if not TRUST_PROXY_HEADERS:
        return direct_ip
    try:
        addr = ipaddress.ip_address(direct_ip)
    except ValueError:
        return direct_ip
    if not any(addr in net for net in TRUSTED_PROXY_NETS):
        return direct_ip
    forwarded = handler.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            return direct_ip
    return direct_ip


def _is_trusted_proxy(handler: BaseHTTPRequestHandler) -> bool:
    if not TRUST_PROXY_HEADERS:
        return False
    try:
        addr = ipaddress.ip_address(handler.client_address[0])
    except ValueError:
        return False
    return any(addr in net for net in TRUSTED_PROXY_NETS)


def _generate_request_id() -> str:
    return uuid.uuid4().hex[:16]


def _safe_audit_field(value: str | None, max_len: int = 200) -> str:
    if value is None:
        return ""
    return value[:max_len].replace("\n", "\\n").replace("\r", "\\r")


def _audit_structured(
    event: str,
    principal: AuthPrincipal,
    request_id: str = "",
    client_ip: str = "",
    method: str = "",
    path: str = "",
    status: int = 0,
    detail: str = "",
) -> None:
    AUDIT_LOG.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": _safe_audit_field(event),
                "request_id": _safe_audit_field(request_id),
                "user": _safe_audit_field(principal.username),
                "role": _safe_audit_field(principal.role),
                "authenticated": str(principal.authenticated).lower(),
                "client_ip": _safe_audit_field(client_ip),
                "method": _safe_audit_field(method),
                "path": _safe_audit_field(path),
                "status": status,
                "detail": _safe_audit_field(detail),
            },
            default=str,
        )
    )


def _rate_limit(client_ip: str) -> bool:
    now = time.monotonic()
    with _rate_limit_lock:
        timestamps = [t for t in _rate_limit_store.get(client_ip, []) if now - t < RATE_LIMIT_WINDOW]
        if len(timestamps) >= RATE_LIMIT_MAX:
            return False
        timestamps.append(now)
        _rate_limit_store[client_ip] = timestamps
    return True


def _clean_rate_limit_store() -> None:
    now = time.monotonic()
    with _rate_limit_lock:
        for ip in list(_rate_limit_store):
            _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if now - t < RATE_LIMIT_WINDOW]
            if not _rate_limit_store[ip]:
                del _rate_limit_store[ip]


def _csrf_session_key(principal: AuthPrincipal, client_ip: str) -> str:
    return f"user:{principal.username}" if principal.authenticated else f"ip:{client_ip}"


def _csrf_token_for(session_key: str) -> str:
    now = time.monotonic()
    with _csrf_token_lock:
        entry = _csrf_tokens.get(session_key)
        if entry and entry["expires"] > now:
            return entry["token"]
        token = secrets.token_urlsafe(32)
        _csrf_tokens[session_key] = {"token": token, "expires": now + CSRF_TOKEN_TTL}
        return token


def _validate_csrf(session_key: str, provided_token: str | None) -> bool:
    if not provided_token:
        return False
    now = time.monotonic()
    with _csrf_token_lock:
        entry = _csrf_tokens.get(session_key)
        if not entry:
            return False
        if entry["expires"] <= now:
            _csrf_tokens.pop(session_key, None)
            return False
        return secrets.compare_digest(entry["token"], provided_token)


def _clean_csrf_store() -> None:
    now = time.monotonic()
    with _csrf_token_lock:
        for key in [k for k, v in _csrf_tokens.items() if v["expires"] <= now]:
            del _csrf_tokens[key]


def _can_view_job(principal: AuthPrincipal, job: PersistedScanJob) -> bool:
    if AUTH_MANAGER.can(principal, "view_all_scans") or AUTH_MANAGER.can(principal, "manage_runtime"):
        return True
    return AUTH_MANAGER.can(principal, "view_scans") and job.created_by == principal.username


def _can_download_job_artifact(principal: AuthPrincipal, job: PersistedScanJob) -> bool:
    if AUTH_MANAGER.can(principal, "download_all_artifacts") or AUTH_MANAGER.can(principal, "manage_runtime"):
        return True
    return AUTH_MANAGER.can(principal, "download_artifacts") and job.created_by == principal.username


def _runtime_targets_path() -> Path:
    return Path(os.getenv("VULNORAIQ_RUNTIME_TARGETS_PATH", str(OUTPUT_ROOT / "runtime_targets.yaml")))


def _load_runtime_targets() -> dict[str, Any]:
    path = _runtime_targets_path()
    if not path.exists():
        return {"targets": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"targets": {}}


def _save_runtime_target(target_id: str, target: dict[str, Any]) -> dict[str, Any]:
    safe_id = target_id.strip()
    if not safe_id or not RUNTIME_TARGET_ID_RE.fullmatch(safe_id):
        raise ValueError("target id must be 2-81 chars and contain only letters, numbers, hyphens, or underscores")
    validated_target = validate_target_definition(safe_id, target)
    runtime = _load_runtime_targets()
    targets = runtime.setdefault("targets", {})
    targets[safe_id] = validated_target
    path = _runtime_targets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(runtime, sort_keys=True), encoding="utf-8")
    return {"target_id": safe_id, "target": validated_target}


def _delete_runtime_target(target_id: str) -> bool:
    runtime = _load_runtime_targets()
    targets = runtime.setdefault("targets", {})
    if target_id not in targets:
        return False
    del targets[target_id]
    path = _runtime_targets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(runtime, sort_keys=True), encoding="utf-8")
    return True


def load_config() -> dict[str, Any]:
    def read_yaml(name: str) -> dict[str, Any]:
        path = CONFIG_ROOT / name
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    raw_targets = read_yaml(os.getenv("VULNORAIQ_TARGET_CONFIG", "targets.yaml")).get("targets") or {}
    runtime_targets = _load_runtime_targets().get("targets", {})
    if isinstance(runtime_targets, dict):
        targets = {**raw_targets, **runtime_targets}
    else:
        targets = raw_targets
    return {
        "targets": targets,
        "profiles": read_yaml("attack_profiles.yaml").get("profiles", {}),
        "web_auth_enabled": AUTH_MANAGER.enabled(),
    }


def _reject_demo_target(target_name: str) -> None:
    allow = os.getenv("VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS", "false").strip().lower() in ("1", "true", "yes")
    if allow:
        return
    lower = target_name.lower()
    for word in ("demo", "mock", "fake", "fixture"):
        if word in lower:
            raise ValueError(
                f"Target '{target_name}' contains '{word}' and is not allowed in normal runtime. "
                "Set VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS=true to enable test fixture targets."
            )


def validate_scan_request(payload: dict[str, Any]) -> tuple[str, str, bool]:
    config = load_config()
    target = str(payload.get("target") or "")
    profile = str(payload.get("profile") or "baseline")
    authorised = bool(payload.get("authorised", True))
    if not target:
        raise ValueError("target is required")
    if target not in config["targets"]:
        raise ValueError(f"Unknown target: {target}")
    _reject_demo_target(target)
    if profile not in config["profiles"]:
        raise ValueError(f"Unknown profile: {profile}")
    return target, profile, authorised


def _acquire_scan_slot(job_id: str) -> bool:
    with _active_scans_lock:
        if len(_active_scans) >= MAX_CONCURRENT_SCANS:
            return False
        _active_scans.add(job_id)
    return True


def _release_scan_slot(job_id: str) -> None:
    with _active_scans_lock:
        _active_scans.discard(job_id)


def run_scan_job(job_id: str) -> None:
    if not _acquire_scan_slot(job_id):
        return
    try:

        def mutate(fn):
            JOB_STORE.update(job_id, fn)

        def start(job: PersistedScanJob) -> None:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc).isoformat()
            job.add_event("scan_started", "Scan started; loading scanner configuration and selected profile.", 5)
            job.add_event("target_validated", "Target configuration and authorisation controls validated.", 12)

        mutate(start)
        job = JOB_STORE.get(job_id)
        if not job:
            return
        job.add_event("phase_started", "Executing selected safe assessment checks.", 20)
        result = Scanner(config_dir=CONFIG_ROOT).scan(
            target_name=job.target, profile_name=job.profile, authorised=job.authorised
        )
        output_dir = OUTPUT_ROOT / job.id
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = MarkdownReportGenerator().generate(result, output_dir / "scan-report.md")
        json_path = JsonReportGenerator().generate(result, output_dir / "scan-report.json")
        sarif_path = SarifReportGenerator().generate(result, output_dir / "scan-report.sarif")
        report_data = json.loads(json_path.read_text(encoding="utf-8"))
        dashboard_path = DashboardGenerator().generate_from_report(report_data, output_dir / "dashboard.md")
        html_dashboard_path = HtmlDashboardGenerator().generate_from_report(report_data, output_dir / "dashboard.html")

        def complete(item: PersistedScanJob) -> None:
            item.status = "completed"
            item.completed_at = datetime.now(timezone.utc).isoformat()
            item.outputs = {
                "markdown": str(markdown_path),
                "json": str(json_path),
                "sarif": str(sarif_path),
                "dashboard_markdown": str(dashboard_path),
                "dashboard_html": str(html_dashboard_path),
            }
            for idx, finding in enumerate(report_data.get("findings", []), start=1):
                item.add_event(
                    "finding_created",
                    f"Finding recorded: {str(finding.get('title') or finding.get('owasp_id') or 'finding')[:120]}",
                    min(85, 30 + idx),
                )
            item.add_event("evidence_saved", "Evidence and report artefacts saved with redaction controls.", 92)
            item.add_event("report_written", "Markdown, JSON, SARIF, and dashboard reports written.", 96)
            item.summary = {
                "target": report_data.get("target"),
                "profile": report_data.get("profile"),
                "finding_count": report_data.get("finding_count"),
                "highest_severity": report_data.get("highest_severity"),
                "policy_status": report_data.get("policy_status"),
                "severity_counts": report_data.get("severity_counts", {}),
                "policy_results": report_data.get("policy_results", []),
                "findings": report_data.get("findings", []),
            }
            item.add_event("completed", "Scan completed and reports are ready.", 100)

        mutate(complete)
        _inc_metric("scans_completed")
    except Exception:
        _inc_metric("scans_failed")
        LOGGER.exception("scan_job_failed job_id=%s", job_id)

        def fail(item: PersistedScanJob) -> None:
            item.status = "failed"
            item.error = "internal scan error"
            item.completed_at = datetime.now(timezone.utc).isoformat()
            item.add_event("failed", "internal scan error", 100, level="error")

        JOB_STORE.update(job_id, fail)
    finally:
        _release_scan_slot(job_id)


class HostedWebUiHandler(BaseHTTPRequestHandler):
    server_version = "VulnoraIQWebUI/0.3.0"

    def _client_ip(self) -> str:
        return _resolve_client_ip(self)

    def _session_key(self, principal: AuthPrincipal) -> str:
        return _csrf_session_key(principal, self._client_ip())

    def _request_id(self) -> str:
        req_id = self.headers.get("X-Request-ID", "").strip()
        return req_id if req_id and len(req_id) <= 64 and req_id.isalnum() else _generate_request_id()

    def _security_headers(self, suppress_hsts: bool = False) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "0")
        if not suppress_hsts and (TRUST_PROXY_HEADERS or self._client_ip() != "127.0.0.1"):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; form-action 'self'; base-uri 'self'; frame-ancestors 'none'",
        )
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def _principal(self, client_ip: str) -> AuthPrincipal | None:
        if AUTH_MANAGER.auth_mode() == "trusted_proxy":
            headers = {
                k: self.headers.get(k, "")
                for k in ("X-Authenticated-User", "X-Authenticated-Email", "X-Authenticated-Groups", "X-VulnoraIQ-Role")
            }
            return AUTH_MANAGER.authenticate_proxy_identity(headers, trusted=_is_trusted_proxy(self))
        return AUTH_MANAGER.authenticate_token(self.headers.get(AUTH_MANAGER.header_name()))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Request-ID", self._request_id())
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_error_response(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _forbidden(self) -> None:
        self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)

    def _check_rate_limit(self, principal: AuthPrincipal, client_ip: str) -> bool:
        if _rate_limit(client_ip):
            return True
        _inc_metric("rate_limit_exceeded")
        self._send_error_response(HTTPStatus.TOO_MANY_REQUESTS, "rate limit exceeded")
        return False

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        if not raw_length.isdigit():
            raise ValueError("invalid Content-Length")
        length = int(raw_length)
        if length > MAX_REQUEST_BODY:
            raise ValueError(f"Request body exceeds maximum allowed size ({MAX_REQUEST_BODY} bytes)")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON request body must be an object")
        return data

    def _require_principal(self, client_ip: str, method: str, path: str, request_id: str) -> AuthPrincipal | None:
        principal = self._principal(client_ip)
        if principal:
            return principal
        _inc_metric("auth_failures")
        _audit_structured(
            "auth_failure",
            AUTH_MANAGER.anonymous(),
            request_id,
            client_ip,
            method,
            path,
            401,
            "authentication required",
        )
        self._send_error_response(HTTPStatus.UNAUTHORIZED, "authentication required")
        return None

    def _handle_request(self, method: str, path: str) -> None:
        request_id = self._request_id()
        client_ip = self._client_ip()
        try:
            if method == "GET":
                self._do_GET_routes(path, client_ip, request_id)
            elif method == "POST":
                self._do_POST_routes(path, client_ip, request_id)
            elif method == "PATCH":
                self._do_PATCH_routes(path, client_ip, request_id)
            else:
                self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
        except ValueError as exc:
            _inc_metric("bad_request")
            self._send_error_response(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception:
            _inc_metric("internal_error")
            LOGGER.exception("internal_error method=%s path=%s", method, path)
            self._send_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, "internal server error")

    def _do_GET_routes(self, path: str, client_ip: str, request_id: str) -> None:
        clean_path = urlparse(path).path
        if clean_path == "/healthz":
            self._send_json({"status": "ok", "service": "vulnoraiq-web", "started_at": STARTED_AT.isoformat()})
            return
        if clean_path == "/readyz":
            cfg = load_config()
            ready = bool(cfg.get("targets")) and bool(cfg.get("profiles"))
            self._send_json(
                {
                    "status": "ready" if ready else "not_ready",
                    "targets_loaded": len(cfg.get("targets", {})),
                    "profiles_loaded": len(cfg.get("profiles", {})),
                    "auth_enabled": cfg.get("web_auth_enabled", False),
                },
                status=HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        if clean_path == "/api/session":
            principal = self._principal(client_ip)
            self._send_json(
                {
                    "auth_enabled": AUTH_MANAGER.enabled(),
                    "authenticated": bool(principal and principal.authenticated),
                    "auth_required": AUTH_MANAGER.enabled() and principal is None,
                    "token_header": AUTH_MANAGER.header_name(),
                    "username": principal.username if principal else None,
                    "role": principal.role if principal else None,
                    "permissions": sorted(principal.permissions) if principal else [],
                }
            )
            return
        if clean_path == "/metrics":
            metrics_auth_required = AUTH_MANAGER.is_production() or _env_flag("VULNORAIQ_METRICS_AUTH_REQUIRED", "true")
            if metrics_auth_required and not self._principal(client_ip):
                self._send_error_response(HTTPStatus.UNAUTHORIZED, "authentication required")
                return
            self._serve_metrics()
            return
        if clean_path == "/":
            # Serve the React SecOps console (built under static/console).
            self._serve_static("console/index.html")
            return
        if clean_path.startswith("/static/"):
            self._serve_static(clean_path.removeprefix("/static/"))
            return

        principal = self._require_principal(client_ip, "GET", clean_path, request_id)
        if not principal or not self._check_rate_limit(principal, client_ip):
            return
        if clean_path == "/api/csrf-token":
            self._send_json({"csrf_token": _csrf_token_for(self._session_key(principal))})
            return
        if clean_path == "/api/targets":
            cfg = load_config()
            self._send_json({"targets": cfg.get("targets", {})})
            return
        if clean_path == "/api/agents":
            agents = list_agents()
            templates = list_templates()
            self._send_json({"agents": agents, "templates": {k: {"display_name": v.get("display_name", k), "description": v.get("description", "")} for k, v in templates.items()}})
            return
        if clean_path.startswith("/api/agents/") and clean_path.endswith("/logs"):
            parts = [unquote(item) for item in clean_path.split("/") if item]
            agent_id = parts[2]
            self._send_json({"logs": agent_logs(agent_id)})
            return
        if clean_path.startswith("/api/agents/") and clean_path.endswith("/templates"):
            parts = [unquote(item) for item in clean_path.split("/") if item]
            template_key = parts[2]
            self._send_json({"template": list_templates().get(template_key, {})})
            return
        if clean_path == "/api/projects":
            self._send_json({"projects": list_projects()})
            return
        if clean_path.startswith("/api/projects/") and clean_path.endswith("/analyze"):
            parts = [unquote(item) for item in clean_path.split("/") if item]
            project_name = parts[2]
            self._send_json(analyze_project(project_name))
            return
        if clean_path.startswith("/api/projects/") and clean_path.endswith("/dockerfile"):
            parts = [unquote(item) for item in clean_path.split("/") if item]
            project_name = parts[2]
            df = generate_dockerfile(project_name)
            self._send_json({"dockerfile": df or "", "exists": df is not None})
            return
        if clean_path == "/api/config":
            cfg = load_config()
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                cfg = {
                    "profiles": {
                        k: {"description": v.get("description", "")} for k, v in cfg.get("profiles", {}).items()
                    },
                    "web_auth_enabled": cfg.get("web_auth_enabled", False),
                }
            self._send_json(cfg)
            return
        if clean_path == "/api/scans":
            if not AUTH_MANAGER.can(principal, "view_scans"):
                self._forbidden()
                return
            self._send_json(
                {
                    "jobs": [
                        job.to_dict(include_events=False) for job in JOB_STORE.list() if _can_view_job(principal, job)
                    ]
                }
            )
            return
        if clean_path.startswith("/api/scans/"):
            self._handle_scan_get(clean_path, principal, client_ip, request_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _do_POST_routes(self, path: str, client_ip: str, request_id: str) -> None:
        clean_path = urlparse(path).path
        principal = self._require_principal(client_ip, "POST", clean_path, request_id)
        if not principal or not self._check_rate_limit(principal, client_ip):
            return
        if clean_path == "/api/targets/save":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            payload = self._read_json()
            target_id = str(payload.get("id") or payload.get("target_id") or "").strip()
            target = payload.get("target")
            if not isinstance(target, dict):
                raise ValueError("target must be a JSON object")
            saved = _save_runtime_target(target_id, target)
            self._send_json({"saved": True, **saved})
            return
        if clean_path == "/api/targets/delete":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            payload = self._read_json()
            target_id = str(payload.get("id") or payload.get("target_id") or "").strip()
            self._send_json({"deleted": _delete_runtime_target(target_id), "target_id": target_id})
            return
        if clean_path.startswith("/api/targets/") and clean_path.endswith("/validate"):
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            parts = [unquote(item) for item in clean_path.split("/") if item]
            target_id = parts[2]
            cfg = load_config().get("targets", {})
            if target_id not in cfg:
                self._send_error_response(HTTPStatus.NOT_FOUND, "target not found")
                return
            self._send_json(connectivity_check(target_id, cfg[target_id]))
            return
        if clean_path == "/api/agents/deploy":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            payload = self._read_json()
            agent_id = str(payload.get("id") or "").strip()
            template_key = payload.get("template")
            image = payload.get("image")
            env = payload.get("env") or {}
            try:
                port = int(payload["port"]) if payload.get("port") not in (None, "") else None
            except (TypeError, ValueError):
                self._send_error_response(HTTPStatus.BAD_REQUEST, "port must be a number")
                return
            if not agent_id:
                self._send_error_response(HTTPStatus.BAD_REQUEST, "agent id is required")
                return
            if not template_key and not image:
                self._send_error_response(HTTPStatus.BAD_REQUEST, "template or image is required")
                return
            result = deploy_agent(agent_id, template_key=template_key, image=image, env=env, port=port)
            for entry in template_targets(template_key) if template_key else []:
                try:
                    _save_runtime_target(entry["id"], entry["config"])
                except ValueError:
                    pass
            # Custom-image agents become scannable targets too: the published port is
            # reachable from the host, so register an http_json target pointing at it.
            if image and port:
                endpoint = str(payload.get("endpoint") or "/").strip() or "/"
                response_path = str(payload.get("response_path") or "response").strip() or "response"
                body_template = payload.get("body_template")
                if isinstance(body_template, str) and body_template.strip():
                    try:
                        body_template = json.loads(body_template)
                    except json.JSONDecodeError:
                        body_template = None
                if not isinstance(body_template, dict):
                    body_template = {"prompt": "{{prompt}}"}
                target_id = f"agent-{agent_id}"[:81]
                target_cfg = {
                    "name": agent_id,
                    "type": "http_json",
                    "base_url": f"http://127.0.0.1:{port}",
                    "endpoint_path": endpoint,
                    "method": "POST",
                    "request_body_template": body_template,
                    "response_extraction_path": response_path,
                    "environment": "lab",
                    "authorisation_required": True,
                }
                try:
                    saved = _save_runtime_target(target_id, target_cfg)
                    result["target_id"] = saved["target_id"]
                except ValueError as exc:
                    result["target_warning"] = str(exc)
            self._send_json(result)
            return
        if clean_path == "/api/agents/templates":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            payload = self._read_json()
            key = str(payload.get("key") or "").strip()
            image = str(payload.get("image") or "").strip()
            if not key or not RUNTIME_TARGET_ID_RE.fullmatch(key):
                self._send_error_response(HTTPStatus.BAD_REQUEST, "template name must be 2-81 chars: letters, numbers, hyphens, underscores")
                return
            if not image:
                self._send_error_response(HTTPStatus.BAD_REQUEST, "docker image is required")
                return
            try:
                port = int(payload["port"]) if payload.get("port") not in (None, "") else None
            except (TypeError, ValueError):
                self._send_error_response(HTTPStatus.BAD_REQUEST, "port must be a number")
                return
            endpoint = str(payload.get("endpoint") or "/").strip() or "/"
            env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
            template: dict[str, Any] = {"image": image, "env": env}
            if port:
                template["ports"] = [f"{port}:{port}"]
                template["targets"] = [{
                    "id": f"agent-{key}"[:81],
                    "config": {
                        "name": key,
                        "type": "http_json",
                        "base_url": f"http://127.0.0.1:{port}",
                        "endpoint_path": endpoint,
                        "method": "POST",
                        "request_body_template": {"prompt": "{{prompt}}"},
                        "response_extraction_path": "response",
                        "environment": "lab",
                        "authorisation_required": True,
                    },
                }]
            saved = save_template(key, template)
            self._send_json({"saved": True, "key": key, "template": saved})
            return
        if clean_path.startswith("/api/agents/templates/") and clean_path.endswith("/delete"):
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            parts = [unquote(item) for item in clean_path.split("/") if item]
            key = parts[3]
            deleted = delete_template(key)
            self._send_json({"deleted": deleted, "key": key})
            return
        if clean_path.startswith("/api/agents/") and any(clean_path.endswith(suffix) for suffix in ("/stop", "/start", "/remove")):
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            parts = [unquote(item) for item in clean_path.split("/") if item]
            agent_id = parts[2]
            action = parts[3]
            if action == "stop":
                ok = stop_agent(agent_id)
            elif action == "start":
                ok = start_agent(agent_id)
            elif action == "remove":
                ok = remove_agent(agent_id)
            else:
                self._send_error_response(HTTPStatus.BAD_REQUEST, f"unknown action: {action}")
                return
            self._send_json({"ok": ok, "agent_id": agent_id, "action": action})
            return
        if clean_path == "/api/projects/deploy":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            if not AUTH_MANAGER.can(principal, "manage_runtime"):
                self._forbidden()
                return
            payload = self._read_json()
            project_name = str(payload.get("project", "")).strip()
            env = payload.get("env") or {}
            if not project_name:
                self._send_error_response(HTTPStatus.BAD_REQUEST, "project name is required")
                return
            from webui.project_analyzer import PROJECTS_ROOT, analyze_project
            proj_path = PROJECTS_ROOT / project_name
            if not proj_path.exists():
                self._send_error_response(HTTPStatus.NOT_FOUND, f"project '{project_name}' not found")
                return
            project_info = analyze_project(project_name)
            df_path = proj_path / "Dockerfile"
            if not df_path.exists():
                df_content = generate_dockerfile(project_name)
                if not df_content:
                    self._send_error_response(HTTPStatus.BAD_REQUEST, "cannot generate Dockerfile for this project")
                    return
                df_path.write_text(df_content, encoding="utf-8")
            image_tag = f"vulnoraiq-project-{project_name}".lower().replace("_", "-")
            ports = project_info.get("ports", [5000])
            try:
                _run_docker(["build", "-t", image_tag, str(proj_path)])
            except RuntimeError as exc:
                self._send_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"build failed: {exc}")
                return
            container_name = f"vulnoraiq-agent-{project_name}"
            try:
                _run_docker(["rm", "-f", container_name])
            except RuntimeError:
                pass
            port_flags = []
            for p in ports:
                port_flags += ["-p", f"{p}:{p}"]
            env_flags = []
            for k, v in env.items():
                if v:
                    env_flags += ["-e", f"{k}={v}"]
            cmd = ["run", "-d", "--name", container_name, "--label", "vulnoraiq.agent=project-deploy", "--label", f"vulnoraiq.agent.id={project_name}", "--network", "vulnoraiq_vulnoraiq-lab", "--restart", "unless-stopped"] + port_flags + env_flags + ["-v", f"{proj_path}:/app:ro", image_tag]
            try:
                container_id, _ = _run_docker(cmd)
            except RuntimeError:
                raise
            for ep in project_info.get("endpoints", []):
                endpoint_path = ep.get("path", "/")
                param_key = ep.get("param_key", "prompt")
                method = ep.get("method", "GET")
                target_id = f"{project_name}-{ep['method'].lower()}-{endpoint_path.replace('/', '_').strip('_') or 'root'}"
                request_body = {param_key: "{{prompt}}"} if method == "POST" else None
                cfg = {
                    "name": f"{project_name} {ep['method']} {endpoint_path}",
                    "type": "http_json",
                    "base_url": f"http://{container_name}:{ports[0]}",
                    "endpoint_path": endpoint_path,
                    "method": method,
                    "request_body_template": request_body or {},
                    "response_extraction_path": "",
                    "authorisation_required": True,
                    "environment": "lab",
                    "safety_profile": "local_lab_safe",
                }
                try:
                    _save_runtime_target(target_id, cfg)
                except ValueError:
                    pass
            self._send_json({"container_id": container_id, "agent_id": project_name, "name": container_name, "status": "deployed", "ports": ports, "endpoints": project_info.get("endpoints", [])})
            return
        parts = [unquote(item) for item in clean_path.split("/") if item]
        if len(parts) == 6 and parts[:2] == ["api", "scans"] and parts[3] == "findings" and parts[5] == "actions":
            if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
                self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
                return
            job = JOB_STORE.get(parts[2])
            if not job:
                self._send_error_response(HTTPStatus.NOT_FOUND, "scan not found")
                return
            if not _can_view_job(principal, job):
                self._forbidden()
                return
            payload = self._validate_finding_patch(self._read_json())
            updated = JOB_STORE.update_finding(job.id, parts[4], payload, principal.username)
            if not updated:
                self._send_error_response(HTTPStatus.NOT_FOUND, "finding not found")
                return
            _audit_structured(
                "finding_action",
                principal,
                request_id,
                client_ip,
                "POST",
                clean_path,
                200,
                f"scan={job.id} finding={parts[4]}",
            )
            self._send_json({"finding_state": updated})
            return
        if clean_path != "/api/scans":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
            _inc_metric("csrf_failures")
            self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
            return
        if "application/json" not in self.headers.get("Content-Type", "").lower():
            _inc_metric("bad_request")
            self._send_error_response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
            return
        target, profile, authorised = validate_scan_request(self._read_json())
        if not AUTH_MANAGER.can(principal, "start_configured_scan"):
            self._forbidden()
            return
        with _active_scans_lock:
            if len(_active_scans) >= SCAN_QUEUE_LIMIT:
                self._send_error_response(HTTPStatus.TOO_MANY_REQUESTS, "scan queue at capacity")
                return
        job = JOB_STORE.create(target, profile, authorised, created_by=principal.username)
        _inc_metric("scans_created")
        threading.Thread(target=run_scan_job, args=(job.id,), daemon=True).start()
        self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)

    def _handle_scan_get(self, path: str, principal: AuthPrincipal, client_ip: str, request_id: str) -> None:
        parts = [unquote(item) for item in path.split("/") if item]
        if len(parts) < 3:
            self.send_error(HTTPStatus.NOT_FOUND, "Scan not found")
            return
        job = JOB_STORE.get(parts[2])
        if not job:
            self.send_error(HTTPStatus.NOT_FOUND, "Scan not found")
            return
        if len(parts) == 3:
            if not _can_view_job(principal, job):
                self._forbidden()
                return
            self._send_json(job.to_dict())
            return
        if parts[3] == "findings":
            self._handle_finding_get(parts, principal, job)
            return
        if parts[3] == "events":
            if not _can_view_job(principal, job):
                self._forbidden()
                return
            self._send_events(job.id)
            return
        if parts[3] == "artifact" and len(parts) == 5:
            if not _can_download_job_artifact(principal, job):
                self._forbidden()
                return
            self._send_artifact(job, parts[4], principal, client_ip, request_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Scan resource not found")

    def _send_artifact(
        self, job: PersistedScanJob, artifact_name: str, principal: AuthPrincipal, client_ip: str, request_id: str
    ) -> None:
        name = artifact_name.replace("\\", "/")
        if "/" in name or ".." in name:
            self._send_error_response(HTTPStatus.BAD_REQUEST, "invalid artifact name")
            return
        path = job.outputs.get(artifact_name)
        if not path:
            self.send_error(HTTPStatus.NOT_FOUND, "Artifact not found")
            return
        file_path = Path(path)
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Artifact file not found")
            return
        data = file_path.read_bytes()
        _inc_metric("artifact_downloads")
        _audit_structured(
            "artifact_download",
            principal,
            request_id,
            client_ip,
            "GET",
            f"/api/scans/{job.id}/artifact/{artifact_name}",
            200,
            f"artifact={artifact_name} job={job.id}",
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name.replace(chr(34), "")}"')
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_events(self, job_id: str) -> None:
        last_id = 0
        raw_last_id = self.headers.get("Last-Event-ID", "0").strip()
        if raw_last_id.isdigit():
            last_id = int(raw_last_id)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._security_headers()
        self.end_headers()
        while True:
            job = JOB_STORE.get(job_id)
            if not job:
                return
            if hasattr(JOB_STORE, "list_events_after"):
                events = JOB_STORE.list_events_after(job_id, last_id)
            else:
                events = [ev for ev in job.events if ev.event_id > last_id]
            for event in events:
                payload = asdict(event)
                payload["scan_id"] = job_id
                payload["severity"] = payload.pop("level", "info")
                payload["progress"] = {"current": int(event.progress), "total": 100, "percent": float(event.progress)}
                last_id = int(event.event_id or last_id + 1)
                self.wfile.write(
                    f"id: {last_id}\nevent: {event.type}\ndata: {json.dumps(payload, default=str)}\n\n".encode()
                )
                self.wfile.flush()
            if job.status in TERMINAL_STATES:
                self.wfile.write(f"event: done\ndata: {json.dumps(job.to_dict(), default=str)}\n\n".encode())
                self.wfile.flush()
                return
            heartbeat = {
                "event_id": last_id,
                "scan_id": job_id,
                "type": "heartbeat",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "info",
                "message": "scan still running",
                "phase": job.events[-1].stage if job.events else "running",
                "progress": {"current": job.progress, "total": 100, "percent": float(job.progress)},
                "data": {},
            }
            self.wfile.write(f"event: heartbeat\ndata: {json.dumps(heartbeat)}\n\n".encode())
            self.wfile.flush()
            time.sleep(0.4)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: ("[REDACTED]" if re.search(r"token|secret|key|cookie|authorization", k, re.I) else self._redact(v))
                for k, v in value.items()
            }
        if isinstance(value, str):
            return re.sub(r"(?i)(bearer\s+)[a-z0-9._\-]+|sk-[a-z0-9._\-]+", "[REDACTED]", value)
        return value

    def _validate_finding_patch(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {"open", "triaged", "in_progress", "accepted_risk", "false_positive", "fixed", "wont_fix"}
        status = payload.get("status")
        if status and status not in allowed:
            raise ValueError("invalid finding status")
        if status == "false_positive" and not payload.get("false_positive_reason"):
            raise ValueError("false_positive requires a reason")
        if status == "accepted_risk" and not payload.get("accepted_risk_reason"):
            raise ValueError("accepted_risk requires a reason")
        return self._redact(payload)

    def _handle_finding_get(self, parts: list[str], principal: AuthPrincipal, job: PersistedScanJob) -> None:
        if not _can_view_job(principal, job):
            self._forbidden()
            return
        if not hasattr(JOB_STORE, "list_findings"):
            self._send_json({"findings": job.summary.get("findings", [])})
            return
        if len(parts) == 4:
            self._send_json({"findings": JOB_STORE.list_findings(job.id)})
            return
        finding_id = parts[4]
        findings = JOB_STORE.list_findings(job.id)
        finding = next((f for f in findings if str(f.get("id") or f.get("owasp_id")) == finding_id), None)
        if not finding:
            self._send_error_response(HTTPStatus.NOT_FOUND, "finding not found")
            return
        if len(parts) == 5:
            self._send_json({"finding": finding})
            return
        if len(parts) == 6 and parts[5] == "history":
            self._send_json({"history": JOB_STORE.finding_history(job.id, finding_id)})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Finding resource not found")

    def _do_PATCH_routes(self, path: str, client_ip: str, request_id: str) -> None:
        clean_path = urlparse(path).path
        principal = self._require_principal(client_ip, "PATCH", clean_path, request_id)
        if not principal or not self._check_rate_limit(principal, client_ip):
            return
        if not _validate_csrf(self._session_key(principal), self.headers.get("X-CSRF-Token")):
            self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
            return
        parts = [unquote(item) for item in clean_path.split("/") if item]
        if len(parts) == 5 and parts[:2] == ["api", "scans"] and parts[3] == "findings":
            job = JOB_STORE.get(parts[2])
            if not job:
                self._send_error_response(HTTPStatus.NOT_FOUND, "scan not found")
                return
            if not _can_view_job(principal, job):
                self._forbidden()
                return
            updated = JOB_STORE.update_finding(
                job.id, parts[4], self._validate_finding_patch(self._read_json()), principal.username
            )
            if not updated:
                self._send_error_response(HTTPStatus.NOT_FOUND, "finding not found")
                return
            _audit_structured(
                "finding_mutation",
                principal,
                request_id,
                client_ip,
                "PATCH",
                clean_path,
                200,
                f"scan={job.id} finding={parts[4]}",
            )
            self._send_json({"finding_state": updated})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _serve_static(self, relative_path: str) -> None:
        safe_relative = Path(relative_path)
        if safe_relative.is_absolute() or ".." in safe_relative.parts:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid path")
            return
        file_path = STATIC_DIR / safe_relative
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _serve_metrics(self) -> None:
        metrics = _get_metrics_snapshot()
        lines = [
            "# HELP vulnoraiq_up Process uptime",
            "# TYPE vulnoraiq_up gauge",
            "vulnoraiq_up 1",
            "# HELP vulnoraiq_started_at Unix timestamp when the process started",
            "# TYPE vulnoraiq_started_at gauge",
            f"vulnoraiq_started_at {STARTED_AT.timestamp():.0f}",
            "# HELP vulnoraiq_active_scans Currently active scan count",
            "# TYPE vulnoraiq_active_scans gauge",
            f"vulnoraiq_active_scans {metrics.get('active_scans', 0)}",
            "# HELP vulnoraiq_auth_failures_total Authentication failure count",
            "# TYPE vulnoraiq_auth_failures_total counter",
            f"vulnoraiq_auth_failures_total {metrics.get('auth_failures', 0)}",
            "# HELP vulnoraiq_authz_failures_total Authorization failure count",
            "# TYPE vulnoraiq_authz_failures_total counter",
            f"vulnoraiq_authz_failures_total {metrics.get('authz_failures', 0)}",
            "# HELP vulnoraiq_scans_created_total Total scans created",
            "# TYPE vulnoraiq_scans_created_total counter",
            f"vulnoraiq_scans_created_total {metrics.get('scans_created', 0)}",
            "# HELP vulnoraiq_scans_completed_total Total scans completed",
            "# TYPE vulnoraiq_scans_completed_total counter",
            f"vulnoraiq_scans_completed_total {metrics.get('scans_completed', 0)}",
            "# HELP vulnoraiq_scans_failed_total Total scans failed",
            "# TYPE vulnoraiq_scans_failed_total counter",
            f"vulnoraiq_scans_failed_total {metrics.get('scans_failed', 0)}",
        ]
        data = "\n".join(lines).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._handle_request("GET", self.path)

    def do_POST(self) -> None:
        self._handle_request("POST", self.path)

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("http_request client=%s message=%s", self.address_string(), format % args)

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        try:
            body = (message or "").encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Request-ID", self._request_id())
            self._security_headers()
            self.end_headers()
            if body:
                self.wfile.write(body)
        except OSError:
            pass


def create_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), HostedWebUiHandler)


def _rate_limit_cleanup_loop() -> None:
    while True:
        time.sleep(RATE_LIMIT_WINDOW)
        _clean_rate_limit_store()
        _clean_csrf_store()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("VULNORAIQ_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    audit_handler = logging.StreamHandler()
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(logging.Formatter("%(asctime)s AUDIT %(message)s"))
    AUDIT_LOG.addHandler(audit_handler)
    AUDIT_LOG.propagate = False
    parser = argparse.ArgumentParser(description="Run the VulnoraIQ hosted web UI.")
    parser.add_argument("--host", default=os.getenv("VULNORAIQ_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VULNORAIQ_PORT", "8787")))
    parser.add_argument("--production", action="store_true", help="Enable production mode validation")
    parser.add_argument("--skip-production-checks", action="store_true", help="Skip production config validation")
    args = parser.parse_args()
    if args.production or AUTH_MANAGER.is_production():
        try:
            AUTH_MANAGER._validate_production()
        except RuntimeError as exc:
            LOGGER.error("production_mode_validation_failed: %s", exc)
            raise SystemExit(1) from exc
        if not args.skip_production_checks:
            results = validate_all(host=args.host)
            failed = [r for r in results if r["status"] != "pass"]
            if failed:
                raise SystemExit(1)
    threading.Thread(target=_rate_limit_cleanup_loop, daemon=True).start()
    create_server(args.host, args.port).serve_forever()


if __name__ == "__main__":
    main()
