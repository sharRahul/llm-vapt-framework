"""Authorisation and target-safety gates on the scanner entry point.

These are the checks that stop VulnoraIQ from assessing something the operator
has not explicitly authorised, or from treating an unconfigured placeholder as a
real system.
"""

from __future__ import annotations

import pytest

from core.scanner import Scanner


def test_scan_refuses_to_run_without_explicit_authorisation() -> None:
    with pytest.raises(PermissionError, match="explicit authorisation"):
        Scanner().scan(target_name="custom_http_agent", profile_name="baseline", authorised=False)


def test_placeholder_configured_target_is_rejected_when_authorised() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        Scanner().scan(target_name="custom_http_agent", profile_name="baseline", authorised=True)


def test_unknown_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown target"):
        Scanner().scan(target_name="no-such-target", profile_name="baseline", authorised=True)


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown assessment profile"):
        Scanner().scan(target_name="demo", profile_name="no-such-profile", authorised=True)


def test_fixture_target_runs_when_fixture_targets_are_enabled() -> None:
    # tests/conftest.py enables VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS.
    result = Scanner().scan(target_name="demo", profile_name="baseline", authorised=True)

    assert result.target_name == "demo"
    assert result.profile_name == "baseline"
    assert result.finding_count > 0
    assert result.metadata["authorised"] is True


def test_fixture_target_is_rejected_when_fixture_targets_are_disabled(monkeypatch) -> None:
    monkeypatch.setenv("VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS", "false")

    with pytest.raises(ValueError, match="not allowed in normal runtime"):
        Scanner().scan(target_name="demo", profile_name="baseline", authorised=True)
