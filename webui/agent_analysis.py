"""Static analysis of an imported agent project.

Agent Lab has to answer one question before it can deploy anything: *what HTTP
contract does this agent actually expose?* These helpers read the project's own
source to recover its framework, listening port, routes, request/response shape,
and configuration variables, then rank the routes to pick the inference
endpoint. Everything here is pure with respect to module state - it reads the
files it is handed and returns data - which keeps the detection rules testable
without Docker or a running agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PY_FRAMEWORK_PATTERNS = {
    "fastapi": ["FastAPI(", "from fastapi", "import fastapi"],
    "flask": ["Flask(", "from flask", "import flask"],
    "django": ["django", "DJANGO_SETTINGS_MODULE"],
    "gradio": ["gradio", ".launch("],
    "streamlit": ["streamlit"],
    "aiohttp": ["aiohttp"],
}
NODE_FRAMEWORK_PATTERNS = {
    "express": ["express(", "from 'express'", 'from "express"', "require('express')", 'require("express")'],
    "nextjs": ["next", "next.config"],
}
HTTP_ROUTE_PATTERNS = [
    re.compile(r"@app\.(get|post|put|patch)\(['\"]([^'\"]+)['\"]"),
    re.compile(r"@router\.(get|post|put|patch)\(['\"]([^'\"]+)['\"]"),
    re.compile(r"app\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?"),
    re.compile(r"app\.(get|post|put|patch)\(['\"]([^'\"]+)['\"]"),
]
PORT_PATTERNS = [
    re.compile(r"port\s*=\s*int\(os\.getenv\(['\"][A-Z0-9_]*PORT['\"],\s*['\"]?(\d{2,5})"),
    re.compile(r"PORT\s*=\s*(\d{2,5})"),
    re.compile(r"listen\((\d{2,5})"),
    re.compile(r"uvicorn\s+[^\n]*--port\s+(\d{2,5})"),
    # Bare port kwarg on a server-start call, e.g. Flask ``app.run('0.0.0.0',
    # port=5000)`` or ``uvicorn.run(app, port=8000)`` — the run= prefix keeps
    # this from matching unrelated ``port=`` assignments.
    re.compile(r"\.run\([^)]*?\bport\s*=\s*(\d{2,5})"),
]
ENDPOINT_RE = re.compile(r"^/[A-Za-z0-9_./{}:-]*$")
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{1,120}$")
SECRET_RE = re.compile(r"(api[_-]?key|token|secret|password|bearer|credential)", re.I)
ENV_PATTERNS = [
    re.compile(r"os\.getenv\(['\"]([A-Z][A-Z0-9_]{1,120})['\"](?:,\s*['\"]([^'\"]*)['\"])?"),
    re.compile(r"os\.environ\[['\"]([A-Z][A-Z0-9_]{1,120})['\"]\]"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]{1,120})"),
]

# Ordered by preference: the first candidate found in a handler is treated as
# the user-supplied inference parameter (AIRA uses ``msg``; most chat agents use
# ``prompt``/``input``/``query``).
PARAM_KEY_CANDIDATES = ["msg", "message", "prompt", "input", "query", "question", "text", "q"]
USER_PARAM_KEYS = {"msg", "message", "prompt", "input", "query", "question", "text"}
# Path tokens that indicate an inference/chat endpoint worth scanning.
INFERENCE_PATH_TOKENS = {
    "chat", "ask", "get", "query", "predict", "invoke", "completion", "completions",
    "complete", "message", "messages", "msg", "run", "api", "generate", "respond",
    "prompt", "inference", "infer", "v1", "answer", "conversation",
}
# Routes that are never the inference endpoint.
NON_INFERENCE_PATHS = {
    "/", "/health", "/healthz", "/healthcheck", "/ready", "/readyz", "/live",
    "/liveness", "/readiness", "/refresh", "/favicon.ico", "/docs", "/redoc",
    "/openapi.json", "/metrics", "/status", "/ping", "/version", "/robots.txt",
}
NON_INFERENCE_PREFIXES = ("/static", "/assets", "/_", "/.well-known", "/public")
JSON_RESPONSE_SIGNALS = ("jsonify(", "JSONResponse", "JsonResponse", "return json.", "make_response(jsonify")
TEXT_RESPONSE_SIGNALS = ("PlainTextResponse", "return str(", "content_type='text", 'content_type="text', "text/plain")
RESPONSE_KEY_PATTERNS = [
    re.compile(r"jsonify\(\s*\{\s*['\"](\w+)['\"]"),
    re.compile(r"JSONResponse\(\s*(?:content=)?\{\s*['\"](\w+)['\"]"),
    re.compile(r"return\s+\{\s*['\"](\w+)['\"]"),
]
def resolve_endpoint_contract(info: dict[str, Any], target_cfg: dict[str, Any], target_type: str) -> dict[str, Any]:
    """Combine the detected inference endpoint with any explicit UI overrides.

    Explicit ``payload.target`` fields always win so an operator can hand-fix a
    contract the analyzer got wrong.
    """
    selected = select_inference_endpoint(info.get("endpoints") or []) or {}
    contract = {
        "method": str(selected.get("method") or ("POST" if target_type == "chat_completions" else "POST")).upper(),
        "path": str(selected.get("path") or _default_endpoint_path(info, target_type)),
        "param_style": str(selected.get("param_style") or "json"),
        "param_key": str(selected.get("param_key") or "prompt"),
        "response_shape": str(selected.get("response_shape") or "text"),
        "response_path": str(selected.get("response_path") or ""),
    }
    if target_type == "chat_completions":
        contract["path"] = str(target_cfg.get("endpoint_path") or "/v1/chat/completions")
        contract["method"] = "POST"
        return contract
    if target_cfg.get("endpoint_path"):
        contract["path"] = str(target_cfg["endpoint_path"])
    if target_cfg.get("method"):
        contract["method"] = str(target_cfg["method"]).upper()
    if target_cfg.get("param_key"):
        contract["param_key"] = str(target_cfg["param_key"])
    if target_cfg.get("param_style"):
        contract["param_style"] = str(target_cfg["param_style"])
    if "response_extraction_path" in target_cfg:
        response_path = str(target_cfg.get("response_extraction_path") or "")
        contract["response_path"] = response_path
        contract["response_shape"] = "json" if response_path else "text"
    return contract



def _default_endpoint_path(info: dict[str, Any], target_type: str) -> str:
    if target_type == "chat_completions":
        return "/v1/chat/completions"
    endpoints = info.get("endpoints") or []
    if endpoints:
        return endpoints[0].get("path") or "/"
    return "/"


def read_representative_text(path: Path, limit: int = 750_000) -> str:
    chunks: list[str] = []
    total = 0
    suffixes = {".py", ".js", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".toml", ".yaml", ".yml", ".md"}
    for item in sorted(path.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in suffixes:
            continue
        if any(part in {"node_modules", ".venv", "venv", "dist", "build", "__pycache__"} for part in item.parts):
            continue
        try:
            data = item.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        chunks.append(f"\n# FILE: {item.relative_to(path)}\n{data[:50_000]}")
        total += len(chunks[-1])
        if total >= limit:
            break
    return "\n".join(chunks)


def detect_framework(path: Path, text: str) -> str | None:
    lowered = text.lower()
    for framework, markers in PY_FRAMEWORK_PATTERNS.items():
        if any(marker.lower() in lowered for marker in markers):
            return framework
    for framework, markers in NODE_FRAMEWORK_PATTERNS.items():
        if any(marker.lower() in lowered for marker in markers):
            return framework
    if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
        return "python"
    if (path / "package.json").exists():
        return "node"
    return None


def detect_ports(path: Path, text: str) -> list[int]:
    found: set[int] = set()
    for pattern in PORT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                port = int(match.group(1))
            except (TypeError, ValueError):
                continue
            if 1 <= port <= 65535:
                found.add(port)
    for env_file in (path / ".env", path / ".env.example"):
        if not env_file.exists():
            continue
        for match in re.finditer(r"PORT\s*=\s*(\d{2,5})", env_file.read_text(encoding="utf-8", errors="ignore")):
            found.add(int(match.group(1)))
    # The Dockerfile is not part of the representative source text, but its
    # EXPOSE directives are the authoritative container ports (AIRA declares
    # EXPOSE 5000 while its Flask app.run also binds 5000).
    dockerfile = path / "Dockerfile"
    if dockerfile.exists():
        for match in re.finditer(r"(?im)^\s*EXPOSE\s+(.+)$", dockerfile.read_text(encoding="utf-8", errors="ignore")):
            for tok in re.findall(r"(\d{2,5})", match.group(1)):
                port = int(tok)
                if 1 <= port <= 65535:
                    found.add(port)
    return sorted(found)


def detect_endpoints(text: str) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pattern in HTTP_ROUTE_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            if len(groups) >= 2 and groups[0] and groups[0].lower() in {"get", "post", "put", "patch"}:
                method = groups[0].upper()
                path = groups[1]
            else:
                path = groups[0]
                methods = (groups[1] or "") if len(groups) > 1 else ""
                method = "POST" if "POST" in methods.upper() else "GET"
            if not path.startswith("/") or not ENDPOINT_RE.match(path):
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            # Inspect the handler body that follows the route decorator to
            # recover the real request/response contract instead of assuming
            # a JSON ``prompt`` body (which breaks GET/query and text agents).
            segment = text[match.end(): match.end() + 1600]
            param_style, param_key = _detect_request_param(segment, text, method)
            response_shape, response_path = _detect_response_contract(segment)
            endpoints.append(
                {
                    "method": method,
                    "path": path,
                    "param_style": param_style,
                    "param_key": param_key,
                    "response_shape": response_shape,
                    "response_path": response_path,
                }
            )
    return endpoints[:30]


def _detect_request_param(segment: str, full_text: str, method: str) -> tuple[str, str]:
    """Return ``(param_style, param_key)`` for a detected endpoint.

    ``param_style`` is ``query`` when the handler reads request query params (or
    the method is GET) and ``json`` otherwise. ``param_key`` is the first known
    user-input key referenced by the handler (falling back to a whole-file scan
    and finally a method-appropriate default).
    """

    def _find(scope: str) -> str | None:
        for candidate in PARAM_KEY_CANDIDATES:
            needles = (
                f'"{candidate}"',
                f"'{candidate}'",
                f'.get("{candidate}"',
                f".get('{candidate}'",
            )
            if any(needle in scope for needle in needles):
                return candidate
        return None

    param_key = _find(segment) or _find(full_text) or ("msg" if method == "GET" else "prompt")
    if method == "GET":
        param_style = "query"
    elif any(sig in segment for sig in ("request.args", "request.query_params", ".query_params", "req.query")):
        param_style = "query"
    else:
        param_style = "json"
    return param_style, param_key


def _detect_response_contract(segment: str) -> tuple[str, str]:
    """Infer ``(response_shape, response_path)`` from a handler body.

    Defaults to ``text`` (safer: the adapter returns the whole body) when the
    shape cannot be determined.
    """
    seg = segment or ""
    if any(sig in seg for sig in JSON_RESPONSE_SIGNALS) or re.search(r"return\s+\{", seg):
        return "json", _detect_response_key(seg)
    if any(sig in seg for sig in TEXT_RESPONSE_SIGNALS):
        return "text", ""
    if re.search(r"return\s+f?['\"]", seg):
        return "text", ""
    return "text", ""


def _detect_response_key(segment: str) -> str:
    for pattern in RESPONSE_KEY_PATTERNS:
        match = pattern.search(segment)
        if match:
            return match.group(1)
    return ""


def _rank_endpoint(endpoint: dict[str, Any]) -> int:
    path = str(endpoint.get("path") or "").lower()
    tokens = {tok for tok in re.split(r"[^a-z0-9]+", path) if tok}
    score = 0
    if tokens & INFERENCE_PATH_TOKENS:
        score += 3
    if str(endpoint.get("param_key") or "") in USER_PARAM_KEYS:
        score += 2
    if str(endpoint.get("method") or "").upper() in {"POST", "PUT"}:
        score += 1
    if str(endpoint.get("response_shape") or "") == "json":
        score += 1
    return score


def select_inference_endpoint(endpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the endpoint most likely to be the agent's inference route.

    Infrastructure routes (``/``, ``/health``, static, docs, …) are dropped
    first; the remainder is ranked by path hints, user-param usage, method, and
    response shape, preserving source order as the tie-breaker.
    """
    if not endpoints:
        return None

    def _is_infra(endpoint: dict[str, Any]) -> bool:
        path = str(endpoint.get("path") or "").lower()
        return path in NON_INFERENCE_PATHS or path.startswith(NON_INFERENCE_PREFIXES)

    candidates = [ep for ep in endpoints if not _is_infra(ep)] or list(endpoints)
    ranked = sorted(enumerate(candidates), key=lambda item: (-_rank_endpoint(item[1]), item[0]))
    return dict(ranked[0][1])


def detect_env_vars(text: str) -> list[dict[str, Any]]:
    envs: dict[str, dict[str, Any]] = {}
    for pattern in ENV_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1)
            if not ENV_KEY_RE.match(name):
                continue
            default = match.group(2) if len(match.groups()) > 1 else ""
            envs[name] = {"name": name, "required": not bool(default), "suggested": "", "secret": bool(SECRET_RE.search(name))}
    return sorted(envs.values(), key=lambda item: item["name"])


def read_readme(path: Path) -> str:
    for name in ("README.md", "README.rst", "readme.md"):
        readme = path / name
        if readme.exists():
            return readme.read_text(encoding="utf-8", errors="ignore")[:4000]
    return ""


