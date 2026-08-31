from datetime import datetime, timezone

from core.risk_scoring import score_finding
from core.types import Confidence, Finding, FindingSource


def test_score_finding_caps_at_ten():
    finding = Finding(
        title="test",
        description="test",
        severity="critical",
        owasp_id="LLM01:2025",
        affected_component="test",
        source=FindingSource.SCANNER_OBSERVED,
        confidence=Confidence.MEDIUM,
        tool="test",
        observed_at=datetime.now(timezone.utc),
        evidence={"a": 1, "b": 2, "c": 3, "d": 4, "e": 5},
        mitre_atlas=["AML.T0051"],
    )

    assert score_finding(finding) <= 10.0
