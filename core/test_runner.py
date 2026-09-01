from __future__ import annotations

from collections.abc import Iterable

from core.cancellation import CancellationToken
from core.payload_loader import PayloadLibrary
from core.risk_scoring import score_findings
from core.types import Finding, ScanContext
from modules.contract import ToolContractError
from modules.registry import ModuleRegistry


class TestRunner:
    """Runs assessment modules resolved from the module registry."""

    def __init__(self, registry: ModuleRegistry | None = None, payload_library: PayloadLibrary | None = None) -> None:
        self.registry = registry or ModuleRegistry()
        self.payload_library = payload_library or PayloadLibrary()

    def run_modules(
        self,
        module_names: Iterable[str],
        context: ScanContext,
        cancellation: CancellationToken | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        library_names = context.config.get("default", {}).get("payload_libraries")
        for module_name in module_names:
            # Between modules is a boundary where no request is in flight, so a
            # stop here leaves the target untouched by the remaining modules.
            if cancellation is not None:
                cancellation.raise_if_stopped()
            module = self.registry.get(module_name)
            self._enforce_contract(module, context)
            payloads = self.payload_library.for_module(module_name, library_names=library_names)
            findings.append(module.run(context, payloads))
        return score_findings(findings)

    @staticmethod
    def _enforce_contract(module, context: ScanContext) -> None:
        """Refuse to run a tool outside the contract it declares.

        A declared contract that nothing checks is documentation. This is the
        one place a module is about to run, so the availability and
        target-support claims are settled here, before any request is sent.
        """
        contract = module.contract
        availability = contract.check_availability()
        if not availability.available:
            raise ToolContractError(f"{contract.tool_id} cannot run here: {availability.reason}")
        target_config = context.config.get("targets", {}).get("targets", {}).get(context.target_name) or {}
        target_type = str(target_config.get("type", "")).strip()
        if target_type and not contract.supports_target(target_type):
            raise ToolContractError(
                f"{contract.tool_id} does not support target type '{target_type}' "
                f"(declares {list(contract.target_types)})"
            )
