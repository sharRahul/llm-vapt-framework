"""Deployment baseline: the hardening the shipped artefacts actually carry.

These assertions check the container image, the installation documentation, and
the quality tooling configuration. They deliberately do not assert on the prose
of any status or backlog document — readiness is attested by
``scripts/validate_production_testing_readiness.py``, which exercises the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
INSTALLATION_DOC = ROOT / "docs" / "getting-started" / "installation.md"


def test_container_image_is_hardened() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "USER vulnoraiq" in dockerfile, "the image must not run as root"
    assert "/healthz" in dockerfile, "the image must declare a health check"
    assert "VOLUME" in dockerfile and "/data" in dockerfile, "mutable state belongs on a volume"
    assert "pip install --no-cache-dir ." in dockerfile, "the runtime image must not install dev extras"
    install_lines = [line for line in dockerfile.splitlines() if "apt-get install" in line]
    assert not any("docker.io" in line for line in install_lines), "only the Docker client belongs in the image"


def test_compose_applies_container_restrictions() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "no-new-privileges:true" in compose
    assert "cap_drop" in compose
    assert "127.0.0.1:8787:8787" in compose, "the console must publish on loopback only"
    assert "privileged" not in compose
    assert "network_mode: host" not in compose
    assert "env_file" not in compose, "compose must not depend on a .env file"


def test_installation_doc_covers_production_operations() -> None:
    deployment = INSTALLATION_DOC.read_text(encoding="utf-8")
    lowered = deployment.lower()

    assert "VULNORAIQ_ADMIN_TOKEN" in deployment
    assert "VULNORAIQ_WEB_USERS_PATH" in deployment
    assert "Production Checklist" in deployment
    assert "reverse proxy" in lowered or "nginx" in lowered
    assert "tls" in lowered
    assert "backup" in lowered
    assert "audit" in lowered


def test_no_environment_files_are_tracked() -> None:
    """The repository must never carry a file whose name starts with `.env`."""
    offenders = [path for path in ROOT.rglob(".env*") if path.is_file() and ".git" not in path.parts]
    offenders = [p for p in offenders if not any(part in {".venv", "node_modules", "agent-lab", "projects"} for part in p.parts)]

    assert offenders == [], f"environment files present: {[str(p) for p in offenders]}"


@pytest.mark.parametrize("required_snippet", ["[tool.ruff]", "[tool.mypy]", "ruff>=", "mypy>="])
def test_lint_and_type_check_configuration_exists(required_snippet: str) -> None:
    assert required_snippet in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_type_checking_is_not_globally_disabled() -> None:
    """A type gate that ignores every error is not a gate."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "ignore_errors = true" not in pyproject


def test_no_test_files_are_excluded_from_the_suite() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "--ignore=tests/" not in pyproject
