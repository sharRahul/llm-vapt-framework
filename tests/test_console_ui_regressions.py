from pathlib import Path

CONSOLE = Path("webui/console/src")


def test_scan_completion_preserves_the_operator_view() -> None:
    app = (CONSOLE / "App.tsx").read_text(encoding="utf-8")

    assert 'refreshScanFindings(scan.id, { ...scan, status: "completed" }, undefined, false)' in app


def test_asset_navigation_expands_when_async_assets_arrive() -> None:
    pane = (CONSOLE / "components/navigation/AssetNavigationPane.tsx").read_text(encoding="utf-8")

    assert "useEffect" in pane
    assert "setExpanded" in pane
    assert "assets[0]?.id" in pane


def test_dashboard_charts_are_decorative_to_keyboard_and_screen_reader_users() -> None:
    severity = (CONSOLE / "components/dashboard/SeverityDonutChart.tsx").read_text(encoding="utf-8")
    burndown = (CONSOLE / "components/dashboard/BurnDownChart.tsx").read_text(encoding="utf-8")

    for chart in (severity, burndown):
        assert 'aria-hidden="true"' in chart
        assert "accessibilityLayer={false}" in chart


def test_workspace_shows_structured_finding_provenance() -> None:
    # The backend-to-console mapping moved out of App.tsx into lib/findings.ts
    # so the product rules could be unit tested; the provenance fields are
    # asserted there as well as here.
    findings = (CONSOLE / "lib/findings.ts").read_text(encoding="utf-8")
    workspace = (CONSOLE / "components/workspace/AnalysisWorkspace.tsx").read_text(encoding="utf-8")

    assert "source: String(finding.source || \"scanner_observed\")" in findings
    assert "Provenance" in workspace
