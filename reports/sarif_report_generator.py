from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.results_engine import ResultsEngine
from core.types import ScanResult


class SarifReportGenerator:
    """Generates a SARIF-style report for CI and code-scanning workflows."""

    def __init__(self) -> None:
        self.results_engine = ResultsEngine()

    def generate(self, result: ScanResult, output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        report = self.results_engine.normalise(result)
        sarif = self._build_sarif(report)
        output.write_text(json.dumps(sarif, indent=2, sort_keys=True), encoding="utf-8")
        return output

    def _build_sarif(self, report: dict[str, Any]) -> dict[str, Any]:
        rules = self._rules(report)
        return {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "VulnoraIQ",
                            "informationUri": "https://github.com/sharRahul/vulnoraiq",
                            "rules": list(rules.values()),
                        }
                    },
                    "automationDetails": {
                        "id": f"{report.get('target', 'unknown')}/{report.get('profile', 'unknown')}"
                    },
                    "properties": {
                        "policy_status": report.get("policy_status", "pass"),
                        "highest_severity": report.get("highest_severity", "info"),
                    },
                    "results": [self._finding_to_result(finding) for finding in report.get("findings", [])],
                }
            ],
        }

    def _rules(self, report: dict[str, Any]) -> dict[str, dict[str, Any]]:
        rules: dict[str, dict[str, Any]] = {}
        for finding in report.get("findings", []):
            rule_id = str(finding.get("owasp_id", "UNMAPPED"))
            if rule_id in rules:
                continue
            rules[rule_id] = {
                "id": rule_id,
                "name": rule_id.replace(":", "_"),
                "shortDescription": {"text": rule_id},
                "fullDescription": {"text": str(finding.get("title", rule_id))},
                "help": {"text": str(finding.get("recommendation", "Review the finding and apply compensating controls."))},
                "properties": {
                    "component": finding.get("affected_component", "Unknown"),
                    "source": finding.get("source", "unknown"),
                    "confidence": finding.get("confidence", "unknown"),
                    "tool": finding.get("tool", "unknown"),
                    "observed_at": finding.get("observed_at"),
                    "limitations": finding.get("limitations", ""),
                },
            }
        return rules

    def _finding_to_result(self, finding: dict[str, Any]) -> dict[str, Any]:
        title = str(finding.get("title", "VulnoraIQ assessment finding"))
        severity = str(finding.get("severity", "info")).lower()
        return {
            "ruleId": str(finding.get("owasp_id", "UNMAPPED")),
            "level": self._level(severity),
            "message": {"text": title},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "vulnoraiq://assessment"},
                        "region": {"startLine": 1},
                    }
                }
            ],
            "properties": {
                "severity": severity,
                "score": finding.get("score"),
                "component": finding.get("affected_component"),
                "mitre_atlas": finding.get("mitre_atlas", []),
                "evidence": finding.get("evidence", {}),
                "source": finding.get("source", "unknown"),
                "confidence": finding.get("confidence", "unknown"),
                "tool": finding.get("tool", "unknown"),
                "observed_at": finding.get("observed_at"),
                "limitations": finding.get("limitations", ""),
            },
        }

    @staticmethod
    def _level(severity: str) -> str:
        if severity in {"critical", "high"}:
            return "error"
        if severity == "medium":
            return "warning"
        return "note"
