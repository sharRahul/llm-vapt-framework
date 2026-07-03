# mypy: ignore-errors
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from webui.agent_host import _run_docker

DEFAULT_AGENT_NETWORK = os.getenv("VULNORAIQ_AGENT_NETWORK", "vulnoraiq_vulnoraiq-lab")
AGENT_LAB_ROOT = Path(os.getenv("VULNORAIQ_AGENT_LAB_ROOT", "/data/agent_lab"))
MANAGED_PROJECTS_ROOT = Path(os.getenv("VULNORAIQ_AGENT_LAB_PROJECTS_ROOT", str(AGENT_LAB_ROOT / "projects")))
DEPLOYMENTS_PATH = Path(os.getenv("VULNORAIQ_AGENT_LAB_DEPLOYMENTS", str(AGENT_LAB_ROOT / "deployments.yaml")))
MOUNTED_PROJECTS_ROOT = Path(os.getenv("VULNORAIQ_PROJECTS_ROOT", "/app/projects"))
MAX_IMPORT_BYTES = int(os.getenv("VULNORAIQ_AGENT_LAB_MAX_IMPORT_BYTES", str(50 * 1024 * 1024)))
MAX_IMPORT_FILES = int(os.getenv("VULNORAIQ_AGENT_LAB_MAX_IMPORT_FILES", "2000"))
ALLOWED_GIT_HOSTS = {
    host.strip().lower()
    for host in os.getenv("VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS", "github.com,gitlab.com,bitbucket.org").split(",")
    if host.strip()
}

PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,80}$")
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{1,120}$")
ENDPOINT_RE = re.compile(r"^/[A-Za-z0-9_./{}:-]*$")
SECRET_RE = re.compile(r"(api[_-]?key|token|secret|password|bearer|credential)", re.I)

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
DEPLOYMENT_MODES = {"container", "external", "hybrid"}
HEALTH_CHECK_TIMEOUT = int(os.getenv("VULNORAIQ_AGENT_LAB_HEALTH_TIMEOUT", "30"))


@dataclass
class ImportResult:
    project_id: str
    source_type: str
    path: str
    files: int
    bytes: int


@dataclass
class DeploymentResult:
    deployment_id: str
    project_id: str
    container_name: str
    image_tag: str
    container_id: str
    status: str
    gpu: dict[str, Any]
    provider: dict[str, Any]
    target_ids: list[str]
    ports: list[int]
    endpoints: list[dict[str, Any]]
    created_at: float
    deployment_mode: str = "container"
    container_port: int | None = None
    host_port: int | None = None
    base_url: str = ""
    health_status: str = "unknown"
    endpoint_contract: dict[str, Any] = field(default_factory=dict)
    updated_at: float = 0.0


def _ensure_roots() -> None:
    for path in (AGENT_LAB_ROOT, MANAGED_PROJECTS_ROOT, DEPLOYMENTS_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)


def normalise_project_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("project id cannot be empty")
    if any(sep in raw for sep in ("/", "\\")) or ".." in raw:
        raise ValueError("project id must not contain path separators or traversal segments")
    candidate = raw.replace(" ", "-")
    candidate = re.sub(r"[^a-zA-Z0-9_.-]+", "-", candidate).strip(".-_")
    candidate = candidate[:80]
    if not candidate or not PROJECT_ID_RE.match(candidate):
        raise ValueError("project id must be 2-80 chars and contain only letters, numbers, dots, hyphens, or underscores")
    blocked = {"demo", "mock", "fake", "fixture"}
    if any(word in candidate.lower() for word in blocked):
        raise ValueError("project id cannot contain demo/mock/fake/fixture in normal Agent Lab runtime")
    return candidate


def _safe_child(root: Path, *parts: str) -> Path:
    root = root.resolve()
    target = root.joinpath(*parts).resolve()
    if target != root and root not in target.parents:
        raise ValueError("path escapes Agent Lab project root")
    return target


def _run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 240) -> tuple[str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"command failed: {' '.join(cmd)}").strip())
    return proc.stdout.strip(), proc.stderr.strip()


def _validate_git_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("only http(s) git URLs are supported")
    if parsed.username or parsed.password:
        raise ValueError("git URLs must not embed credentials")
    host = (parsed.hostname or "").lower()
    if ALLOWED_GIT_HOSTS and host not in ALLOWED_GIT_HOSTS:
        raise ValueError(f"git host '{host}' is not allowed; configure VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS to permit it")
    if not parsed.path or parsed.path == "/":
        raise ValueError("git URL must include a repository path")
    return url.strip()


def import_git_project(url: str, project_id: str | None = None, branch: str | None = None) -> ImportResult:
    _ensure_roots()
    git_url = _validate_git_url(url)
    repo_name = Path(urlparse(git_url).path.rstrip("/")).name.removesuffix(".git")
    pid = normalise_project_id(project_id or repo_name)
    dest = _safe_child(MANAGED_PROJECTS_ROOT, pid)
    if dest.exists():
        raise ValueError(f"project '{pid}' already exists; remove it first or choose a different id")
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["--branch", branch.strip(), "--single-branch"]
    cmd += [git_url, str(dest)]
    _run_command(cmd, timeout=300)
    shutil.rmtree(dest / ".git", ignore_errors=True)
    files, total = _project_size(dest)
    if total > MAX_IMPORT_BYTES or files > MAX_IMPORT_FILES:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError("imported repository exceeds Agent Lab size limits")
    return ImportResult(pid, "git", str(dest), files, total)


def import_archive_project(archive_base64: str, project_id: str) -> ImportResult:
    _ensure_roots()
    pid = normalise_project_id(project_id)
    raw = base64.b64decode(archive_base64, validate=True)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("archive exceeds Agent Lab size limit")
    dest = _safe_child(MANAGED_PROJECTS_ROOT, pid)
    if dest.exists():
        raise ValueError(f"project '{pid}' already exists; remove it first or choose a different id")
    tmp_zip = AGENT_LAB_ROOT / f".{pid}.zip"
    tmp_zip.write_bytes(raw)
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            if len(members) > MAX_IMPORT_FILES:
                raise ValueError("archive contains too many files")
            total = sum(m.file_size for m in members)
            if total > MAX_IMPORT_BYTES:
                raise ValueError("archive uncompressed size exceeds Agent Lab size limit")
            dest.mkdir(parents=True, exist_ok=False)
            for member in zf.infolist():
                member_name = member.filename.replace("\\", "/")
                if member_name.startswith("/") or ".." in Path(member_name).parts:
                    raise ValueError(f"unsafe archive path: {member.filename}")
                if member.is_dir():
                    continue
                out = _safe_child(dest, member_name)
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, out.open("wb") as fh:
                    shutil.copyfileobj(src, fh)
        _collapse_single_top_level_directory(dest)
        files, total = _project_size(dest)
        return ImportResult(pid, "archive", str(dest), files, total)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    finally:
        tmp_zip.unlink(missing_ok=True)


def _collapse_single_top_level_directory(dest: Path) -> None:
    entries = [p for p in dest.iterdir() if p.name not in {"__MACOSX", ".DS_Store"}]
    if len(entries) != 1 or not entries[0].is_dir():
        return
    nested = entries[0]
    tmp = dest.with_name(dest.name + "-tmp-collapse")
    nested.rename(tmp)
    shutil.rmtree(dest)
    tmp.rename(dest)


def delete_project(project_id: str) -> bool:
    pid = normalise_project_id(project_id)
    path = _safe_child(MANAGED_PROJECTS_ROOT, pid)
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True


def _project_size(path: Path) -> tuple[int, int]:
    count = 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return count, total


def _project_roots() -> list[tuple[str, Path, bool]]:
    return [("managed", MANAGED_PROJECTS_ROOT, True), ("mounted", MOUNTED_PROJECTS_ROOT, False)]


def _project_path(project_id: str) -> tuple[Path, str, bool]:
    pid = normalise_project_id(project_id)
    for source, root, writable in _project_roots():
        candidate = _safe_child(root, pid)
        if candidate.exists() and candidate.is_dir():
            return candidate, source, writable
    raise FileNotFoundError(f"project '{pid}' not found")


def list_agent_projects() -> list[dict[str, Any]]:
    _ensure_roots()
    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, root, writable in _project_roots():
        if not root.exists():
            continue
        for item in sorted(p for p in root.iterdir() if p.is_dir()):
            try:
                pid = normalise_project_id(item.name)
            except ValueError:
                continue
            if pid in seen:
                continue
            seen.add(pid)
            info = analyze_agent_project(pid)
            info["source"] = source
            info["writable"] = writable
            projects.append(info)
    return projects


def analyze_agent_project(project_id: str) -> dict[str, Any]:
    path, source, writable = _project_path(project_id)
    files, total = _project_size(path)
    text = _read_representative_text(path)
    framework = _detect_framework(path, text)
    ports = _detect_ports(path, text)
    endpoints = _detect_endpoints(text)
    env_vars = _detect_env_vars(text)
    readme = _read_readme(path)
    return {
        "id": path.name,
        "name": path.name,
        "source": source,
        "writable": writable,
        "path": str(path),
        "framework": framework,
        "ports": ports or [8000],
        "endpoints": endpoints,
        # The authoritative inference-endpoint choice, so callers (e.g. the WebUI
        # deploy preview) display the same route the deploy path will register
        # instead of re-implementing the ranking and drifting from it.
        "selected_endpoint": select_inference_endpoint(endpoints),
        "env_vars": env_vars,
        "has_dockerfile": (path / "Dockerfile").exists(),
        "has_requirements": (path / "requirements.txt").exists(),
        "has_pyproject": (path / "pyproject.toml").exists(),
        "has_package_json": (path / "package.json").exists(),
        "readme": readme,
        "file_count": files,
        "size_bytes": total,
        "errors": [],
    }


def _read_representative_text(path: Path, limit: int = 750_000) -> str:
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


def _detect_framework(path: Path, text: str) -> str | None:
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


def _detect_ports(path: Path, text: str) -> list[int]:
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


def _detect_endpoints(text: str) -> list[dict[str, Any]]:
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


def _detect_env_vars(text: str) -> list[dict[str, Any]]:
    envs: dict[str, dict[str, Any]] = {}
    for pattern in ENV_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1)
            if not ENV_KEY_RE.match(name):
                continue
            default = match.group(2) if len(match.groups()) > 1 else ""
            envs[name] = {"name": name, "required": not bool(default), "suggested": "", "secret": bool(SECRET_RE.search(name))}
    return sorted(envs.values(), key=lambda item: item["name"])


def _read_readme(path: Path) -> str:
    for name in ("README.md", "README.rst", "readme.md"):
        readme = path / name
        if readme.exists():
            return readme.read_text(encoding="utf-8", errors="ignore")[:4000]
    return ""


def provider_presets() -> dict[str, dict[str, Any]]:
    return {
        "ollama": {
            "display_name": "Ollama local/OpenAI-compatible",
            "requires_api_key": False,
            "default_base_url": os.getenv("VULNORAIQ_OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"),
            "default_model": os.getenv("VULNORAIQ_OLLAMA_MODEL", ""),
            "env": ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OLLAMA_HOST", "MODEL"],
        },
        "lmstudio": {
            "display_name": "LM Studio local/OpenAI-compatible",
            "requires_api_key": False,
            "default_base_url": os.getenv("VULNORAIQ_LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"),
            "default_model": os.getenv("VULNORAIQ_LMSTUDIO_MODEL", ""),
            "env": ["OPENAI_BASE_URL", "OPENAI_API_BASE", "MODEL"],
        },
        "openrouter": {
            "display_name": "OpenRouter cloud",
            "requires_api_key": True,
            "default_base_url": "https://openrouter.ai/api/v1",
            "default_model": os.getenv("VULNORAIQ_OPENROUTER_MODEL", ""),
            "env": ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "MODEL"],
        },
        "openai_compatible": {
            "display_name": "Custom OpenAI-compatible endpoint",
            "requires_api_key": False,
            "default_base_url": "",
            "default_model": "",
            "env": ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_API_KEY", "MODEL"],
        },
        "custom_env": {
            "display_name": "Custom environment only",
            "requires_api_key": False,
            "default_base_url": "",
            "default_model": "",
            "env": [],
        },
    }


def _redact_provider(provider: dict[str, Any]) -> dict[str, Any]:
    safe = dict(provider)
    if safe.get("api_key"):
        safe["api_key"] = "***redacted***"
    return safe


def _provider_env(provider: dict[str, Any]) -> dict[str, str]:
    kind = str(provider.get("kind") or "custom_env")
    base_url = str(provider.get("base_url") or provider_presets().get(kind, {}).get("default_base_url") or "").strip()
    model = str(provider.get("model") or provider_presets().get(kind, {}).get("default_model") or "").strip()
    api_key = str(provider.get("api_key") or "").strip()
    env: dict[str, str] = {}
    if base_url:
        env["OPENAI_BASE_URL"] = base_url
        env["OPENAI_API_BASE"] = base_url
        if kind == "ollama":
            env["OLLAMA_HOST"] = base_url.removesuffix("/v1")
    if model:
        env["MODEL"] = model
        env["OPENAI_MODEL"] = model
        env["VULNORAIQ_LLM_MODEL"] = model
    if api_key:
        env["OPENAI_API_KEY"] = api_key
        if kind == "openrouter":
            env["OPENROUTER_API_KEY"] = api_key
    env["VULNORAIQ_LLM_PROVIDER"] = kind
    return env


def _validate_env_map(env: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in env.items():
        if not ENV_KEY_RE.match(str(key)):
            raise ValueError(f"invalid environment variable name: {key}")
        if value is None:
            continue
        clean[str(key)] = str(value)
    return clean


def generate_dockerfile_for_project(project_id: str) -> str | None:
    path, _, _ = _project_path(project_id)
    framework = analyze_agent_project(project_id).get("framework")
    if (path / "Dockerfile").exists():
        return (path / "Dockerfile").read_text(encoding="utf-8", errors="ignore")
    if framework in {"fastapi", "flask", "django", "gradio", "streamlit", "aiohttp", "python"}:
        install = "RUN pip install --no-cache-dir -r requirements.txt" if (path / "requirements.txt").exists() else "RUN pip install --no-cache-dir fastapi uvicorn requests"
        command = _python_default_command(framework)
        return f"""FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY . /app
{install}
EXPOSE 8000
CMD {json.dumps(command)}
"""
    if framework in {"express", "nextjs", "node"}:
        command = ["npm", "start"]
        return f"""FROM node:22-slim
ENV NODE_ENV=production PORT=8000
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY . /app
EXPOSE 8000
CMD {json.dumps(command)}
"""
    return None


def _python_default_command(framework: str | None) -> list[str]:
    if framework == "streamlit":
        return ["sh", "-c", "streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT:-8000}"]
    if framework == "gradio":
        return ["python", "app.py"]
    if framework == "flask":
        return ["sh", "-c", "flask run --host 0.0.0.0 --port ${PORT:-8000}"]
    return ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]


def _running_in_container() -> bool:
    """True when VulnoraIQ itself runs inside a container (Docker Lab Mode).

    In that mode the scanner shares the agent Docker network and must reach the
    agent by its container DNS name. On the host (Desktop Mode) it must use the
    published ``127.0.0.1:<host_port>`` instead.
    """
    run_mode = os.getenv("VULNORAIQ_RUN_MODE", "").strip().lower()
    if run_mode in {"desktop", "native"}:
        return False
    if os.getenv("VULNORAIQ_IN_CONTAINER"):
        return True
    return Path("/.dockerenv").exists()


def _port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    # Do NOT set SO_REUSEADDR here: on Windows it lets this probe bind a port
    # that already has a listening socket (both sockets sharing via the flag),
    # which would falsely report an occupied port as free. A strict bind fails
    # with an OSError when the port is genuinely in use on every platform.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _free_host_port(preferred: int | None = None, host: str = "127.0.0.1") -> int:
    """Return a bindable host port, preferring ``preferred`` when it is free.

    Falls back to an OS-assigned ephemeral port so a busy host port (a real
    failure hit during manual AIRA testing: host ``5000`` was occupied) never
    blocks the deployment.
    """
    if preferred and 1 <= int(preferred) <= 65535 and _port_is_free(int(preferred), host):
        return int(preferred)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _http_responds(base_url: str, timeout: float = 2.0) -> bool:
    """True if the URL returns *any* HTTP response (including 4xx/5xx).

    A bare TCP connect is not enough on Docker Desktop: its host-side port proxy
    accepts connections on a published port even when nothing inside the
    container is listening (e.g. a crash-looping app), so the connection appears
    open while no application is serving. An actual HTTP round-trip only
    completes when an app answers, so it distinguishes a live app from an empty
    published port whose backend is dead.
    """
    parsed = urlparse(base_url)
    if not parsed.hostname or not parsed.port:
        return False
    req = urllib.request.Request(base_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310 - loopback health probe
            return True
    except urllib.error.HTTPError:
        # 4xx/5xx still proves an application answered.
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _container_run_state(container_name: str) -> tuple[str, bool]:
    """Return ``(status, restarting)`` for a container, ("", False) if unknown.

    A crash-looping container (bad entrypoint, import error) reports
    ``restarting=True`` or cycles through ``exited`` — either means the app is
    not actually serving, even if a published host port looks connectable.
    """
    try:
        out, _ = _run_docker(
            ["inspect", "-f", "{{.State.Status}}|{{.State.Restarting}}", container_name]
        )
    except RuntimeError:
        return "", False
    raw = (out or "").strip().splitlines()[0] if out else ""
    status, _, restarting = raw.partition("|")
    return status.strip(), restarting.strip().lower() == "true"


def _wait_for_healthy(base_url: str, container_name: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """Poll until the container serves HTTP while genuinely running.

    Registration is gated on this so a container that never boots its app (or
    crash-loops) is never turned into a broken scan target. Requires both a real
    HTTP response and a ``running``/not-restarting container state.
    """
    deadline = time.monotonic() + max(1, timeout)
    while time.monotonic() < deadline:
        status, restarting = _container_run_state(container_name)
        if status == "exited":
            # The app process died and there is no restart pending: fail fast.
            return False
        if status == "running" and not restarting and _http_responds(base_url):
            return True
        time.sleep(0.5)
    return False


def _resolve_endpoint_contract(info: dict[str, Any], target_cfg: dict[str, Any], target_type: str) -> dict[str, Any]:
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


def deploy_agent_project(project_id: str, payload: dict[str, Any], save_target_fn) -> DeploymentResult:
    deployment_mode = str(payload.get("deployment_mode") or "container").strip().lower()
    if deployment_mode not in DEPLOYMENT_MODES:
        raise ValueError(f"deployment_mode must be one of {sorted(DEPLOYMENT_MODES)}")
    if deployment_mode == "external":
        return _deploy_external_endpoint(project_id, payload, save_target_fn)

    path, source, writable = _project_path(project_id)
    info = analyze_agent_project(project_id)
    provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    if deployment_mode == "hybrid":
        if not payload.get("authorization_acknowledged"):
            raise ValueError("hybrid deployments require authorization_acknowledged=true for the external model dependency")
        if not (provider.get("base_url") or provider.get("kind")):
            raise ValueError("hybrid mode requires external model provider configuration (base_url or kind)")
    runtime_env = _validate_env_map(payload.get("env") or {})
    runtime_env.update(_provider_env(provider))
    gpu = payload.get("gpu") if isinstance(payload.get("gpu"), dict) else {}
    gpu_mode = str(gpu.get("mode") or "cpu")
    ports = _normalise_ports(payload.get("ports") or info.get("ports") or [8000])
    target_cfg = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    target_type = str(target_cfg.get("type") or "http_json")
    target_profile = str(target_cfg.get("safety_profile") or "local_lab_safe")
    contract = _resolve_endpoint_contract(info, target_cfg, target_type)
    pid = normalise_project_id(project_id)
    image_tag = f"vulnoraiq-agent-lab-{pid}".lower().replace("_", "-")
    container_name = f"vulnoraiq-agent-lab-{pid}".lower().replace("_", "-")

    df_path = path / "Dockerfile"
    generated_dockerfile = False
    if not df_path.exists():
        if not writable:
            raise ValueError("mounted project has no Dockerfile; copy/import it into the managed Agent Lab first or add a Dockerfile")
        dockerfile = generate_dockerfile_for_project(project_id)
        if not dockerfile:
            raise ValueError("cannot generate Dockerfile for this project; add a Dockerfile")
        df_path.write_text(dockerfile, encoding="utf-8")
        generated_dockerfile = True

    try:
        _run_docker(["build", "-t", image_tag, str(path)])
    except RuntimeError as exc:
        if generated_dockerfile:
            df_path.unlink(missing_ok=True)
        raise RuntimeError(f"build failed: {exc}") from exc

    try:
        _run_docker(["rm", "-f", container_name])
    except RuntimeError:
        pass

    env_flags: list[str] = []
    for key, value in sorted(runtime_env.items()):
        if value:
            env_flags += ["-e", f"{key}={value}"]
    container_port = ports[0]
    publish_ports = bool(payload.get("publish_ports", True))
    in_container = _running_in_container()
    port_flags: list[str] = []
    host_port = container_port
    if publish_ports:
        # Pick a free host port for the primary container port (the host port
        # need not equal the container port) so a busy host port cannot break
        # the deployment. Additional ports are published on free ports too.
        host_port = _free_host_port(container_port)
        port_flags += ["-p", f"127.0.0.1:{host_port}:{container_port}"]
        for extra in ports[1:]:
            port_flags += ["-p", f"127.0.0.1:{_free_host_port(extra)}:{extra}"]

    run_cmd = [
        "run",
        "-d",
        "--name",
        container_name,
        "--label",
        "vulnoraiq.agent=agent-lab",
        "--label",
        f"vulnoraiq.agent.id={pid}",
        "--network",
        DEFAULT_AGENT_NETWORK,
        "--restart",
        "unless-stopped",
        "--security-opt",
        "no-new-privileges:true",
        "--cap-drop",
        "ALL",
    ]
    if gpu_mode == "all":
        run_cmd += ["--gpus", "all"]
    elif gpu_mode == "device":
        device_ids = str(gpu.get("device_ids") or "").strip()
        if not device_ids:
            raise ValueError("gpu.device_ids is required when gpu.mode=device")
        run_cmd += ["--gpus", f"device={device_ids}"]
    elif gpu_mode != "cpu":
        raise ValueError("gpu.mode must be cpu, all, or device")
    memory = str(payload.get("memory") or "").strip()
    cpus = str(payload.get("cpus") or "").strip()
    if memory:
        run_cmd += ["--memory", memory]
    if cpus:
        run_cmd += ["--cpus", cpus]
    run_cmd += port_flags + env_flags + [image_tag]
    container_id, _ = _run_docker(run_cmd)

    # Reach the container by container DNS in Docker Lab Mode, and by the
    # published loopback host port in Desktop Mode.
    if in_container:
        base_url = f"http://{container_name}:{container_port}"
    else:
        base_url = f"http://127.0.0.1:{host_port}"

    # Health-gate registration: never register a target for a container that
    # never came up. Clean the failed container up rather than leaking it.
    health_status = "healthy"
    if publish_ports or in_container:
        if not _wait_for_healthy(base_url, container_name, HEALTH_CHECK_TIMEOUT):
            logs = _safe_container_logs(container_name)
            try:
                _run_docker(["rm", "-f", container_name])
            except RuntimeError:
                pass
            detail = f" Last container logs:\n{logs}" if logs else ""
            raise RuntimeError(
                f"agent container '{container_name}' did not serve HTTP at {base_url} "
                f"within {HEALTH_CHECK_TIMEOUT}s (it may have failed to start or is crash-looping); "
                f"deployment aborted and container removed.{detail}"
            )
    else:
        health_status = "unpublished"

    target_ids = _register_targets(
        save_target_fn=save_target_fn,
        project_id=pid,
        base_url=base_url,
        target_type=target_type,
        contract=contract,
        safety_profile=target_profile,
    )
    now = time.time()
    result = DeploymentResult(
        deployment_id=f"{pid}-{int(now)}",
        project_id=pid,
        container_name=container_name,
        image_tag=image_tag,
        container_id=container_id,
        status="running",
        gpu={"mode": gpu_mode, "device_ids": gpu.get("device_ids", "")},
        provider=_redact_provider(provider),
        target_ids=target_ids,
        ports=ports,
        endpoints=info.get("endpoints", []),
        created_at=now,
        deployment_mode=deployment_mode,
        container_port=container_port,
        host_port=host_port if publish_ports else None,
        base_url=base_url,
        health_status=health_status,
        endpoint_contract=contract,
        updated_at=now,
    )
    _save_deployment(result)
    return result


def _safe_container_logs(container_name: str, tail: int = 40) -> str:
    try:
        out, err = _run_docker(["logs", "--tail", str(tail), container_name])
    except RuntimeError:
        return ""
    return (out or err or "").strip()[:4000]


def _deploy_external_endpoint(project_id: str, payload: dict[str, Any], save_target_fn) -> DeploymentResult:
    """Register a scan target for an already-running external endpoint.

    No Docker build/run happens: the operator supplies the reachable base URL,
    the target contract, and an explicit authorization acknowledgement.
    """
    if not payload.get("authorization_acknowledged"):
        raise ValueError("external endpoint deployments require authorization_acknowledged=true")
    target_cfg = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    target_type = str(target_cfg.get("type") or "http_json")
    target_profile = str(target_cfg.get("safety_profile") or "local_lab_safe")
    base_url = str(payload.get("base_url") or target_cfg.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("external endpoint mode requires a base_url")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base_url must be an http(s) URL with a host")
    pid = normalise_project_id(project_id)
    info: dict[str, Any] = {"endpoints": []}
    try:
        info = analyze_agent_project(project_id)
    except FileNotFoundError:
        # External endpoints need not have imported source; fall back to
        # whatever contract the operator supplied.
        pass
    contract = _resolve_endpoint_contract(info, target_cfg, target_type)
    target_ids = _register_targets(
        save_target_fn=save_target_fn,
        project_id=pid,
        base_url=base_url,
        target_type=target_type,
        contract=contract,
        safety_profile=target_profile,
    )
    now = time.time()
    result = DeploymentResult(
        deployment_id=f"{pid}-{int(now)}",
        project_id=pid,
        container_name="",
        image_tag="",
        container_id="",
        status="external",
        gpu={"mode": "none", "device_ids": ""},
        provider={},
        target_ids=target_ids,
        ports=[],
        endpoints=info.get("endpoints", []),
        created_at=now,
        deployment_mode="external",
        container_port=None,
        host_port=None,
        base_url=base_url,
        health_status="external",
        endpoint_contract=contract,
        updated_at=now,
    )
    _save_deployment(result)
    return result


def _normalise_ports(values: Any) -> list[int]:
    ports: list[int] = []
    if not isinstance(values, list):
        values = [values]
    for value in values:
        port = int(value)
        if not 1 <= port <= 65535:
            raise ValueError(f"invalid port: {port}")
        if port not in ports:
            ports.append(port)
    return ports or [8000]


def _default_endpoint_path(info: dict[str, Any], target_type: str) -> str:
    if target_type == "chat_completions":
        return "/v1/chat/completions"
    endpoints = info.get("endpoints") or []
    if endpoints:
        return endpoints[0].get("path") or "/"
    return "/"


def _register_targets(save_target_fn, project_id: str, base_url: str, target_type: str, contract: dict[str, Any], safety_profile: str) -> list[str]:
    """Register a scan target whose config matches the agent's real HTTP contract.

    For ``http_json`` the method, endpoint path, request body (keyed by the
    detected user param) and response extraction path all come from the resolved
    ``contract`` rather than being hardcoded, so GET/query and plain-text agents
    (e.g. AIRA's ``GET /get?msg=``) register correctly with no manual edits.
    """
    base_url = base_url.rstrip("/")
    endpoint_path = str(contract.get("path") or "/")
    if not endpoint_path.startswith("/"):
        endpoint_path = "/" + endpoint_path
    if target_type == "chat_completions":
        config = {
            "name": f"Agent Lab {project_id} chat completions",
            "type": "chat_completions",
            "base_url": base_url,
            "endpoint_path": endpoint_path,
            "method": "POST",
            "request_body_template": {
                "model": "{{model}}",
                "messages": [{"role": "user", "content": "{{prompt}}"}],
            },
            "response_extraction_path": "choices.0.message.content",
            "authorisation_required": True,
            "environment": "agent_lab",
            "safety_profile": safety_profile,
        }
    else:
        param_key = str(contract.get("param_key") or "prompt")
        response_shape = str(contract.get("response_shape") or "text")
        response_path = str(contract.get("response_path") or "")
        # Empty extraction path returns the whole body — correct for plain-text
        # responses and a safe fallback for JSON with no detected key.
        response_extraction_path = response_path if (response_shape == "json" and response_path) else ""
        config = {
            "name": f"Agent Lab {project_id} HTTP",
            "type": "http_json",
            "base_url": base_url,
            "endpoint_path": endpoint_path,
            "method": str(contract.get("method") or "POST").upper(),
            "request_body_template": {param_key: "{{prompt}}"},
            "response_extraction_path": response_extraction_path,
            "authorisation_required": True,
            "environment": "agent_lab",
            "safety_profile": safety_profile,
        }
    target_id = _runtime_target_id(project_id, target_type)
    saved = save_target_fn(target_id, config)
    return [saved["target_id"]]


def _runtime_target_id(project_id: str, target_type: str) -> str:
    """Derive a runtime target id that satisfies the target store's id rules.

    Project ids may contain dots and be up to 80 chars (both allowed by
    ``PROJECT_ID_RE``), but the runtime target store requires
    ``^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$``. Map any disallowed character to a
    hyphen and cap the length so a dotted or long project name (e.g.
    ``socket.io``) does not dead-end the deploy with a validation error.
    """
    raw = f"agent-lab-{project_id}-{target_type}".lower()
    safe = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return safe[:81] or "agent-lab-target"


def list_deployments() -> list[dict[str, Any]]:
    if not DEPLOYMENTS_PATH.exists():
        return []
    data = yaml.safe_load(DEPLOYMENTS_PATH.read_text(encoding="utf-8")) or {}
    deployments = data.get("deployments") or []
    return deployments if isinstance(deployments, list) else []


def _save_deployment(result: DeploymentResult) -> None:
    _ensure_roots()
    data = {"deployments": list_deployments()}
    deployments = data.setdefault("deployments", [])
    deployments.insert(0, asdict(result))
    data["deployments"] = deployments[:200]
    DEPLOYMENTS_PATH.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _container_exists(container_name: str) -> bool:
    if not container_name:
        return False
    try:
        out, _ = _run_docker(["ps", "-aq", "--filter", f"name=^{container_name}$"])
    except RuntimeError:
        return False
    return bool(out.strip())


def _drop_deployment_records(container_name: str) -> int:
    deployments = list_deployments()
    remaining = [d for d in deployments if d.get("container_name") != container_name]
    dropped = len(deployments) - len(remaining)
    if dropped:
        _ensure_roots()
        DEPLOYMENTS_PATH.write_text(yaml.safe_dump({"deployments": remaining}, sort_keys=True), encoding="utf-8")
    return dropped


def remove_deployment(identifier: str) -> dict[str, Any]:
    ident = str(identifier or "").strip()
    if not ident:
        raise ValueError("deployment identifier is required")
    # The identifier may be a deployment_id, a project_id, or a container_name.
    # Resolve it against the stored deployment registry to find the real
    # container name rather than assuming the identifier is a project id.
    record = next(
        (
            d
            for d in list_deployments()
            if ident in (d.get("deployment_id"), d.get("project_id"), d.get("container_name"))
        ),
        None,
    )
    if record is not None:
        container_name = str(record.get("container_name") or "")
        project_id = str(record.get("project_id") or "")
        deployment_id = str(record.get("deployment_id") or "")
    else:
        # No registry record (legacy/manual deployment): best-effort fall back
        # to deriving the container name from a project id.
        project_id = normalise_project_id(ident)
        container_name = f"vulnoraiq-agent-lab-{project_id}".lower().replace("_", "-")
        deployment_id = ""

    # Only report success when a matching container actually existed and was
    # removed. ``docker rm -f`` exits 0 for a missing container, so we must not
    # infer removal from its exit code alone.
    existed = _container_exists(container_name)
    if existed:
        _run_docker(["rm", "-f", container_name])
    records_dropped = _drop_deployment_records(container_name) if container_name else 0
    return {
        "deployment_id": deployment_id,
        "project_id": project_id,
        "container_name": container_name,
        "removed": existed,
        "records_removed": records_dropped,
    }
