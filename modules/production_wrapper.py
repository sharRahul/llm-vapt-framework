from __future__ import annotations

from collections.abc import Mapping

from core.production_detection import ProductionOwaspDetector
from core.types import ScanContext
from modules.base import AssessmentModule
from modules.contract import ToolContract


class ProductionAssessmentModule:
    """Adds production OWASP detection evidence to an assessment module."""

    __slots__ = ("module", "metadata")

    def __init__(self, module: AssessmentModule) -> None:
        self.module = module
        self.metadata = module.metadata

    @property
    def contract(self) -> ToolContract:
        """Detection evidence is added in-process; the wrapped contract stands."""
        return self.module.contract

    def run(self, context: ScanContext, payloads):
        finding = self.module.run(context, payloads)
        detector = ProductionOwaspDetector()
        interaction_evidence = finding.evidence.get("interaction_evidence", [])
        production_results: list[dict] = []
        for item in interaction_evidence:
            if not isinstance(item, dict):
                continue
            detector_input = {
                "payload_id": item.get("payload_id"),
                "response_preview": item.get("response_preview"),
                "target": context.target_name,
                "prompt_category": item.get("prompt_category") or item.get("payload_metadata", {}).get("category") or "assessment",
                "owasp_id": finding.owasp_id,
            }
            result = detector.evaluate(
                str(finding.evidence.get("module", "")),
                detector_input,
                str(item.get("response_preview", "")),
            )
            item["production_detection_status"] = result.status
            item["production_detection_verdict"] = result.verdict
            item["production_detection_result"] = result.to_dict()
            production_results.append(result.to_dict())

        production_summary = detector.summarise(production_results)
        finding.evidence["check_type"] = "production_owasp_detection"
        finding.evidence["production_detection_status_summary"] = production_summary
        finding.evidence["production_detection_profile"] = detector.detector_profile
        finding.evidence["production_validation_status"] = "authorised_production_assessment_testing_ready"
        return finding


def wrap_production_modules(modules: Mapping[str, AssessmentModule]) -> dict[str, AssessmentModule]:
    return {name: ProductionAssessmentModule(module) for name, module in modules.items()}
