from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class TargetClient(Protocol):
    """Minimal target interface used by assessment modules."""

    name: str

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """Send an assessment input to the target and return a text response."""


class FindingSource(str, Enum):
    """How the assessment established a finding."""

    SCANNER_OBSERVED = "scanner_observed"
    INFERRED = "inferred"
    AI_ASSISTED = "ai_assisted"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class Finding:
    title: str
    description: str
    severity: str
    owasp_id: str
    affected_component: str
    source: FindingSource
    confidence: Confidence
    tool: str
    observed_at: datetime
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    mitre_atlas: list[str] = field(default_factory=list)
    score: float | None = None
    limitations: str = "Human review is required before acting on this finding."
    analysis_provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source is FindingSource.SCANNER_OBSERVED and self.analysis_provenance.get("assistant"):
            raise ValueError("scanner_observed findings cannot include assistant analysis provenance")


@dataclass(slots=True)
class PolicyResult:
    policy_id: str
    status: str
    decision: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScanContext:
    target_name: str
    profile_name: str
    target: TargetClient | None = None
    config: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class ScanResult:
    target_name: str
    profile_name: str
    findings: list[Finding]
    started_at: datetime
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_results: list[PolicyResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def highest_severity(self) -> str:
        order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        if not self.findings:
            return "info"
        return max(self.findings, key=lambda finding: order.get(finding.severity.lower(), 0)).severity

    @property
    def policy_status(self) -> str:
        if any(result.status == "fail" for result in self.policy_results):
            return "fail"
        if any(result.status == "warn" for result in self.policy_results):
            return "warn"
        return "pass"
