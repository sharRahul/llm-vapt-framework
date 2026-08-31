from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from core.types import Finding, PolicyResult, ScanResult


class ResultsEngine:
    """Normalises and summarises assessment output."""

    def normalise(self, result: ScanResult) -> dict[str, Any]:
        severity_counts = Counter(f.severity.lower() for f in result.findings)
        owasp_counts = Counter(f.owasp_id for f in result.findings)
        policy_counts = Counter(p.status.lower() for p in result.policy_results)
        return {
            "target": result.target_name,
            "profile": result.profile_name,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "finding_count": result.finding_count,
            "highest_severity": result.highest_severity,
            "policy_status": result.policy_status,
            "severity_counts": dict(severity_counts),
            "owasp_counts": dict(owasp_counts),
            "policy_counts": dict(policy_counts),
            "metadata": result.metadata,
            "findings": [self._finding_to_dict(f) for f in result.findings],
            "policy_results": [self._policy_to_dict(p) for p in result.policy_results],
        }

    @staticmethod
    def _finding_to_dict(finding: Finding) -> dict[str, Any]:
        data = asdict(finding)
        data["severity"] = finding.severity.lower()
        data["source"] = finding.source.value
        data["confidence"] = finding.confidence.value
        data["observed_at"] = finding.observed_at.isoformat()
        return data

    @staticmethod
    def _policy_to_dict(policy_result: PolicyResult) -> dict[str, Any]:
        data = asdict(policy_result)
        data["status"] = policy_result.status.lower()
        return data
