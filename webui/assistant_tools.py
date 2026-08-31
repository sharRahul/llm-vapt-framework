"""Safe, minimal tool surface for the VulnoraIQ assistant.

The assistant is a small helper agent, not an autonomous operator, so its tools
are deliberately narrow and guarded:

- :func:`web_fetch` performs a single HTTP(S) GET, blocks private/loopback/link
  -local targets (SSRF guard), caps the response size, and returns readable text.
  This is how the assistant can "look something up" when it does not know an
  answer from its bundled knowledge.
- :func:`read_text_file` reads a UTF-8 text file, but from an allowlisted
  root (the repository docs by default), so the model cannot exfiltrate arbitrary
  host files.
- :func:`cve_lookup` looks up public CVE records (NVD + OSV) for a finding,
  returning structured CVE IDs, CVSS scores, and summaries. It is SSRF-guarded
  and offline-safe: network failures return an empty result, not an error.

All return short, structured strings suitable for injecting back into a prompt.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[1]
_MAX_FETCH_BYTES = int(os.getenv("VULNORAIQ_ASSISTANT_FETCH_MAX_BYTES", str(200_000)))
_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]*\n[ \t]*")


def _read_root() -> Path:
    configured = os.getenv("VULNORAIQ_ASSISTANT_READ_ROOT", "").strip()
    return Path(configured) if configured else (_ROOT / "docs")


def _host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = str(info[4][0])
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def web_fetch(url: str, *, timeout: float = 15.0) -> str:
    """Fetch a public URL and return readable text (SSRF-guarded, size-capped)."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return "web_fetch error: only http/https URLs are allowed"
    if not parsed.hostname:
        return "web_fetch error: missing host"
    if not _host_is_public(parsed.hostname):
        return "web_fetch error: refusing to fetch a private, loopback, or reserved address"
    request = urllib.request.Request(url, headers={"User-Agent": "VulnoraIQ-Assistant/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read(_MAX_FETCH_BYTES + 1)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:  # network failures are reported, not raised
        return f"web_fetch error: {exc}"
    truncated = len(raw) > _MAX_FETCH_BYTES
    text = raw[:_MAX_FETCH_BYTES].decode(charset, errors="replace")
    text = _TAG_RE.sub(" ", text)
    text = _HTML_RE.sub(" ", text)
    text = _WS_RE.sub("\n", text).strip()
    if truncated:
        text += "\n…[truncated]"
    return text[:_MAX_FETCH_BYTES]


def read_text_file(relative_path: str) -> str:
    """Read a UTF-8 text file from inside the allowlisted read root."""
    root = _read_root().resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents and candidate != root:
        return "read error: path is outside the allowed documentation root"
    if not candidate.is_file():
        return f"read error: no such file: {relative_path}"
    try:
        return candidate.read_text(encoding="utf-8", errors="replace")[:_MAX_FETCH_BYTES]
    except OSError as exc:
        return f"read error: {exc}"


_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_CVE_ID_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)

# Authoritative public sources Nora may consult when an answer is not in the
# bundled knowledge. ``web_fetch`` will fetch any public URL, but these are the
# canonical references for security facts and should be preferred/cited.
AUTHORITATIVE_SOURCES = {
    "nvd": "https://nvd.nist.gov/vuln/detail/{id}",          # CVE / CVSS
    "cve": "https://www.cve.org/CVERecord?id={id}",          # CVE record
    "cvss": "https://www.first.org/cvss/",                   # CVSS spec
    "owasp_llm": "https://genai.owasp.org/llm-top-10/",      # OWASP LLM Top 10
    "owasp_agentic": "https://genai.owasp.org/initiatives/#agenticinitiative",
    "owasp_cheatsheets": "https://cheatsheetseries.owasp.org/",
    "cwe": "https://cwe.mitre.org/data/definitions/{id}.html",
}


def find_cve_ids(text: str) -> list[str]:
    """Return de-duplicated, upper-cased CVE identifiers mentioned in ``text``."""
    seen: list[str] = []
    for m in _CVE_ID_RE.findall(text or ""):
        cid = m.upper()
        if cid not in seen:
            seen.append(cid)
    return seen


def cve_reference_lookup(text: str, *, limit: int = 4) -> str:
    """Fetch authoritative NVD records for CVE IDs mentioned in free text.

    This is how Nora answers "what is the CVSS for CVE-xxxx" without guessing:
    it fetches the real record from NVD. Offline/unknown ids are reported, never
    fabricated. Returns a prompt-injectable block, or "" when no CVE is present.
    """
    ids = find_cve_ids(text)[:limit]
    if not ids:
        return ""
    try:
        from integrations.cve_lookup import lookup_by_id
    except Exception:
        return ""
    lines: list[str] = []
    for cid in ids:
        rec = lookup_by_id(cid)
        if rec:
            lines.append(
                f"- {rec['id']} (NVD) severity={rec.get('severity') or '?'} "
                f"summary={(rec.get('summary') or '')[:200]} url={rec.get('url', '')}"
            )
        else:
            lines.append(f"- {cid}: no authoritative NVD record retrieved (offline or unknown id).")
    return "Authoritative CVE reference (NVD):\n" + "\n".join(lines)

_DUMMY_FINDING_KEYS = {"package", "ecosystem", "title", "category", "owasp", "cwe", "affected_component"}


def extract_url(text: str) -> str | None:
    match = _URL_RE.search(text or "")
    return match.group(0) if match else None


def cve_lookup(finding: dict[str, object], *, timeout: float = 15.0) -> str:
    """Look up public CVE/advisory records for a finding (NVD + OSV).

    Returns a formatted block safe to inject into a prompt, or an empty string
    when offline or no finding keys are present.
    """
    if not any(k in finding for k in _DUMMY_FINDING_KEYS):
        return ""
    try:
        from integrations.cve_lookup import lookup_for_finding

        result = lookup_for_finding(finding, limit=4)
    except Exception:
        return ""
    if not result.get("online"):
        return ""
    lines: list[str] = []
    for m in result.get("matches", []):
        lines.append(
            f"- {m.get('id', '?')} ({m.get('source', '?')}) "
            f"severity={m.get('severity', '?')} "
            f"summary={m.get('summary', '')[:200]}"
        )
    if lines:
        if result.get("candidate_novel"):
            lines.append("\nNo matching public CVE found — candidate novel issue (human verification required).")
        return "CVE lookup:\n" + "\n".join(lines)
    return ""
