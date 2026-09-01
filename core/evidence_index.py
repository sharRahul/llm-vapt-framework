"""Index and read back the raw evidence a scan wrote to disk.

``VULNORAIQ_EVIDENCE_DIR`` has always received raw request/response artefacts,
but nothing read them: no index, no route, no link from a finding. The material
a reviewer most wants was the least reachable. This module writes the index at
report time and resolves an indexed artefact back to bytes under the same root
check the download route uses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

INDEX_FILENAME = "evidence-index.json"


def evidence_root() -> Path:
    return Path(os.getenv("VULNORAIQ_EVIDENCE_DIR", "reports/output/evidence"))


def _within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _artifact_entries(finding: dict[str, Any], roots: list[Path]) -> list[dict[str, Any]]:
    """Collect the on-disk artefacts a finding recorded, rejecting stray paths."""
    entries: list[dict[str, Any]] = []
    items = finding.get("evidence", {}).get("evidence_items") or []
    for position, item in enumerate(items if isinstance(items, list) else []):
        raw_path = str((item or {}).get("raw_artifact_path") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        # An artefact path is only trusted when it resolves inside a root this
        # deployment owns; anything else is not served.
        if not any(_within(path, root) for root in roots):
            continue
        entries.append(
            {
                "artifact_id": f"{position}",
                "name": path.name,
                "path": str(path),
                "test_id": str((item or {}).get("test_id") or ""),
                "policy_decision": str((item or {}).get("policy_decision") or "review"),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "available": path.exists(),
            }
        )
    return entries


def build_index(scan_id: str, report_data: dict[str, Any]) -> dict[str, Any]:
    roots = [evidence_root(), Path(os.getenv("VULNORAIQ_WEB_OUTPUT_ROOT", "reports/output/webui"))]
    findings: list[dict[str, Any]] = []
    for position, finding in enumerate(report_data.get("findings", []) or [], start=1):
        finding_id = str(finding.get("id") or finding.get("owasp_id") or f"finding-{position}")
        findings.append(
            {
                "finding_id": finding_id,
                "title": finding.get("title", ""),
                "source": finding.get("source", "scanner_observed"),
                "confidence": finding.get("confidence", "medium"),
                "tool": finding.get("tool", ""),
                "observed_at": finding.get("observed_at", ""),
                "limitations": finding.get("limitations", ""),
                "artifacts": _artifact_entries(finding, roots),
            }
        )
    return {"scan_id": scan_id, "findings": findings}


def write_index(scan_id: str, report_data: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    index = build_index(scan_id, report_data)
    destination = Path(output_dir) / INDEX_FILENAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(index, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return index


def read_artifact(index: dict[str, Any], finding_id: str, artifact_id: str) -> dict[str, Any] | None:
    """Return one indexed artefact's contents, or ``None`` when it is not indexed.

    Only paths the index already recorded can be reached, so an artefact
    reference from a request body cannot escape the evidence root.
    """
    for finding in index.get("findings", []) or []:
        if str(finding.get("finding_id")) != finding_id:
            continue
        for artifact in finding.get("artifacts", []) or []:
            if str(artifact.get("artifact_id")) != artifact_id:
                continue
            path = Path(str(artifact.get("path", "")))
            if not any(_within(path, root) for root in [evidence_root(), Path("reports/output")]):
                return None
            if not path.exists():
                return None
            try:
                content: Any = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                content = path.read_text(encoding="utf-8", errors="replace")[:200_000]
            return {"artifact": {**artifact, "path": path.name}, "content": content}
    return None
