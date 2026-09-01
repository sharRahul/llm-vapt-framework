"""The contract every assessment tool declares before it can be run.

Until now a module was a ``run(context, payloads) -> Finding`` and nothing else.
That is enough while every "tool" is an HTTP request VulnoraIQ makes itself, and
not nearly enough the moment a third-party binary is wrapped: there was no
declared argument schema, no availability check, no per-tool timeout, and no way
to ask what a module can actually assess before running it.

A :class:`ToolContract` states all of that up front. It is data, not behaviour --
the registry can answer "what can this assess, on this platform, with these
arguments?" without importing or executing anything.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: Where a tool's work happens. ``in_process`` is the only environment that
#: needs no external boundary; the other two must go through
#: :mod:`core.process_boundary`.
EXECUTION_ENVIRONMENTS = frozenset({"in_process", "subprocess", "container"})

#: Coarse capability names a tool may require. They are declarative: the
#: contract refuses a permission it does not know, so a typo cannot silently
#: widen what a tool is allowed to do.
KNOWN_PERMISSIONS = frozenset(
    {
        "target.invoke",  # send assessment input to the configured target
        "target.http",  # make HTTP requests to the target endpoint
        "filesystem.read",  # read files under the configured workspace
        "filesystem.write",  # write evidence/report artefacts
        "process.spawn",  # run an external executable
        "docker",  # drive the Docker CLI
        "network.egress",  # reach hosts other than the target
    }
)

#: Target types a tool can declare support for. ``*`` means "any configured
#: target"; it is what the built-in review modules use.
ANY_TARGET = "*"

_ARGUMENT_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list, tuple),
    "object": (dict,),
}


class ToolContractError(ValueError):
    """A contract is malformed, or arguments do not satisfy one."""


@dataclass(frozen=True, slots=True)
class ArgumentSpec:
    """One declared argument: its type, whether it is required, its choices."""

    type: str
    description: str = ""
    required: bool = False
    default: Any = None
    choices: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if self.type not in _ARGUMENT_TYPES:
            raise ToolContractError(
                f"unknown argument type '{self.type}'; expected one of {sorted(_ARGUMENT_TYPES)}"
            )
        if self.required and self.default is not None:
            raise ToolContractError("a required argument cannot also carry a default")

    def validate(self, name: str, value: Any) -> Any:
        expected = _ARGUMENT_TYPES[self.type]
        # bool is a subclass of int in Python; an integer argument accepting
        # True would make "count: true" silently mean 1.
        if self.type in ("integer", "number") and isinstance(value, bool):
            raise ToolContractError(f"argument '{name}' must be {self.type}, got boolean")
        if not isinstance(value, expected):
            raise ToolContractError(f"argument '{name}' must be {self.type}, got {type(value).__name__}")
        if self.choices and value not in self.choices:
            raise ToolContractError(f"argument '{name}' must be one of {list(self.choices)}")
        return value

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type, "required": self.required}
        if self.description:
            payload["description"] = self.description
        if self.default is not None:
            payload["default"] = self.default
        if self.choices:
            payload["choices"] = list(self.choices)
        return payload


@dataclass(frozen=True, slots=True)
class ToolAvailability:
    """Whether a tool can run here, and why not when it cannot."""

    available: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"available": self.available, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class ToolContract:
    """Everything the execution boundary needs to know before running a tool."""

    tool_id: str
    purpose: str
    target_types: tuple[str, ...] = (ANY_TARGET,)
    arguments: Mapping[str, ArgumentSpec] = field(default_factory=dict)
    permissions: frozenset[str] = frozenset({"target.invoke"})
    execution: str = "in_process"
    timeout_seconds: float = 120.0
    max_output_bytes: int = 1_000_000
    result_type: str = "finding"
    error_types: tuple[str, ...] = ("ToolContractError",)
    #: Platforms the tool runs on, as ``sys.platform`` values. Empty means any.
    platforms: frozenset[str] = frozenset()
    #: Executable that must exist on PATH for a subprocess tool to be usable.
    requires_executable: str = ""

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ToolContractError("tool_id cannot be empty")
        if not self.purpose.strip():
            raise ToolContractError(f"{self.tool_id}: purpose cannot be empty")
        if self.execution not in EXECUTION_ENVIRONMENTS:
            raise ToolContractError(
                f"{self.tool_id}: unknown execution environment '{self.execution}'; "
                f"expected one of {sorted(EXECUTION_ENVIRONMENTS)}"
            )
        unknown = set(self.permissions) - KNOWN_PERMISSIONS
        if unknown:
            raise ToolContractError(f"{self.tool_id}: unknown permissions {sorted(unknown)}")
        if self.timeout_seconds <= 0:
            raise ToolContractError(f"{self.tool_id}: timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ToolContractError(f"{self.tool_id}: max_output_bytes must be positive")
        if not self.target_types:
            raise ToolContractError(f"{self.tool_id}: declare at least one target type")
        if self.execution == "subprocess" and "process.spawn" not in self.permissions:
            raise ToolContractError(f"{self.tool_id}: subprocess execution requires the 'process.spawn' permission")
        if self.execution == "container" and "docker" not in self.permissions:
            raise ToolContractError(f"{self.tool_id}: container execution requires the 'docker' permission")

    def supports_target(self, target_type: str) -> bool:
        """True when this tool declares support for ``target_type``."""
        if ANY_TARGET in self.target_types:
            return True
        return str(target_type or "").strip().lower() in {item.lower() for item in self.target_types}

    def supports_platform(self, platform: str | None = None) -> bool:
        """True when this tool declares support for the running platform."""
        if not self.platforms:
            return True
        return (platform or sys.platform) in self.platforms

    def check_availability(self, platform: str | None = None) -> ToolAvailability:
        """Whether the tool could run right now, without running it."""
        if not self.supports_platform(platform):
            return ToolAvailability(False, f"not supported on {platform or sys.platform}")
        if self.requires_executable and shutil.which(self.requires_executable) is None:
            return ToolAvailability(False, f"'{self.requires_executable}' was not found on PATH")
        return ToolAvailability(True)

    def validate_arguments(self, arguments: Mapping[str, Any] | None) -> dict[str, Any]:
        """Validate and normalise ``arguments`` against the declared schema.

        Unknown keys are rejected rather than dropped: a caller passing an
        argument this tool has never heard of is wrong about the tool, and
        silently ignoring it would hide that.
        """
        supplied = dict(arguments or {})
        unknown = set(supplied) - set(self.arguments)
        if unknown:
            raise ToolContractError(f"{self.tool_id}: unknown arguments {sorted(unknown)}")
        validated: dict[str, Any] = {}
        for name, spec in self.arguments.items():
            if name in supplied:
                validated[name] = spec.validate(name, supplied[name])
            elif spec.required:
                raise ToolContractError(f"{self.tool_id}: missing required argument '{name}'")
            elif spec.default is not None:
                validated[name] = spec.default
        return validated

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "purpose": self.purpose,
            "target_types": list(self.target_types),
            "arguments": {name: spec.to_dict() for name, spec in self.arguments.items()},
            "permissions": sorted(self.permissions),
            "execution": self.execution,
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "result_type": self.result_type,
            "error_types": list(self.error_types),
            "platforms": sorted(self.platforms),
            "requires_executable": self.requires_executable,
        }


def contract_for_metadata(metadata: Any, arguments: Mapping[str, ArgumentSpec] | None = None) -> ToolContract:
    """The default contract for a built-in review module.

    The built-ins all do the same thing: send bounded payloads to the configured
    target and return one finding. Deriving their contract from the metadata they
    already declare keeps that fact in one place instead of twenty-four.
    """
    return ToolContract(
        tool_id=metadata.name,
        purpose=f"{metadata.title} ({metadata.owasp_id}) against {metadata.component}.",
        target_types=(ANY_TARGET,),
        arguments=dict(arguments or {"max_payloads": ArgumentSpec("integer", "Payloads to send.", default=5)}),
        permissions=frozenset({"target.invoke"}),
        execution="in_process",
    )
