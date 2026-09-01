"""The validated route from a proposed action to an execution adapter.

The design has always assumed one path::

    proposal -> structured request -> schema validation -> target/scope
    validation -> policy validation -> execution adapter -> bounded result

Only the safe half existed: the assistant produces text for a human and has no
way to reach execution. That default is correct, but it left the pipeline
unwritten, so the first feature that lets anything *propose* an action would
have had to invent one -- and the safe version of this is much harder to add
after the fact than before.

This module is that pipeline. It is deliberately built with a refusing adapter
as the default, so the current behaviour is unchanged: a model-originated
request is parsed, schema-checked, scope-checked, and policy-checked, and is
then refused because no adapter is registered to run it. What the pipeline adds
is that every future caller has one validated route to take, and every rejection
carries the stage that produced it.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from modules.contract import ToolContract, ToolContractError

#: Who proposed the action. The origin is not decoration: a model-originated
#: request is held to stricter policy than one an operator typed.
ORIGIN_OPERATOR = "operator"
ORIGIN_MODEL = "model"
ORIGIN_SYSTEM = "system"
VALID_ORIGINS = frozenset({ORIGIN_OPERATOR, ORIGIN_MODEL, ORIGIN_SYSTEM})

#: The stages a request passes through, in order. A rejection names the stage
#: it failed at, so a caller can tell a malformed request from a denied one.
STAGES = ("schema", "scope", "policy", "execution")

#: Permissions a model-originated request may never carry, whatever adapter is
#: registered. These are the capabilities that reach beyond assessing the
#: target the operator authorised.
MODEL_DENIED_PERMISSIONS = frozenset({"process.spawn", "docker", "filesystem.write", "network.egress"})


class ToolRequestRejected(RuntimeError):
    """A request did not survive one of the validation stages."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.message = message


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """A proposed tool invocation, before any of it has been believed."""

    tool_id: str
    target: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    origin: str = ORIGIN_OPERATOR
    requested_by: str = "unknown"
    rationale: str = ""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ToolRequest:
        """Build a request from untrusted JSON-shaped input.

        Anything a model emits arrives here. The envelope is checked for shape
        only; the contract does the real argument validation in the next stage.
        """
        if not isinstance(payload, Mapping):
            raise ToolRequestRejected("schema", "request must be an object")
        tool_id = str(payload.get("tool_id") or "").strip()
        target = str(payload.get("target") or "").strip()
        if not tool_id:
            raise ToolRequestRejected("schema", "tool_id is required")
        if not target:
            raise ToolRequestRejected("schema", "target is required")
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            raise ToolRequestRejected("schema", "arguments must be an object")
        origin = str(payload.get("origin") or ORIGIN_OPERATOR).strip().lower()
        if origin not in VALID_ORIGINS:
            raise ToolRequestRejected("schema", f"origin must be one of {sorted(VALID_ORIGINS)}")
        return cls(
            tool_id=tool_id,
            target=target,
            arguments=dict(arguments),
            origin=origin,
            requested_by=str(payload.get("requested_by") or "unknown"),
            rationale=str(payload.get("rationale") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_id": self.tool_id,
            "target": self.target,
            "arguments": dict(self.arguments),
            "origin": self.origin,
            "requested_by": self.requested_by,
            "rationale": self.rationale,
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True, slots=True)
class ValidatedToolRequest:
    """A request that survived schema, scope, and policy validation."""

    request: ToolRequest
    contract: ToolContract
    arguments: Mapping[str, Any]
    target_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.request.to_dict(),
            "validated_arguments": dict(self.arguments),
            "target_type": self.target_type,
            "contract": self.contract.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """What an adapter produced, always attributable to its request."""

    request_id: str
    tool_id: str
    status: str
    detail: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_id": self.tool_id,
            "status": self.status,
            "detail": self.detail,
            "data": dict(self.data),
        }


class ToolExecutionAdapter(Protocol):
    """The only thing allowed to act on a validated request."""

    def execute(self, request: ValidatedToolRequest) -> ToolExecutionResult:
        """Run the validated request and return a bounded result."""


class RefusingAdapter:
    """The default adapter: validates everything, executes nothing.

    VulnoraIQ has no feature that should execute a proposed action yet, and a
    model that can run commands is a stated non-goal. Keeping the refusal as an
    *adapter* rather than as a missing pipeline means the boundary is explicit
    and testable, and swapping it later is a deliberate, reviewable change.
    """

    def execute(self, request: ValidatedToolRequest) -> ToolExecutionResult:
        return ToolExecutionResult(
            request_id=request.request.request_id,
            tool_id=request.contract.tool_id,
            status="refused",
            detail="No execution adapter is registered. Proposed actions are surfaced for human review only.",
        )


def validate_schema(request: ToolRequest, contract: ToolContract) -> Mapping[str, Any]:
    """Stage 1 -- the arguments must satisfy the tool's declared schema."""
    try:
        return contract.validate_arguments(request.arguments)
    except ToolContractError as exc:
        raise ToolRequestRejected("schema", str(exc)) from exc


def validate_scope(request: ToolRequest, contract: ToolContract, targets: Mapping[str, Any]) -> str:
    """Stage 2 -- the target must exist, be in scope, and be a supported type."""
    target_config = targets.get(request.target)
    if not isinstance(target_config, Mapping):
        raise ToolRequestRejected("scope", f"unknown target '{request.target}'")
    target_type = str(target_config.get("type", "")).strip()
    if target_type and not contract.supports_target(target_type):
        raise ToolRequestRejected(
            "scope",
            f"{contract.tool_id} does not support target type '{target_type}'",
        )
    availability = contract.check_availability()
    if not availability.available:
        raise ToolRequestRejected("scope", f"{contract.tool_id} cannot run here: {availability.reason}")
    return target_type


def validate_policy(request: ToolRequest, contract: ToolContract, authorised: bool) -> None:
    """Stage 3 -- authorisation and origin limits, before any adapter is asked."""
    if not authorised:
        raise ToolRequestRejected(
            "policy",
            "the target is not marked as authorised for assessment",
        )
    if request.origin == ORIGIN_MODEL:
        denied = sorted(set(contract.permissions) & MODEL_DENIED_PERMISSIONS)
        if denied:
            raise ToolRequestRejected(
                "policy",
                f"a model-originated request may not carry {denied}",
            )
        if contract.execution != "in_process":
            raise ToolRequestRejected(
                "policy",
                f"a model-originated request may not use '{contract.execution}' execution",
            )
        if not request.rationale.strip():
            raise ToolRequestRejected("policy", "a model-originated request must state a rationale")


def dispatch(
    payload: Mapping[str, Any],
    contracts: Mapping[str, ToolContract],
    targets: Mapping[str, Any],
    authorised: bool = False,
    adapter: ToolExecutionAdapter | None = None,
) -> ToolExecutionResult:
    """Run the whole chain for one proposed action.

    Every rejection raises :class:`ToolRequestRejected` carrying the stage that
    refused it, so a caller can report "the arguments were wrong" separately
    from "policy said no".
    """
    request = ToolRequest.from_payload(payload)
    contract = contracts.get(request.tool_id)
    if contract is None:
        raise ToolRequestRejected("schema", f"unknown tool '{request.tool_id}'")
    arguments = validate_schema(request, contract)
    target_type = validate_scope(request, contract, targets)
    validate_policy(request, contract, authorised)
    validated = ValidatedToolRequest(request, contract, arguments, target_type)
    return (adapter or RefusingAdapter()).execute(validated)
