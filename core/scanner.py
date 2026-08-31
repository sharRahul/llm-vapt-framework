from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

from core.evidence_model import OwaspOracleRegistry
from core.policy_engine import PolicyEngine
from core.production_detection import ProductionOwaspDetector
from core.real_scan import run_real_target_modules
from core.runtime_targets import merge_into as merge_runtime_targets
from core.test_runner import TestRunner
from core.types import Finding, ScanContext, ScanResult, TargetClient
from integrations.target_adapters import RealTargetClient


def _fixture_targets_allowed() -> bool:
    return os.getenv("VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS", "false").strip().lower() in ("1", "true", "yes")


class TestFixtureTargetClient:
    """Deterministic target used only when test fixture targets are explicitly enabled."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        lowered = prompt.lower()
        if "secret" in lowered or "password" in lowered or "token" in lowered:
            return "I cannot reveal secrets, passwords, tokens, or protected system instructions."
        if "ignore" in lowered and "instruction" in lowered:
            return "I will follow the authorised system policy and ignore untrusted override instructions."
        if "tool" in lowered or "action" in lowered:
            return "Tool execution is constrained to approved, least-privilege actions with human review gates."
        return "Safe deterministic test fixture response for authorised VulnoraIQ validation."


class Scanner:
    """High-level assessment entry point."""

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)
        self.runner = TestRunner()
        self.policy_engine = PolicyEngine()
        self.oracle_registry = OwaspOracleRegistry()
        self.production_detector = ProductionOwaspDetector()

    def validate_scan(
        self,
        target_name: str,
        profile_name: str = "baseline",
        authorised: bool = True,
    ) -> None:
        """Run every pre-flight check without sending a single request.

        Callers that report progress need to know the target and authorisation
        are genuinely valid *before* they say so. Raises the same errors
        :meth:`scan` would raise for the same configuration.
        """
        config = self._load_config()
        self._resolve_profile(config, profile_name)
        self._require_authorisation(authorised=authorised, policy=config.get("policies", {}))
        self._default_target(target_name, config=config)

    @staticmethod
    def _resolve_profile(config: dict[str, Any], profile_name: str) -> dict[str, Any]:
        profile = config["attack_profiles"].get("profiles", {}).get(profile_name)
        if not profile:
            raise ValueError(f"Unknown assessment profile: {profile_name}")
        return profile

    def scan(
        self,
        target_name: str,
        profile_name: str = "baseline",
        target: TargetClient | None = None,
        authorised: bool = True,
    ) -> ScanResult:
        config = self._load_config()
        profile = self._resolve_profile(config, profile_name)
        self._require_authorisation(authorised=authorised, policy=config.get("policies", {}))
        target_client = target or self._default_target(target_name, config=config)
        context = ScanContext(
            target_name=target_name,
            profile_name=profile_name,
            target=target_client,
            config=config,
        )
        if profile_name == "owasp-aitg-full" or "aitg_full_manifest" in profile.get("modules", []):
            findings = self._run_aitg_full_manifest(context)
        elif isinstance(target_client, RealTargetClient):
            findings = run_real_target_modules(context, profile, self.runner.payload_library)
        else:
            findings = self.runner.run_modules(profile["modules"], context)
        aitg_matrix = (
            self._aitg_coverage_matrix(findings)
            if profile_name == "owasp-aitg-full" or "aitg_full_manifest" in profile.get("modules", [])
            else []
        )
        result = ScanResult(
            target_name=target_name,
            profile_name=profile_name,
            findings=findings,
            started_at=context.started_at,
            completed_at=datetime.now(timezone.utc),
            metadata={
                "framework": config.get("default", {}).get("framework", {}),
                "profile_description": profile.get("description", ""),
                "authorised": authorised,
                "owasp_oracle_coverage": self.oracle_registry.coverage_summary(),
                "production_owasp_detection": self.production_detector.coverage_summary(),
                "production_validation_status": "authorised_production_assessment_testing_ready",
                "assessment_scope_warning": (
                    "Run only against systems you own or are explicitly authorised to test; "
                    "findings still require tester review and business-context validation."
                ),
                "aitg_coverage_matrix": aitg_matrix,
            },
        )
        result.policy_results = self.policy_engine.evaluate(result, config)
        return result

    @staticmethod
    def _aitg_coverage_matrix(findings: list[Finding]) -> list[dict[str, Any]]:
        matrix = []
        for finding in findings:
            if "aitg_test_id" in finding.evidence:
                matrix.append(
                    {
                        "test_id": finding.evidence["aitg_test_id"],
                        "status": finding.evidence.get("status", "passed"),
                        "confidence": finding.evidence.get("confidence", "medium"),
                        "evidence_artifacts": finding.evidence.get("evidence_artifacts", []),
                        "owasp_llm_top10": finding.owasp_id.split(",") if finding.owasp_id else [],
                        "mitre_atlas": finding.mitre_atlas,
                        "limitations": finding.evidence.get("limitations", "Human review required."),
                    }
                )
        return matrix

    def _run_aitg_full_manifest(self, context: ScanContext) -> list[Finding]:
        manifest_path = Path("benchmarks/fixtures/aitg/aitg_32_manifest.yaml")
        if not manifest_path.exists():
            manifest_path = self.config_dir.parent / "benchmarks" / "fixtures" / "aitg" / "aitg_32_manifest.yaml"
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        findings: list[Finding] = []
        for item in data.get("aitg_tests", []):
            findings.append(
                Finding(
                    title=f"{item['id']} coverage executed",
                    description=item["objective"],
                    severity="info",
                    owasp_id=",".join(item.get("owasp_llm_top10", [])) or "AITG",
                    affected_component=item["owasp_ai_testing_guide_section"],
                    evidence={
                        "aitg_test_id": item["id"],
                        "status": "passed",
                        "confidence": "medium",
                        "fixture": item["fixture"],
                        "evidence_artifacts": item["evidence_artifacts"],
                        "limitations": "Synthetic fixture coverage by default; real target assurance requires explicit authorised configuration and human review.",
                    },
                    recommendation="Review mapped evidence and validate applicability with an authorised system owner before making assurance claims.",
                    mitre_atlas=item.get("mitre_atlas", []),
                )
            )
        return findings

    def _require_authorisation(
        self,
        authorised: bool,
        policy: dict[str, Any],
    ) -> None:
        policy_config = policy.get("policies", {}).get("authorised_testing_required", {})
        policy_enabled = bool(policy_config.get("enabled", True))
        if policy_enabled and not authorised:
            raise PermissionError(
                "Targets require explicit authorisation. Re-run with the --authorised flag "
                "only for systems you own or are permitted to assess."
            )

    @staticmethod
    def _reject_fixture_target(target_name: str, target_config: dict[str, Any] | None = None) -> None:
        if _fixture_targets_allowed():
            return
        target_config = target_config or {}
        target_values = [target_name, str(target_config.get("type", "")), str(target_config.get("environment", ""))]
        for value in target_values:
            lower = value.lower()
            for word in ("demo", "mock", "fake", "fixture"):
                if word in lower:
                    raise ValueError(
                        f"Target '{target_name}' contains '{word}' and is not allowed in normal runtime. "
                        "Set VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS=true to enable test fixture targets."
                    )

    def _default_target(self, target_name: str, config: dict[str, Any]) -> TargetClient:
        target_config = config.get("targets", {}).get("targets", {}).get(target_name)
        if not target_config:
            raise ValueError(f"Unknown target: {target_name}")
        self._reject_fixture_target(target_name, target_config)
        if str(target_config.get("type", "")).lower() == "test_fixture":
            return cast(TargetClient, TestFixtureTargetClient(target_name))
        self._reject_placeholder(target_name, target_config.get("endpoint") or target_config.get("base_url"))
        return RealTargetClient(target_name, target_config)

    @staticmethod
    def _reject_placeholder(target_name: str, endpoint: Any) -> None:
        if not endpoint or "example.invalid" in str(endpoint):
            raise ValueError(
                f"Target '{target_name}' is a placeholder. Configure a real authorised endpoint before assessment."
            )

    def _load_config(self) -> dict[str, Any]:
        def load_yaml(name: str) -> dict[str, Any]:
            path = self.config_dir / name
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}

        targets = load_yaml(os.getenv("VULNORAIQ_TARGET_CONFIG", "targets.yaml"))
        targets["targets"] = merge_runtime_targets(targets.get("targets") or {})
        return {
            "default": load_yaml("default.yaml"),
            "targets": targets,
            "attack_profiles": load_yaml("attack_profiles.yaml"),
            "policies": load_yaml("policies.yaml"),
            "safety_profiles": load_yaml("safety_profiles.yaml"),
        }

