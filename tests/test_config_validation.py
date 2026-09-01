"""Configuration is validated at startup and fails closed.

Each YAML file used to be read lazily and coerced ad hoc: a malformed
``attack_profiles.yaml`` surfaced as a failed scan, and a malformed
``safety_profiles.yaml`` silently yielded an empty profile, which *weakened*
enforcement instead of stopping the server.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.config_validation import ConfigurationError, require_valid_config, validate_config

REPO_CONFIG = Path("config")


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    destination = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, destination)
    return destination


def test_the_shipped_configuration_is_valid() -> None:
    assert validate_config(REPO_CONFIG) == []


def test_a_malformed_safety_profile_stops_startup(config_dir: Path) -> None:
    (config_dir / "safety_profiles.yaml").write_text("safety_profiles: [not, a, mapping]\n", encoding="utf-8")

    problems = validate_config(config_dir)

    assert any("safety_profiles" in problem for problem in problems)
    with pytest.raises(ConfigurationError):
        require_valid_config(config_dir)


def test_unparseable_yaml_is_reported_with_the_file_name(config_dir: Path) -> None:
    (config_dir / "attack_profiles.yaml").write_text("profiles: [unclosed\n", encoding="utf-8")

    problems = validate_config(config_dir)

    assert any("attack_profiles.yaml" in problem and "YAML" in problem for problem in problems)


def test_an_empty_safety_profile_file_is_refused(config_dir: Path) -> None:
    """No profiles means no limits, which must fail rather than run unbounded."""
    (config_dir / "safety_profiles.yaml").write_text("safety_profiles: {}\n", encoding="utf-8")

    assert any("no safety profiles" in problem for problem in validate_config(config_dir))


def test_a_profile_enabling_destructive_tests_is_refused(config_dir: Path) -> None:
    (config_dir / "safety_profiles.yaml").write_text(
        "safety_profiles:\n  reckless:\n    destructive_tests: true\n", encoding="utf-8"
    )

    assert any("destructive_tests" in problem for problem in validate_config(config_dir))


def test_a_profile_without_modules_is_refused(config_dir: Path) -> None:
    (config_dir / "attack_profiles.yaml").write_text("profiles:\n  empty:\n    description: nothing\n", encoding="utf-8")

    assert any("at least one module" in problem for problem in validate_config(config_dir))


def test_a_missing_required_file_is_reported(config_dir: Path) -> None:
    (config_dir / "policies.yaml").unlink()

    assert any("policies.yaml" in problem and "missing" in problem for problem in validate_config(config_dir))


def test_every_problem_is_listed_not_just_the_first(config_dir: Path) -> None:
    (config_dir / "policies.yaml").unlink()
    (config_dir / "safety_profiles.yaml").write_text("safety_profiles: {}\n", encoding="utf-8")

    assert len(validate_config(config_dir)) >= 2


# --- the runtime loader fails closed too ------------------------------------------


def test_a_target_naming_an_undefined_safety_profile_is_refused(monkeypatch, config_dir: Path) -> None:
    """An unknown profile used to yield ``{}``, quietly removing every limit."""
    from integrations import target_adapters

    monkeypatch.setenv("VULNORAIQ_SAFETY_PROFILE_PATH", str(config_dir / "safety_profiles.yaml"))
    target_adapters._safety_profiles_cached.cache_clear()

    with pytest.raises(ValueError, match="not defined"):
        target_adapters._load_safety_profile("no_such_profile")


def test_an_unreadable_safety_profile_file_is_refused(monkeypatch, tmp_path: Path) -> None:
    from integrations import target_adapters

    monkeypatch.setenv("VULNORAIQ_SAFETY_PROFILE_PATH", str(tmp_path / "absent.yaml"))
    target_adapters._safety_profiles_cached.cache_clear()

    with pytest.raises(ValueError, match="unavailable"):
        target_adapters._load_safety_profile("docker_lab")


def test_a_target_with_no_declared_profile_still_loads(monkeypatch, config_dir: Path) -> None:
    from integrations import target_adapters

    monkeypatch.setenv("VULNORAIQ_SAFETY_PROFILE_PATH", str(config_dir / "safety_profiles.yaml"))
    target_adapters._safety_profiles_cached.cache_clear()

    assert target_adapters._load_safety_profile("") == {}
