"""Connect VulnoraIQ findings to public vulnerability records (NVD / OSV).

Given a finding, this builds a keyword query and looks it up online against the
NVD (NIST) keyword API and, when the finding names a software package, the OSV
database. It returns any matching CVE/advisory records, or flags the finding as a
*candidate novel issue* when no public record matches — explicitly noting that a
human must verify before calling anything a zero-day.

The lookup is best-effort and online-only: network/timeouts/offline are reported
as ``online: false`` rather than raised, so the WebUI never breaks because the
internet is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_URL = "https://api.osv.dev/v1/query"
_TIMEOUT = float(os.getenv("VULNORAIQ_CVE_TIMEOUT", "12"))
_USER_AGENT = "VulnoraIQ-CVE/1.0"
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#-]{2,}")
_STOP = frozenset(
    "the and for with that this from review finding evidence layer real target assessment "
    "interactions observed component potential context analysis baseline profile".split()
)


def _http_get_json(url: str, params: dict[str, str], timeout: float) -> Any:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_post_json(url: str, body: dict[str, Any], timeout: float) -> Any:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def keywords_from_finding(finding: dict[str, Any], *, max_terms: int = 6) -> str:
    raw = " ".join(
        str(finding.get(key, ""))
        for key in ("title", "category", "owasp", "cwe", "affected_component", "affectedPath")
    )
    seen: list[str] = []
    for match in _WORD_RE.findall(raw):
        term = match.strip(".-+#")
        low = term.lower()
        if low in _STOP or low in {t.lower() for t in seen} or len(term) < 3:
            continue
        seen.append(term)
        if len(seen) >= max_terms:
            break
    return " ".join(seen)


def _nvd_records(payload: Any, limit: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in (payload or {}).get("vulnerabilities", [])[:limit]:
        cve = item.get("cve", {})
        cid = cve.get("id")
        if not cid:
            continue
        descriptions = cve.get("descriptions", [])
        english = next((d.get("value") for d in descriptions if d.get("lang") == "en"), "")
        severity = ""
        metrics = cve.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key)
            if entries:
                data = entries[0].get("cvssData", {})
                severity = f"{data.get('baseScore', '?')} ({data.get('baseSeverity', entries[0].get('baseSeverity', 'n/a'))})"
                break
        records.append(
            {
                "id": cid,
                "source": "NVD",
                "summary": (english or "")[:400],
                "severity": severity,
                "url": f"https://nvd.nist.gov/vuln/detail/{cid}",
                "published": cve.get("published", ""),
            }
        )
    return records


def search_nvd(keywords: str, *, limit: int = 5, timeout: float = _TIMEOUT) -> list[dict[str, Any]]:
    if not keywords.strip():
        return []
    params = {"keywordSearch": keywords, "resultsPerPage": str(max(1, min(limit, 20)))}
    payload = _http_get_json(NVD_URL, params, timeout)
    return _nvd_records(payload, limit)


def lookup_by_id(cve_id: str, *, timeout: float = _TIMEOUT) -> dict[str, Any] | None:
    """Fetch a single authoritative NVD record by CVE identifier.

    Returns the structured record (id, CVSS severity, summary, url) or ``None``
    when the id is unknown, offline, or the API errors.
    """
    cve_id = cve_id.strip().upper()
    if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve_id):
        return None
    try:
        payload = _http_get_json(NVD_URL, {"cveId": cve_id}, timeout)
    except Exception:
        return None
    records = _nvd_records(payload, limit=1)
    return records[0] if records else None


def search_osv(package: str, *, ecosystem: str | None = None, timeout: float = _TIMEOUT) -> list[dict[str, Any]]:
    if not package.strip():
        return []
    body: dict[str, Any] = {"package": {"name": package}}
    if ecosystem:
        body["package"]["ecosystem"] = ecosystem
    payload = _http_post_json(OSV_URL, body, timeout)
    records: list[dict[str, Any]] = []
    for vuln in (payload or {}).get("vulns", []):
        vid = vuln.get("id")
        if not vid:
            continue
        records.append(
            {
                "id": vid,
                "source": "OSV",
                "summary": (vuln.get("summary") or vuln.get("details") or "")[:400],
                "severity": (vuln.get("database_specific", {}) or {}).get("severity", ""),
                "url": f"https://osv.dev/vulnerability/{vid}",
                "published": vuln.get("published", ""),
            }
        )
    return records


def lookup_for_finding(finding: dict[str, Any], *, limit: int = 5) -> dict[str, Any]:
    """Look up public CVE/advisory records related to a finding."""
    keywords = keywords_from_finding(finding)
    package = str(finding.get("package") or "").strip()
    ecosystem = str(finding.get("ecosystem") or "").strip() or None
    sources: list[str] = []
    matches: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        nvd = search_nvd(keywords, limit=limit)
        sources.append("NVD")
        matches.extend(nvd)
    except Exception as exc:  # offline / rate-limited / API change -> stay graceful
        errors.append(f"NVD: {exc}")

    if package:
        try:
            osv = search_osv(package, ecosystem=ecosystem)
            sources.append("OSV")
            matches.extend(osv)
        except Exception as exc:
            errors.append(f"OSV: {exc}")

    online = bool(sources)
    # Only call something a "candidate novel issue" when a lookup actually
    # succeeded and returned nothing — absence of data is not absence of a CVE.
    candidate_novel = online and not matches
    if not online:
        note = "CVE lookup unavailable (offline or blocked); could not check public databases."
    elif candidate_novel:
        # The console shows this verbatim beside the banner that already says
        # "no public CVE matched"; the long form repeated that banner in prose.
        note = "No match is not proof of none — verify scope before claiming a zero-day."
    else:
        note = f"Matched {len(matches)} public record(s); confirm relevance before citing."

    return {
        "query": keywords,
        "package": package or None,
        "sources_queried": sources,
        "matches": matches[: limit * 2],
        "match_count": len(matches),
        "candidate_novel": candidate_novel,
        "online": online,
        "errors": errors,
        "note": note,
        "disclaimer": "CVE correlation is advisory and requires human validation; VulnoraIQ does not assign CVE identifiers.",
    }
