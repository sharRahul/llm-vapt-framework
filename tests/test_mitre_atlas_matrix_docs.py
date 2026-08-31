from __future__ import annotations

from pathlib import Path

from scripts.generate_mitre_atlas_matrix import DEFAULT_SOURCE_URL, UNMAPPED_LABEL

MATRIX_DOC = Path("docs/reference/mitre-atlas-matrix.md")
GENERATOR = Path("scripts/generate_mitre_atlas_matrix.py")


def test_mitre_atlas_matrix_doc_exists() -> None:
    assert MATRIX_DOC.exists()
    text = MATRIX_DOC.read_text(encoding="utf-8")
    assert "MITRE ATLAS Matrix for AI Systems" in text
    assert "Unmapped / map later" in text
    assert "Drift-control rule" in text


def test_mitre_atlas_matrix_doc_points_to_official_source_and_generator() -> None:
    text = MATRIX_DOC.read_text(encoding="utf-8")
    assert "https://atlas.mitre.org" in text
    assert "https://github.com/mitre-atlas/atlas-data" in text
    assert "scripts/generate_mitre_atlas_matrix.py" in text
    assert "vulnoraiq-generate-atlas-matrix" in text


def test_mitre_atlas_generator_defaults_to_official_source() -> None:
    assert GENERATOR.exists()
    assert "mitre-atlas/atlas-data" in DEFAULT_SOURCE_URL
    assert DEFAULT_SOURCE_URL.endswith("dist/v6/ATLAS-2026.05.yaml")
    assert UNMAPPED_LABEL == "Unmapped / map later"
