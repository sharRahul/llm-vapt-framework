"""The tool/scanner contract, its enforcement, and the tool-request pipeline."""

from __future__ import annotations

import sys

import pytest

from core.process_boundary import ProcessBoundaryError, run_contracted_tool
from core.test_runner import TestRunner as AssessmentRunner
from core.tool_request import (
    MODEL_DENIED_PERMISSIONS,
    RefusingAdapter,
    ToolExecutionResult,
    ToolRequestRejected,
    dispatch,
)
from core.types import ScanContext
from modules.contract import ANY_TARGET, ArgumentSpec, ToolContract, ToolContractError
from modules.registry import ModuleRegistry

# -- The contract itself ------------------------------------------------------


def test_every_built_in_module_declares_a_matching_contract() -> None:
    registry = ModuleRegistry()
    contracts = registry.contracts()
    assert set(contracts) == set(registry.names())
    for name, contract in contracts.items():
        assert contract.tool_id == name
        assert contract.purpose
        assert contract.execution == "in_process"
        assert contract.timeout_seconds > 0
        assert contract.max_output_bytes > 0
        assert contract.check_availability().available


def test_registry_refuses_a_module_without_a_contract() -> None:
    class Contractless:
        metadata = None

        def run(self, context, payloads):  # pragma: no cover - never reached
            raise AssertionError

    # Deliberately not an AssessmentModule: that is what is being rejected.
    with pytest.raises(ToolContractError):
        ModuleRegistry().register("contractless", Contractless())  # type: ignore[arg-type]


def test_registry_refuses_a_contract_registered_under_another_name() -> None:
    class Mismatched:
        contract = ToolContract("declared_id", "purpose")

        def run(self, context, payloads):  # pragma: no cover - never reached
            raise AssertionError

    with pytest.raises(ToolContractError, match="declared_id"):
        ModuleRegistry().register("registered_id", Mismatched())  # type: ignore[arg-type]


def test_argument_schema_validates_types_defaults_and_unknown_keys() -> None:
    contract = ToolContract(
        "example",
        "an example tool",
        arguments={
            "mode": ArgumentSpec("string", required=True, choices=("fast", "full")),
            "depth": ArgumentSpec("integer", default=3),
        },
    )
    assert contract.validate_arguments({"mode": "fast"}) == {"mode": "fast", "depth": 3}
    with pytest.raises(ToolContractError, match="missing required argument"):
        contract.validate_arguments({})
    with pytest.raises(ToolContractError, match="must be one of"):
        contract.validate_arguments({"mode": "sideways"})
    with pytest.raises(ToolContractError, match="unknown arguments"):
        contract.validate_arguments({"mode": "fast", "surprise": 1})
    # bool is an int subclass; an integer argument must not silently accept it.
    with pytest.raises(ToolContractError, match="got boolean"):
        contract.validate_arguments({"mode": "fast", "depth": True})


def test_contract_rejects_execution_without_the_matching_permission() -> None:
    with pytest.raises(ToolContractError, match="process.spawn"):
        ToolContract("spawner", "runs a binary", execution="subprocess")
    with pytest.raises(ToolContractError, match="docker"):
        ToolContract("boxed", "runs a container", execution="container")
    with pytest.raises(ToolContractError, match="unknown permissions"):
        ToolContract("typo", "a typo", permissions=frozenset({"filesystem.wrte"}))


def test_availability_reports_platform_and_missing_executable() -> None:
    other_platform = "aix" if sys.platform != "aix" else "win32"
    wrong_platform = ToolContract("elsewhere", "not here", platforms=frozenset({other_platform}))
    assert not wrong_platform.check_availability().available

    missing = ToolContract(
        "absent",
        "needs a binary",
        execution="subprocess",
        permissions=frozenset({"process.spawn"}),
        requires_executable="vulnoraiq-tool-that-does-not-exist",
    )
    availability = missing.check_availability()
    assert not availability.available
    assert "not found on PATH" in availability.reason


def test_supports_target_honours_the_wildcard_and_the_declared_list() -> None:
    anything = ToolContract("any", "any target", target_types=(ANY_TARGET,))
    assert anything.supports_target("http_api")
    narrow = ToolContract("narrow", "http only", target_types=("http_api",))
    assert narrow.supports_target("HTTP_API")
    assert not narrow.supports_target("test_fixture")


# -- Enforcement at the point of running --------------------------------------


def test_runner_refuses_a_target_type_the_module_does_not_support() -> None:
    runner = AssessmentRunner()
    module_name = runner.registry.names()[0]
    module = runner.registry.get(module_name)
    narrow = ToolContract(module_name, "http only", target_types=("http_api",))

    class Narrowed:
        metadata = module.metadata
        contract = narrow

        def run(self, context, payloads):  # pragma: no cover - must not be reached
            raise AssertionError("the contract check should have stopped this")

    runner.registry._modules[module_name] = Narrowed()  # noqa: SLF001 - test seam
    context = ScanContext(
        target_name="fixture",
        profile_name="baseline",
        config={"targets": {"targets": {"fixture": {"type": "test_fixture"}}}},
    )
    with pytest.raises(ToolContractError, match="does not support target type"):
        runner.run_modules([module_name], context)


# -- The external-process boundary --------------------------------------------


def test_process_boundary_refuses_a_tool_not_declared_as_a_subprocess() -> None:
    contract = ToolContract("in_proc", "runs in process")
    with pytest.raises(ProcessBoundaryError, match="not 'subprocess'"):
        run_contracted_tool(contract, ["--version"])


def test_process_boundary_refuses_an_unavailable_executable() -> None:
    contract = ToolContract(
        "absent",
        "needs a binary",
        execution="subprocess",
        permissions=frozenset({"process.spawn"}),
        requires_executable="vulnoraiq-tool-that-does-not-exist",
    )
    with pytest.raises(ProcessBoundaryError, match="not found on PATH"):
        run_contracted_tool(contract, ["--version"])


def test_process_boundary_runs_and_truncates_at_the_contract_limit() -> None:
    contract = ToolContract(
        "python",
        "the interpreter, as a stand-in for any wrapped scanner",
        execution="subprocess",
        permissions=frozenset({"process.spawn"}),
        requires_executable=sys.executable,
        max_output_bytes=16,
        timeout_seconds=60,
    )
    result = run_contracted_tool(contract, ["-c", "print('x' * 200)"])
    assert result.exit_code == 0
    assert result.truncated
    assert len(result.stdout.encode("utf-8")) <= 16


def test_process_boundary_surfaces_a_non_zero_exit() -> None:
    contract = ToolContract(
        "python",
        "the interpreter",
        execution="subprocess",
        permissions=frozenset({"process.spawn"}),
        requires_executable=sys.executable,
        timeout_seconds=60,
    )
    with pytest.raises(ProcessBoundaryError, match="exited 3"):
        run_contracted_tool(contract, ["-c", "raise SystemExit(3)"])
    # The same run is a result, not a failure, when the caller says so.
    assert run_contracted_tool(contract, ["-c", "raise SystemExit(3)"], check=False).exit_code == 3


def test_process_boundary_enforces_the_contract_timeout() -> None:
    contract = ToolContract(
        "python",
        "the interpreter",
        execution="subprocess",
        permissions=frozenset({"process.spawn"}),
        requires_executable=sys.executable,
        timeout_seconds=0.5,
    )
    with pytest.raises(ProcessBoundaryError, match="contract timeout"):
        run_contracted_tool(contract, ["-c", "import time; time.sleep(10)"])


# -- The structured tool-request pipeline -------------------------------------


CONTRACTS = ModuleRegistry().contracts()
TARGETS = {"authorised-agent": {"type": "http_api"}}


def _payload(**overrides):
    payload = {
        "tool_id": "rag_poisoning",
        "target": "authorised-agent",
        "origin": "operator",
        "requested_by": "tester",
    }
    payload.update(overrides)
    return payload


def test_a_valid_request_reaches_the_adapter_and_is_refused_by_default() -> None:
    result = dispatch(_payload(), CONTRACTS, TARGETS, authorised=True)
    assert result.status == "refused"
    assert result.tool_id == "rag_poisoning"


def test_a_registered_adapter_receives_the_validated_request() -> None:
    seen: list[str] = []

    class RecordingAdapter:
        def execute(self, request) -> ToolExecutionResult:
            seen.append(request.target_type)
            return ToolExecutionResult(request.request.request_id, request.contract.tool_id, "ok")

    result = dispatch(_payload(), CONTRACTS, TARGETS, authorised=True, adapter=RecordingAdapter())
    assert result.status == "ok"
    assert seen == ["http_api"]


@pytest.mark.parametrize(
    ("payload", "stage", "fragment"),
    [
        ({"target": "authorised-agent"}, "schema", "tool_id is required"),
        ({"tool_id": "rag_poisoning"}, "schema", "target is required"),
        (_payload(tool_id="not_a_tool"), "schema", "unknown tool"),
        (_payload(arguments={"max_payloads": "many"}), "schema", "must be integer"),
        (_payload(arguments=["not", "an", "object"]), "schema", "arguments must be an object"),
        (_payload(origin="sideways"), "schema", "origin must be one of"),
        (_payload(target="unregistered"), "scope", "unknown target"),
    ],
)
def test_rejections_name_the_stage_that_refused_them(payload, stage, fragment) -> None:
    with pytest.raises(ToolRequestRejected) as exc:
        dispatch(payload, CONTRACTS, TARGETS, authorised=True)
    assert exc.value.stage == stage
    assert fragment in exc.value.message


def test_an_unauthorised_target_is_refused_by_policy() -> None:
    with pytest.raises(ToolRequestRejected) as exc:
        dispatch(_payload(), CONTRACTS, TARGETS, authorised=False)
    assert exc.value.stage == "policy"


def test_a_model_request_needs_a_rationale_and_cannot_reach_beyond_the_target() -> None:
    with pytest.raises(ToolRequestRejected, match="rationale"):
        dispatch(_payload(origin="model"), CONTRACTS, TARGETS, authorised=True)

    spawning = {
        "shell_tool": ToolContract(
            "shell_tool",
            "runs a binary",
            execution="subprocess",
            permissions=frozenset({"process.spawn"}),
            requires_executable=sys.executable,
        )
    }
    with pytest.raises(ToolRequestRejected) as exc:
        dispatch(
            _payload(tool_id="shell_tool", origin="model", rationale="because"),
            spawning,
            TARGETS,
            authorised=True,
        )
    assert exc.value.stage == "policy"
    assert "process.spawn" in exc.value.message
    assert "process.spawn" in MODEL_DENIED_PERMISSIONS


def test_the_default_adapter_never_executes_anything() -> None:
    """The refusal is the product decision, so it is asserted, not assumed."""
    assert isinstance(RefusingAdapter(), object)
    result = dispatch(_payload(), CONTRACTS, TARGETS, authorised=True, adapter=RefusingAdapter())
    assert result.status == "refused"
    assert result.data == {}
