from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_installation_requirements() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Installation" in readme
    for phrase in [
        "Docker Engine or Docker Desktop",
        "Compose v2",
        "Python 3.10+",
        "modern browser",
        "Node.js 20+",
    ]:
        assert phrase in readme


def test_webui_alignment_utilities_are_defined() -> None:
    css = (ROOT / "webui" / "console" / "src" / "index.css").read_text(encoding="utf-8")

    for utility in [".break-anywhere", ".ui-icon", ".ui-title-row", ".ui-action-row"]:
        assert utility in css
    assert "overflow-wrap: anywhere" in css


def test_header_and_target_workspace_use_responsive_alignment() -> None:
    header = (ROOT / "webui" / "console" / "src" / "components" / "HeaderBar.tsx").read_text(encoding="utf-8")
    targets = (ROOT / "webui" / "console" / "src" / "components" / "targets" / "TargetsManager.tsx").read_text(encoding="utf-8")

    assert "flex-wrap" in header
    assert "overflow-x-auto" in header
    assert "ui-title-row" in header
    assert "grid-cols-1" in targets
    assert "lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]" in targets
    assert "ui-action-row" in targets
    assert "break-anywhere" in targets


def test_buttons_and_cards_keep_icons_aligned() -> None:
    button = (ROOT / "webui" / "console" / "src" / "components" / "ui" / "button.tsx").read_text(encoding="utf-8")
    kpi = (ROOT / "webui" / "console" / "src" / "components" / "dashboard" / "KpiCard.tsx").read_text(encoding="utf-8")
    asset_card = (ROOT / "webui" / "console" / "src" / "components" / "navigation" / "AssetFindingCard.tsx").read_text(encoding="utf-8")

    assert "[&_svg]:self-center" in button
    assert "min-w-0" in button
    assert "ui-icon" in kpi
    assert "break-anywhere" in kpi
    assert "ui-icon" in asset_card
    assert "break-anywhere" in asset_card
