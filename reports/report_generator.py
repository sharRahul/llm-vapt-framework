from __future__ import annotations

import json
from pathlib import Path

from core.results_engine import ResultsEngine
from core.types import ScanResult


class MarkdownReportGenerator:
    """Generates audit-friendly Markdown reports."""

    def __init__(self) -> None:
        self.results_engine = ResultsEngine()

    def generate(self, result: ScanResult, output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        normalised = self.results_engine.normalise(result)
        lines = [
            f"# VulnoraIQ Report - {normalised['target']}",
            "",
            "_LLM VAPT Report compatibility title for existing automation._",
            "",
            "## Executive Summary",
            "",
            f"- Profile: `{normalised['profile']}`",
            f"- Findings: `{normalised['finding_count']}`",
            f"- Highest severity: `{normalised['highest_severity']}`",
            f"- Policy status: `{normalised['policy_status']}`",
            "",
            "## Severity Counts",
            "",
        ]
        for severity, count in sorted(normalised["severity_counts"].items()):
            lines.append(f"- {severity}: {count}")

        lines.extend(["", "## Policy Evaluation", ""])
        if normalised["policy_results"]:
            for policy in normalised["policy_results"]:
                lines.extend(
                    [
                        f"### {policy['policy_id']}",
                        "",
                        f"- Status: `{policy['status']}`",
                        f"- Decision: `{policy['decision']}`",
                        f"- Message: {policy['message']}",
                        "",
                    ]
                )
        else:
            lines.append("No policy results were produced.")

        lines.extend(["", "## Findings", ""])
        for index, finding in enumerate(normalised["findings"], start=1):
            lines.extend([
                f"### {index}. {finding['title']}",
                "",
                f"- Severity: `{finding['severity']}`",
                f"- Score: `{finding.get('score')}`",
                f"- OWASP: `{finding['owasp_id']}`",
                f"- Component: `{finding['affected_component']}`",
                f"- MITRE ATLAS: `{', '.join(finding.get('mitre_atlas') or []) or 'Not mapped'}`",
                f"- Source: `{finding.get('source', 'scanner_observed')}`",
                f"- Confidence: `{finding.get('confidence', 'medium')}`",
                f"- Tool: `{finding.get('tool') or 'unknown'}`",
                f"- Observed at: `{finding.get('observed_at') or 'unknown'}`",
                "",
                finding["description"],
                "",
                f"Recommendation: {finding['recommendation']}",
                "",
                f"Limitations: {finding.get('limitations') or 'Human review is required before acting on this finding.'}",
                "",
                "Evidence:",
                "",
                "```json",
                json.dumps(finding.get("evidence", {}), indent=2, sort_keys=True),
                "```",
                "",
            ])
        output.write_text("\n".join(lines), encoding="utf-8")
        return output
