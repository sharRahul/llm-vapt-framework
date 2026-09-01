from __future__ import annotations

from collections.abc import Iterable

from core.cancellation import CancellationToken
from core.payload_loader import PayloadLibrary
from core.risk_scoring import score_findings
from core.types import Finding, ScanContext
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
            payloads = self.payload_library.for_module(module_name, library_names=library_names)
            findings.append(module.run(context, payloads))
        return score_findings(findings)
