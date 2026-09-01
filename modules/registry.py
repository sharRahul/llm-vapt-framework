from __future__ import annotations

from collections.abc import Iterable

from modules.base import AssessmentModule
from modules.contract import ToolContract, ToolContractError
from modules.production_wrapper import wrap_production_modules
from modules.starter import build_starter_modules


class ModuleRegistry:
    """Registry for built-in and future third-party assessment modules."""

    def __init__(self) -> None:
        self._modules: dict[str, AssessmentModule] = {}
        for name, module in wrap_production_modules(build_starter_modules()).items():
            self.register(name, module)

    def register(self, name: str, module: AssessmentModule) -> None:
        if not name:
            raise ValueError("Module name cannot be empty")
        if name in self._modules:
            raise ValueError(f"Module already registered: {name}")
        # A module without a usable contract cannot be run safely: nothing would
        # know its limits, its permissions, or what it can assess. Reject it at
        # registration rather than discovering it mid-scan.
        contract = getattr(module, "contract", None)
        if not isinstance(contract, ToolContract):
            raise ToolContractError(f"Module '{name}' does not declare a ToolContract")
        if contract.tool_id != name:
            raise ToolContractError(
                f"Module '{name}' declares contract id '{contract.tool_id}'; they must match"
            )
        self._modules[name] = module

    def get(self, name: str) -> AssessmentModule:
        try:
            return self._modules[name]
        except KeyError as exc:
            raise KeyError(f"Unknown assessment module: {name}") from exc

    def contract(self, name: str) -> ToolContract:
        """The declared contract for one module."""
        return self.get(name).contract

    def contracts(self) -> dict[str, ToolContract]:
        """Every declared contract, keyed by tool id."""
        return {name: module.contract for name, module in sorted(self._modules.items())}

    def names(self) -> list[str]:
        return sorted(self._modules)

    def resolve(self, names: Iterable[str]) -> list[AssessmentModule]:
        return [self.get(name) for name in names]
