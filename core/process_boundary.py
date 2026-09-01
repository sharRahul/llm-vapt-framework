"""The single boundary for running an external tool declared by a contract.

Docker invocations already go through one auditable choke point
(``webui.docker_cli``). External scanners need the same treatment, and the
properties that boundary guarantees now come from the tool's own
:class:`~modules.contract.ToolContract` rather than from constants:

* commands are argument arrays -- never an interpolated shell string;
* every run is bounded by the contract's ``timeout_seconds``;
* output is truncated at the contract's ``max_output_bytes`` so a chatty tool
  cannot exhaust memory or fill an evidence file;
* the tool must be declared as ``subprocess`` and be available on this host
  before a process is spawned at all.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass

from modules.contract import ToolContract

LOGGER = logging.getLogger("vulnoraiq.process_boundary")


class ProcessBoundaryError(RuntimeError):
    """An external tool could not be run, timed out, or exited non-zero."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """What an external tool produced, already bounded by its contract."""

    tool_id: str
    exit_code: int
    stdout: str
    stderr: str
    truncated: bool
    duration_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_id": self.tool_id,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "duration_seconds": self.duration_seconds,
        }


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8", "replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", "ignore"), True


def run_contracted_tool(
    contract: ToolContract,
    args: list[str],
    check: bool = True,
    cwd: str | None = None,
) -> ProcessResult:
    """Run ``contract.requires_executable`` with ``args`` inside its contract.

    ``args`` must already be split into individual arguments; no shell is
    involved, so a target name or operator-supplied value cannot inject a
    command. Set ``check=False`` for tools whose non-zero exit is a result
    rather than a failure.
    """
    if contract.execution != "subprocess":
        raise ProcessBoundaryError(
            f"{contract.tool_id}: declared execution is '{contract.execution}', not 'subprocess'"
        )
    if not contract.requires_executable:
        raise ProcessBoundaryError(f"{contract.tool_id}: no executable is declared in the contract")
    availability = contract.check_availability()
    if not availability.available:
        raise ProcessBoundaryError(f"{contract.tool_id}: {availability.reason}")

    executable = shutil.which(contract.requires_executable)
    if executable is None:  # pragma: no cover - availability already checked
        raise ProcessBoundaryError(f"{contract.tool_id}: '{contract.requires_executable}' was not found on PATH")

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=contract.timeout_seconds,
            cwd=cwd,
            check=False,
        )
    except OSError as exc:
        raise ProcessBoundaryError(f"{contract.tool_id}: could not start '{contract.requires_executable}': {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProcessBoundaryError(
            f"{contract.tool_id}: exceeded its {contract.timeout_seconds:g}s contract timeout"
        ) from exc

    duration = time.monotonic() - started
    stdout, stdout_truncated = _truncate(completed.stdout or "", contract.max_output_bytes)
    stderr, stderr_truncated = _truncate(completed.stderr or "", contract.max_output_bytes)
    result = ProcessResult(
        tool_id=contract.tool_id,
        exit_code=completed.returncode,
        stdout=stdout.strip(),
        stderr=stderr.strip(),
        truncated=stdout_truncated or stderr_truncated,
        duration_seconds=duration,
    )
    if result.truncated:
        LOGGER.warning("%s output truncated at %d bytes", contract.tool_id, contract.max_output_bytes)
    if check and completed.returncode != 0:
        raise ProcessBoundaryError(
            f"{contract.tool_id}: exited {completed.returncode}: {result.stderr or result.stdout or 'no output'}"
        )
    return result
