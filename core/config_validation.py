"""Validate the YAML configuration once, at startup, and fail early.

Each config file used to be read lazily by whoever needed it and coerced ad hoc.
A malformed ``attack_profiles.yaml`` surfaced as a failed scan; a malformed
``safety_profiles.yaml`` silently yielded an empty profile, which *weakened*
enforcement instead of failing closed. Validating them together at boot turns
both into a startup error with a readable message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(RuntimeError):
    """Raised when configuration cannot be trusted to enforce what it declares."""


@dataclass(frozen=True, slots=True)
class ConfigFileSpec:
    filename: str
    #: Top-level key that must hold a mapping when the file is present.
    root_key: str | None
    #: A missing optional file is not an error; a missing required one is.
    required: bool


CONFIG_SPECS: tuple[ConfigFileSpec, ...] = (
    ConfigFileSpec("default.yaml", None, required=True),
    ConfigFileSpec("attack_profiles.yaml", "profiles", required=True),
    ConfigFileSpec("policies.yaml", "policies", required=True),
    ConfigFileSpec("safety_profiles.yaml", "safety_profiles", required=True),
    ConfigFileSpec("targets.yaml", "targets", required=False),
    ConfigFileSpec("policy_exceptions.yaml", None, required=False),
    ConfigFileSpec("web_users.yaml", None, required=False),
)


def config_root() -> Path:
    return Path(os.getenv("VULNORAIQ_CONFIG_DIR", "config"))


def _load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path} is not valid YAML: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"{path} could not be read: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"{path} must contain a mapping at the top level")
    return data


def _validate_safety_profiles(profiles: dict[str, Any], path: Path) -> list[str]:
    problems: list[str] = []
    if not profiles:
        problems.append(f"{path} declares no safety profiles, so no limits would be enforced")
    numeric_fields = (
        "max_payloads_per_module",
        "max_concurrency",
        "max_requests_per_scan",
        "request_timeout_seconds",
        "max_request_body_bytes",
        "max_response_body_bytes",
        "request_size_limit_bytes",
        "response_size_limit_bytes",
        "max_tool_steps",
    )
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            problems.append(f"safety profile '{name}' must be a mapping of settings")
            continue
        for key in numeric_fields:
            if key in profile and (not isinstance(profile[key], int) or isinstance(profile[key], bool)):
                problems.append(f"safety profile '{name}' setting '{key}' must be an integer")
        if profile.get("destructive_tests") is True:
            problems.append(f"safety profile '{name}' enables destructive_tests, which VulnoraIQ never permits")
    return problems


def _validate_attack_profiles(profiles: dict[str, Any], path: Path) -> list[str]:
    problems: list[str] = []
    if not profiles:
        problems.append(f"{path} declares no assessment profiles, so no scan could run")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            problems.append(f"assessment profile '{name}' must be a mapping")
            continue
        modules = profile.get("modules")
        if not isinstance(modules, list) or not modules:
            problems.append(f"assessment profile '{name}' must list at least one module")
    return problems


def validate_config(config_dir: str | Path | None = None) -> list[str]:
    """Return every configuration problem found, newest concern first.

    Returning the whole list rather than raising on the first one means an
    operator fixing a bad deployment sees all of it in a single run.
    """
    root = Path(config_dir) if config_dir is not None else config_root()
    problems: list[str] = []
    for spec in CONFIG_SPECS:
        path = root / spec.filename
        if not path.exists():
            if spec.required:
                problems.append(f"{path} is required but missing")
            continue
        try:
            data = _load(path)
        except ConfigurationError as exc:
            problems.append(str(exc))
            continue
        if spec.root_key is None:
            continue
        section = data.get(spec.root_key)
        if section is None:
            problems.append(f"{path} is missing the '{spec.root_key}' section")
            continue
        if not isinstance(section, dict):
            problems.append(f"'{spec.root_key}' in {path} must be a mapping")
            continue
        if spec.filename == "safety_profiles.yaml":
            problems.extend(_validate_safety_profiles(section, path))
        elif spec.filename == "attack_profiles.yaml":
            problems.extend(_validate_attack_profiles(section, path))
    return problems


def require_valid_config(config_dir: str | Path | None = None) -> None:
    """Raise :class:`ConfigurationError` listing every problem, or return quietly."""
    problems = validate_config(config_dir)
    if problems:
        joined = "\n  - ".join(problems)
        raise ConfigurationError(f"configuration is not valid:\n  - {joined}")
