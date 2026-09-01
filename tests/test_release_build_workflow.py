"""Release paths live in the single workflow but must not run as normal CI.

Test, container, security, ATLAS refresh, and release used to be five workflow
files that repeated the same setup and re-ran the same suite on the same events.
They are one file now, so the guard that mattered — a release job must not fire
on an ordinary push or pull request — is a job-level condition rather than a
separate trigger block, and that is what these assert.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _workflow()["jobs"]


def test_there_is_exactly_one_workflow() -> None:
    assert sorted(p.name for p in Path(".github/workflows").glob("*.yml")) == ["ci.yml"]


def test_the_workflow_handles_every_event_the_split_files_did() -> None:
    triggers = _workflow()[True]

    assert set(triggers) == {"push", "pull_request", "schedule", "release", "workflow_dispatch"}
    assert triggers["release"]["types"] == ["published"]


def test_release_jobs_do_not_run_on_push_or_pull_request() -> None:
    for name in ("python-package", "release-package"):
        condition = _jobs()[name]["if"]
        assert "github.event_name == 'release'" in condition
        assert "inputs.run == 'release'" in condition
        assert "workflow_dispatch" in condition


def test_the_release_job_builds_all_target_platforms() -> None:
    include = _jobs()["release-package"]["strategy"]["matrix"]["include"]
    by_platform = {entry["platform"]: entry for entry in include}

    assert set(by_platform) == {"windows", "linux", "macos"}
    assert by_platform["windows"]["os"] == "windows-latest"
    assert by_platform["linux"]["os"] == "ubuntu-latest"
    assert by_platform["macos"]["os"] == "macos-latest"


def test_the_release_job_uses_native_artifact_extensions() -> None:
    include = _jobs()["release-package"]["strategy"]["matrix"]["include"]
    extensions = {entry["platform"]: entry["extension"] for entry in include}

    assert extensions == {"windows": "zip", "linux": "tar.gz", "macos": "dmg"}
    assert ".${{ matrix.extension }}" in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_publishing_a_python_package_requires_an_explicit_target() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    options = _workflow()[True]["workflow_dispatch"]["inputs"]["publish_to"]["options"]

    assert options == ["none", "testpypi", "pypi"]
    assert "inputs.publish_to == 'testpypi'" in _jobs()["publish-testpypi"]["if"]
    assert "inputs.publish_to == 'pypi'" in _jobs()["publish-pypi"]["if"]
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow


def test_a_manual_run_defaults_to_ci_only() -> None:
    """A dispatch meant as "just run CI" must not build or publish a release."""
    run_input = _workflow()[True]["workflow_dispatch"]["inputs"]["run"]

    assert run_input["default"] == "ci"
    assert run_input["options"] == ["ci", "security", "atlas", "release"]


def test_the_scheduled_run_only_refreshes_the_atlas_mapping() -> None:
    jobs = _jobs()

    assert jobs["atlas-refresh"]["if"].startswith("github.event_name == 'schedule'")
    for name in ("test", "docker", "security"):
        assert "github.event_name != 'schedule'" in jobs[name]["if"]
