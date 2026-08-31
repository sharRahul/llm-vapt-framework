"""Single boundary for every Docker CLI invocation VulnoraIQ makes.

All container work (Agent Lab builds/deploys, prebuilt agent images, runtime
health checks) goes through :func:`run_docker`. Centralising it keeps three
properties in one auditable place:

* commands are always argument arrays — never an interpolated shell string;
* every invocation is bounded by a timeout;
* failures surface as ``DockerCommandError`` with the command's own stderr.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

LOGGER = logging.getLogger("vulnoraiq.webui.docker")

DEFAULT_TIMEOUT = int(os.getenv("VULNORAIQ_DOCKER_COMMAND_TIMEOUT", "600"))


class DockerCommandError(RuntimeError):
    """A ``docker`` invocation exited non-zero, timed out, or was unavailable."""


def docker_path() -> str | None:
    """Return the resolved ``docker`` executable, or None when it is absent."""
    return shutil.which(os.getenv("VULNORAIQ_DOCKER_BINARY", "docker"))


def docker_available() -> bool:
    """True when a Docker CLI exists and its engine answers ``docker info``."""
    if docker_path() is None:
        return False
    try:
        run_docker(["info", "--format", "{{.ServerVersion}}"], timeout=20)
    except DockerCommandError:
        return False
    return True


def run_docker(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    """Run ``docker <args>`` and return ``(stdout, stderr)``, both stripped.

    ``args`` must already be split into individual arguments; no shell is
    involved, so target names and user-supplied values cannot inject commands.
    """
    executable = docker_path()
    if executable is None:
        raise DockerCommandError(
            "Docker CLI not found on PATH. Install Docker Desktop / Docker Engine to use container features."
        )
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DockerCommandError(f"docker {args[0] if args else ''} timed out after {timeout}s") from exc
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        raise DockerCommandError(stderr or stdout or f"docker {' '.join(args)} failed")
    return stdout, stderr


def loopback_publish(mapping: str) -> str:
    """Force a Docker ``-p`` mapping to publish on loopback only.

    ``5000:5000`` binds 0.0.0.0, which would expose an intentionally weak
    assessment target to the whole network. Agent containers are only ever
    reached from this machine, so bare mappings are pinned to 127.0.0.1; a
    mapping that already names a bind address is left as the operator wrote it.
    """
    return mapping if mapping.count(":") >= 2 else f"127.0.0.1:{mapping}"
