from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.payload_loader import Payload
from core.types import Finding, ScanContext
from modules.contract import ToolContract


@dataclass(frozen=True, slots=True)
class ModuleMetadata:
    name: str
    owasp_id: str
    title: str
    component: str
    default_severity: str
    recommendation: str
    atlas_mapping: list[str]


class AssessmentModule(Protocol):
    metadata: ModuleMetadata

    @property
    def contract(self) -> ToolContract:
        """What this module can assess, and under what limits."""

    def run(self, context: ScanContext, payloads: list[Payload]) -> Finding:
        """Run the assessment module and return a finding."""
