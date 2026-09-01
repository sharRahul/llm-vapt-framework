from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import yaml

SECRET_PATTERNS = [re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]+=*", re.I), re.compile(r"(?i)(api[_-]?key|token|secret|password)['\"]?\s*[:=]\s*['\"]?([^,'\"\s}]+)")]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<redacted>" if any(s in k.lower() for s in ("token", "secret", "password", "key", "authorization")) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        out = value
        for pat in SECRET_PATTERNS:
            out = pat.sub(lambda m: (m.group(1) + "=<redacted>") if len(m.groups()) > 1 else "Bearer <redacted>", out)
        return out[:20000]
    return value


def get_path(data: Any, path: str | None) -> Any:
    if not path:
        return data
    cur = data
    for part in path.replace("$.", "").split("."):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def render_template(obj: Any, prompt: str, target: dict[str, Any]) -> Any:
    if isinstance(obj, dict):
        return {k: render_template(v, prompt, target) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_template(v, prompt, target) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{{prompt}}", prompt).replace("{{input}}", prompt).replace("{{payload}}", prompt).replace("{{ payload }}", prompt).replace("{{model}}", str(target.get("model", "local-model")))
    return obj


@dataclass(slots=True)
class AdapterResult:
    ok: bool
    answer: str = ""
    status_code: int | None = None
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    tool_calls: list[Any] = field(default_factory=list)
    retrieval_context: Any = None
    duration_ms: int = 0


class RealTargetClient:
    name: str

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = normalize_target_config(name, config)
        self.last_result: AdapterResult | None = None
        self._last_request_at = 0.0

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        result = self.invoke_detailed(prompt, **kwargs)
        self.last_result = result
        if not result.ok:
            return f"TARGET_ERROR: {result.error.get('message') if result.error else 'unknown error'}"
        return result.answer

    def invoke_detailed(self, prompt: str, **kwargs: Any) -> AdapterResult:
        return invoke_target(self.name, self.config, prompt)


def normalize_target_config(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(raw)
    if "endpoint" in cfg and "base_url" not in cfg:
        parsed = urlparse(str(cfg["endpoint"]))
        cfg["base_url"] = f"{parsed.scheme}://{parsed.netloc}"
        cfg["endpoint_path"] = parsed.path or "/"
    cfg.setdefault("name", name)
    cfg.setdefault("method", "POST")
    cfg.setdefault("headers", {})
    cfg.setdefault("timeout", cfg.get("timeout_seconds", 30))
    cfg.setdefault("retry", {"attempts": 1, "backoff_seconds": 0.2})
    cfg.setdefault("rate_limit", {"requests_per_second": 1})
    cfg.setdefault("authorisation_required", True)
    cfg.setdefault("safety_profile", "local_lab_safe")
    cfg.setdefault("environment", "local")
    cfg.setdefault("tags", [])
    t = cfg.get("type")
    if t in {"custom_agent", "custom_http_agent", "http"}:
        cfg["type"] = "http_json"
    if t == "chat_completions_compatible":
        cfg["type"] = "chat_completions"
    return cfg


def validate_target_definition(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    cfg = normalize_target_config(name, raw)
    target_type = str(cfg.get("type") or "").strip()
    if target_type not in {"http_json", "chat_completions", "ollama_generate", "webhook_json", "rag_query", "agent_tool_loop"}:
        raise ValueError(f"unsupported target type: {target_type or '<missing>'}")
    if not str(cfg.get("name") or "").strip():
        raise ValueError("target name is required")
    if not str(cfg.get("base_url") or "").strip():
        raise ValueError("base_url or endpoint is required")
    endpoint_path = str(cfg.get("endpoint_path") or "/").strip()
    if not endpoint_path.startswith("/"):
        raise ValueError("endpoint_path must start with '/'")
    cfg["endpoint_path"] = endpoint_path
    if target_type in {"chat_completions", "ollama_generate"} and not str(cfg.get("model") or "").strip():
        raise ValueError(f"model is required for target type {target_type}")
    body_template = cfg.get("request_body_template")
    if body_template is not None and not isinstance(body_template, (dict, list)):
        raise ValueError("request_body_template must be a JSON object or array")
    headers = cfg.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError("headers must be a JSON object")
    validate_url(cfg)
    return cfg


def _safety_profiles_path() -> str:
    return os.getenv("VULNORAIQ_SAFETY_PROFILE_PATH") or str(
        Path(os.getenv("VULNORAIQ_CONFIG_DIR", "config")) / "safety_profiles.yaml"
    )


def _load_safety_profile(name: str) -> dict[str, Any]:
    """Return one named safety profile, cached per (path, mtime).

    The profile is consulted several times per outbound request; re-reading and
    re-parsing the YAML each time was both wasteful and leaked file handles.

    Fails closed. A profile that cannot be read, or a target naming a profile
    the file does not define, raises instead of yielding an empty mapping —
    silently dropping the limits a safety profile exists to impose is the one
    outcome worse than refusing to run.
    """
    path = _safety_profiles_path()
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        if name:
            raise ValueError(f"safety profile '{name}' is unavailable: cannot read {path}") from None
        return {}
    profiles = _safety_profiles_cached(path, stamp)
    if not name:
        return {}
    if name not in profiles:
        raise ValueError(f"safety profile '{name}' is not defined in {path}")
    return profiles[name]


@lru_cache(maxsize=8)
def _safety_profiles_cached(path: str, _stamp: int) -> dict[str, dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise ValueError(f"safety profiles are unreadable: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"safety profiles are malformed: {path}") from exc
    profiles = data.get("safety_profiles")
    if profiles is None:
        return {}
    if not isinstance(profiles, dict):
        raise ValueError(f"safety_profiles in {path} must be a mapping of profile name to settings")
    return profiles


def _environment_allowed_hosts() -> set[str]:
    raw = os.getenv("VULNORAIQ_ALLOWED_TARGET_HOSTS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _host_matches(hostname: str, allowed: str) -> bool:
    if allowed.startswith("*."):
        return hostname.endswith(allowed[1:]) and hostname != allowed[2:]
    return hostname == allowed


def _enforce_environment_allowlist(hostname: str) -> None:
    """Apply the deployment-wide target host allowlist, when one is configured.

    ``VULNORAIQ_ALLOWED_TARGET_HOSTS`` is an operator-level guard rail that sits
    above per-target safety profiles: nothing outside it is ever contacted.
    Entries may be exact hosts or ``*.suffix`` wildcards.
    """
    allowed = _environment_allowed_hosts()
    if allowed and not any(_host_matches(hostname, item) for item in allowed):
        raise ValueError(f"target host '{hostname}' is not in VULNORAIQ_ALLOWED_TARGET_HOSTS")


def _target_allowlist(cfg: dict[str, Any], profile: dict[str, Any]) -> set[str]:
    """Collect the host allowlist declared by the safety profile and the target.

    Three places may narrow scope and all of them are honoured:
    ``safety_profile.allowed_hosts``, ``target.allowed_hosts``, and the
    ``target.allowed_host_pattern`` shorthand (``"a.example|*.lab.example"``).
    Declaring an allowlist *is* the operator's explicit scope statement, so a
    matching host does not additionally have to resolve to a private address.
    """
    allowed: set[str] = set()
    for source in (profile.get("allowed_hosts"), cfg.get("allowed_hosts")):
        if isinstance(source, str):
            source = [source]
        for item in source or []:
            text = str(item).strip().lower()
            if text:
                allowed.add(text)
    for item in str(cfg.get("allowed_host_pattern") or "").split("|"):
        text = item.strip().lower()
        if text:
            allowed.add(text)
    return allowed


def _resolved_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve ``host`` to every address it currently maps to.

    A literal address resolves to itself. An empty list means the name could not
    be resolved, which callers must treat as "not provably internal".
    """
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return addresses


def _is_internal_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(address.is_loopback or address.is_private or address.is_link_local)


def validate_url(cfg: dict[str, Any]) -> str:
    """Validate and return the absolute request URL for a target configuration.

    Scope control: unless the target or its safety profile opts into external
    network access, every address the host resolves to must be loopback,
    private, or link-local. Resolving instead of pattern-matching the hostname
    is what lets Docker Lab Mode reach an agent by its container DNS name while
    still refusing a public name that merely *looks* internal (``x.internal``).
    """
    url = urljoin(str(cfg.get("base_url", "")).rstrip("/") + "/", str(cfg.get("endpoint_path", "/")).lstrip("/"))
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid URL: only http(s) targets with host are supported")
    if parsed.username or parsed.password:
        raise ValueError("target URL must not embed credentials; use token_env_var instead")
    _enforce_environment_allowlist(parsed.hostname.lower())
    profile = _load_safety_profile(str(cfg.get("safety_profile", "")))
    allowed_schemes = set(profile.get("allowed_schemes") or [])
    if allowed_schemes and parsed.scheme not in allowed_schemes:
        raise ValueError(f"scheme '{parsed.scheme}' is blocked by safety profile")
    host = parsed.hostname.lower()
    allowed_hosts = _target_allowlist(cfg, profile)
    if allowed_hosts and not any(_host_matches(host, item) for item in allowed_hosts):
        raise ValueError(f"host '{host}' is blocked by the configured target allowlist")
    allow_external = bool(cfg.get("allow_external", False) or profile.get("allow_external_network", False))
    if not allow_external and not allowed_hosts:
        addresses = _resolved_addresses(host)
        if not addresses:
            raise ValueError(
                f"target host '{host}' could not be resolved; external targets are blocked by default"
            )
        if not all(_is_internal_address(address) for address in addresses):
            raise ValueError(
                f"target host '{host}' resolves outside loopback/private networks; "
                "external targets are blocked by default"
            )
    return url


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
    headers.setdefault("Content-Type", "application/json")
    env = cfg.get("token_env_var") or cfg.get("auth_token_env")
    if env:
        token = os.getenv(str(env))
        if not token:
            raise RuntimeError(f"Target token environment variable '{env}' is not set.")
        header = str(cfg.get("auth_header", "Authorization"))
        prefix = str(cfg.get("auth_prefix", "Bearer "))
        headers[header] = prefix + token
    return headers


def _body(cfg: dict[str, Any], prompt: str) -> Any:
    if cfg.get("request_template") is not None:
        return render_template(cfg["request_template"], prompt, cfg)
    if cfg.get("request_body_template") is not None:
        return render_template(cfg["request_body_template"], prompt, cfg)
    typ = cfg.get("type")
    if typ == "chat_completions":
        return {"model": cfg.get("model", "local-model"), "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    if typ == "ollama_generate":
        return {"model": cfg.get("model", "llama3"), "prompt": prompt, "stream": False}
    if typ in {"rag_query"}:
        return {"query": prompt, "include_context": True}
    if typ in {"webhook_json", "agent_tool_loop"}:
        return {"input": prompt, "metadata": {"assessment_client": cfg.get("name")}}
    return {"prompt": prompt, "input": prompt}


def _default_response_path(typ: str) -> str | None:
    return {"chat_completions": "choices.0.message.content", "ollama_generate": "response", "rag_query": "answer"}.get(typ)


def invoke_target(name: str, cfg: dict[str, Any], prompt: str) -> AdapterResult:
    start = time.monotonic()
    try:
        url = validate_url(cfg)
        rps = float((cfg.get("rate_limit") or {}).get("requests_per_second", 0) or 0)
        if rps > 0:
            time.sleep(min(1 / rps, 2.0))
        body = _body(cfg, prompt)
        headers = _headers(cfg)
        attempts = int((cfg.get("retry") or {}).get("attempts", 1) or 1)
        method = str(cfg.get("method", "POST")).upper()
        response = None
        for attempt in range(max(1, attempts)):
            try:
                response = requests.request(method, url, json=body if method != "GET" else None, params=body if method == "GET" else None, headers=headers, timeout=float(cfg.get("timeout", cfg.get("timeout_seconds", _load_safety_profile(str(cfg.get("safety_profile", ""))).get("request_timeout_seconds", 30)))))
                break
            except requests.RequestException:
                if attempt >= attempts - 1:
                    raise
                time.sleep(float((cfg.get("retry") or {}).get("backoff_seconds", 0.2)))
        assert response is not None
        text = response.text[: int(cfg.get("max_response_bytes", _load_safety_profile(str(cfg.get("safety_profile", ""))).get("max_response_body_bytes", 200000)))]
        data: Any
        try:
            data = response.json()
        except ValueError:
            data = text
        answer_value = get_path(data, (cfg.get("response_extraction_path") or (cfg.get("response_extraction") or {}).get("path")) or _default_response_path(str(cfg.get("type"))))
        answer = answer_value if isinstance(answer_value, str) else json.dumps(answer_value, default=str)
        return AdapterResult(
            ok=200 <= response.status_code < 300,
            answer=answer,
            status_code=response.status_code,
            request={"method": method, "url": url, "headers": redact(headers), "body": redact(body)},
            response={"headers": redact(dict(response.headers)), "body": redact(data)},
            tool_calls=get_path(data, cfg.get("tool_calls_path")) if cfg.get("tool_calls_path") else [],
            retrieval_context=get_path(data, cfg.get("retrieval_context_path")) if cfg.get("retrieval_context_path") else None,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=None if 200 <= response.status_code < 300 else {"type": "http_error", "message": f"HTTP {response.status_code}"},
        )
    except Exception as exc:
        return AdapterResult(ok=False, error={"type": exc.__class__.__name__, "message": redact(str(exc))}, duration_ms=int((time.monotonic() - start) * 1000))


def connectivity_check(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = normalize_target_config(name, cfg)
    prompt = str(cfg.get("health_prompt", "Health check: reply with OK."))
    result = invoke_target(name, cfg, prompt)
    return {"target_id": name, "ready": result.ok and bool(result.answer), "normalized_response": result.answer[:500], "status_code": result.status_code, "error": result.error, "request": result.request, "response_preview": redact(result.response.get("body")) if result.response else None}

def validate_real_environment_config(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    cfg = normalize_target_config(name, raw)
    if not cfg.get("explicit_authorisation") and not cfg.get("authorised"):
        raise ValueError("real-environment targets require explicit_authorisation: true")
    if cfg.get("dry_run", True) is not True and not cfg.get("allow_live_requests"):
        raise ValueError("dry-run is the default; set allow_live_requests only for approved internal validation")
    validate_url(cfg)
    if not _target_allowlist(cfg, _load_safety_profile(str(cfg.get("safety_profile", "")))):
        raise ValueError("target allow-list or allowed_host_pattern is required")
    if not cfg.get("rate_limit"):
        raise ValueError("rate_limit is required")
    for key in ("api_key", "token", "password", "authorization"):
        if key in {str(k).lower() for k in cfg}:
            raise ValueError("credentials must be referenced through environment variables, not inline values")
    return cfg
