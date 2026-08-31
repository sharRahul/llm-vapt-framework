from __future__ import annotations

import json
from datetime import datetime

import pytest

from core.scanner import Scanner
from core.types import Finding
from reports.sarif_report_generator import SarifReportGenerator


def test_finding_requires_structured_provenance() -> None:
    with pytest.raises(TypeError):
        Finding(  # type: ignore[call-arg]  # This assertion deliberately omits required provenance.
            title="Missing provenance",
            description="A finding without a source must not be representable.",
            severity="info",
            owasp_id="TEST",
            affected_component="test",
        )


def test_scanner_emits_observed_provenance_in_every_finding() -> None:
    result = Scanner().scan(target_name="demo", profile_name="baseline")

    for finding in result.findings:
        assert finding.source.value == "scanner_observed"
        assert finding.tool
        assert isinstance(finding.observed_at, datetime)
        assert finding.confidence.value in {"low", "medium", "high"}


def test_sarif_carries_finding_provenance(tmp_path) -> None:
    result = Scanner().scan(target_name="demo", profile_name="baseline")
    output = SarifReportGenerator().generate(result, tmp_path / "report.sarif")
    finding = json.loads(output.read_text(encoding="utf-8"))["runs"][0]["results"][0]

    assert finding["properties"]["source"] == "scanner_observed"
    assert finding["properties"]["tool"]
    assert finding["properties"]["confidence"] in {"low", "medium", "high"}
    assert finding["properties"]["observed_at"]
