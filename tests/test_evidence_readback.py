"""Raw evidence is reachable, and only from inside the evidence root.

``VULNORAIQ_EVIDENCE_DIR`` was written to and never read back: no index, no
route, no link from a finding. The material a reviewer most wants was the least
reachable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.evidence_index import INDEX_FILENAME, build_index, read_artifact, write_index


def _report_with_artifact(path: Path) -> dict:
    return {
        "findings": [
            {
                "id": "finding-1",
                "title": "Prompt injection resilience",
                "source": "scanner_observed",
                "confidence": "high",
                "tool": "prompt_injection",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "limitations": "Human review required.",
                "evidence": {
                    "evidence_items": [
                        {"raw_artifact_path": str(path), "test_id": "pi-1", "policy_decision": "warn"}
                    ]
                },
            }
        ]
    }


@pytest.fixture()
def evidence_file(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    artifact = root / "prompt_injection-pi-1.json"
    artifact.write_text(json.dumps({"payload": {"id": "pi-1"}, "adapter_result": {"answer": "refused"}}), "utf-8")
    monkeypatch.setenv("VULNORAIQ_EVIDENCE_DIR", str(root))
    return artifact


def test_the_index_records_provenance_alongside_each_artifact(evidence_file: Path) -> None:
    index = build_index("scan-1", _report_with_artifact(evidence_file))

    entry = index["findings"][0]
    assert entry["finding_id"] == "finding-1"
    assert entry["source"] == "scanner_observed"
    assert entry["confidence"] == "high"
    assert entry["tool"] == "prompt_injection"
    assert entry["artifacts"][0]["available"] is True
    assert entry["artifacts"][0]["size_bytes"] > 0


def test_the_index_is_written_next_to_the_report_artefacts(tmp_path: Path, evidence_file: Path) -> None:
    output_dir = tmp_path / "out"

    write_index("scan-1", _report_with_artifact(evidence_file), output_dir)

    assert json.loads((output_dir / INDEX_FILENAME).read_text(encoding="utf-8"))["scan_id"] == "scan-1"


def test_an_indexed_artifact_reads_back_its_content(evidence_file: Path) -> None:
    index = build_index("scan-1", _report_with_artifact(evidence_file))

    result = read_artifact(index, "finding-1", "0")

    assert result is not None
    assert result["content"]["adapter_result"]["answer"] == "refused"
    assert "/" not in result["artifact"]["path"], "only the file name is exposed to the client"


def test_a_path_outside_the_evidence_root_is_not_indexed(tmp_path: Path, evidence_file: Path) -> None:
    """An artefact path is only trusted when it resolves inside a root we own."""
    stray = tmp_path / "elsewhere" / "secrets.json"
    stray.parent.mkdir()
    stray.write_text("{}", encoding="utf-8")

    index = build_index("scan-1", _report_with_artifact(stray))

    assert index["findings"][0]["artifacts"] == []


def test_an_unindexed_artifact_id_is_refused(evidence_file: Path) -> None:
    index = build_index("scan-1", _report_with_artifact(evidence_file))

    assert read_artifact(index, "finding-1", "99") is None
    assert read_artifact(index, "no-such-finding", "0") is None


def test_a_missing_file_is_reported_as_unavailable(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("VULNORAIQ_EVIDENCE_DIR", str(root))
    index = build_index("scan-1", _report_with_artifact(root / "never-written.json"))

    assert index["findings"][0]["artifacts"][0]["available"] is False
    assert read_artifact(index, "finding-1", "0") is None


def test_a_scan_writes_an_evidence_index_into_its_summary(monkeypatch, tmp_path: Path) -> None:
    from webui import hosted_server
    from webui.persistent_jobs import SqliteJobStore

    store = SqliteJobStore(tmp_path / "jobs.db")
    monkeypatch.setattr(hosted_server, "JOB_STORE", store)
    monkeypatch.setattr(hosted_server, "OUTPUT_ROOT", tmp_path / "out")
    job = store.create("demo", "baseline", True)

    hosted_server.run_scan_job(job.id)

    stored = store.get(job.id)
    assert stored is not None
    assert stored.status == "completed", stored.error
    index = stored.summary["evidence_index"]
    assert index["scan_id"] == job.id
    assert len(index["findings"]) == stored.summary["finding_count"]
    assert (tmp_path / "out" / job.id / INDEX_FILENAME).exists()
