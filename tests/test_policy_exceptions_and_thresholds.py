from __future__ import annotations

from datetime import datetime, timezone

from core.approval_evidence import ApprovalEvidenceRegistry
from core.exception_registry import PolicyExceptionRegistry
from core.policy_engine import PolicyEngine
from core.types import Confidence, Finding, FindingSource, PolicyResult, ScanResult


def test_severity_threshold_policy_passes_demo_scan() -> None:
    result = ScanResult(
        target_name="demo",
        profile_name="baseline",
        findings=[
            Finding(
                title="Info finding",
                description="Safe finding",
                severity="info",
                owasp_id="LLM00:2025",
                affected_component="demo",
                source=FindingSource.SCANNER_OBSERVED,
                confidence=Confidence.MEDIUM,
                tool="test",
                observed_at=datetime.now(timezone.utc),
            )
        ],
        started_at=datetime.now(timezone.utc),
    )
    config = {"policies": {"policies": {"severity_threshold": {"enabled": True, "maximum_allowed_severity": "high"}}}}

    policies = PolicyEngine().evaluate(result, config)

    threshold = next(policy for policy in policies if policy.policy_id == "severity_threshold")
    assert threshold.status == "pass"


def test_severity_threshold_policy_fails_critical() -> None:
    result = ScanResult(
        target_name="demo",
        profile_name="baseline",
        findings=[
            Finding(
                title="Critical finding",
                description="Critical result",
                severity="critical",
                owasp_id="LLM00:2025",
                affected_component="demo",
                source=FindingSource.SCANNER_OBSERVED,
                confidence=Confidence.MEDIUM,
                tool="test",
                observed_at=datetime.now(timezone.utc),
            )
        ],
        started_at=datetime.now(timezone.utc),
    )
    config = {"policies": {"policies": {"severity_threshold": {"enabled": True, "maximum_allowed_severity": "high"}}}}

    policies = PolicyEngine().evaluate(result, config)

    threshold = next(policy for policy in policies if policy.policy_id == "severity_threshold")
    assert threshold.status == "fail"


def test_active_policy_exception_suppresses_fail_to_warn_with_valid_approval(tmp_path) -> None:
    exception_file = tmp_path / "policy_exceptions.yaml"
    approval_file = tmp_path / "approval_evidence.yaml"
    canonical = "TEST-APPROVAL-001|security-team|demo-fixture|2999-01-01"
    signature = ApprovalEvidenceRegistry.expected_signature(canonical)
    approval_file.write_text(
        f"""
approvals:
  - id: TEST-APPROVAL-001
    owner: security-team
    approver: risk-owner@example.invalid
    scope: demo-fixture
    issued_on: 2026-06-22
    expires_on: 2999-01-01
    canonical_statement: "{canonical}"
    signature_algorithm: sha256
    signature: {signature}
""",
        encoding="utf-8",
    )
    exception_file.write_text(
        """
exceptions:
  - id: EX-001
    policy_id: severity_threshold
    status: active
    owner: security-team
    reason: Approved temporary acceptance for test fixture.
    expires_on: 2999-01-01
    target: demo
    profile: baseline
    approval_reference: TEST-APPROVAL-001
    compensating_controls:
      - Manual review required.
""",
        encoding="utf-8",
    )
    result = ScanResult(target_name="demo", profile_name="baseline", findings=[], started_at=datetime.now(timezone.utc))
    registry = PolicyExceptionRegistry(exception_file, approval_registry=ApprovalEvidenceRegistry(approval_file))
    policy = PolicyResult(policy_id="severity_threshold", status="fail", decision="fail_on_critical", message="Original failure", evidence={})

    updated = registry.apply(result, [policy])

    assert updated[0].status == "warn"
    assert updated[0].evidence["original_status"] == "fail"
    assert updated[0].evidence["active_exceptions"] == ["EX-001"]
    assert updated[0].evidence["approval_references"] == ["TEST-APPROVAL-001"]


def test_active_policy_exception_without_valid_approval_does_not_suppress(tmp_path) -> None:
    exception_file = tmp_path / "policy_exceptions.yaml"
    exception_file.write_text(
        """
exceptions:
  - id: EX-002
    policy_id: severity_threshold
    status: active
    owner: security-team
    reason: Missing approval evidence.
    expires_on: 2999-01-01
    target: demo
    profile: baseline
    approval_reference: MISSING-APPROVAL
""",
        encoding="utf-8",
    )
    result = ScanResult(target_name="demo", profile_name="baseline", findings=[], started_at=datetime.now(timezone.utc))
    registry = PolicyExceptionRegistry(exception_file, approval_registry=ApprovalEvidenceRegistry(tmp_path / "missing.yaml"))
    policy = PolicyResult(policy_id="severity_threshold", status="fail", decision="fail_on_critical", message="Original failure", evidence={})

    updated = registry.apply(result, [policy])

    assert updated[0].status == "fail"
    assert "exception_validation" in updated[0].evidence
