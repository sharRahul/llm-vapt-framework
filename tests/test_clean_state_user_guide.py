from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_react_app_does_not_import_or_fallback_to_dummy_data() -> None:
    app = (ROOT / "webui" / "console" / "src" / "App.tsx").read_text(encoding="utf-8")

    forbidden = [
        "@/data/mock",
        "demoAssets",
        "demoFindings",
        "trendData",
    ]
    for token in forbidden:
        assert token not in app

    assert "const displayFindings = runtimeFindings" in app
    assert "const displayAssets = activeScan ? [scanAsset(activeScan, runtimeFindings)] : []" in app
    assert "No scans yet" in app
    assert "no sample findings or dummy assets" in app
    assert "/api/scans" in app


def test_webui_mock_data_module_is_removed() -> None:
    assert not (ROOT / "webui" / "console" / "src" / "data" / "mock.ts").exists()


def test_user_guide_exists_and_documents_clean_state_flow() -> None:
    guide = (ROOT / "docs" / "getting-started" / "quick-start.md").read_text(encoding="utf-8")

    required = [
        "# Quick start",
        "Docker GUI lab",
        "Clean workspace",
        "does not show sample findings",
        "Configure targets",
        "Run a scan",
        "Review and act on findings",
        "Operate safely",
    ]
    for phrase in required:
        assert phrase in guide


def test_readme_and_docs_index_link_user_guide() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "docs/getting-started/quick-start.md" in readme
    assert "getting-started/quick-start.md" in docs_index
