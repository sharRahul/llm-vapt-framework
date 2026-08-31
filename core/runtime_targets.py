"""The runtime target registry: targets created at run time, not shipped in config.

Agent Lab and the WebUI register scan targets while VulnoraIQ is running. Those
targets live in one YAML document, separate from the committed
``config/targets.yaml``, and both the API layer and the scanner read them from
here so a target means the same thing everywhere.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from integrations.target_adapters import validate_target_definition

#: Runtime target ids are used in URLs and as YAML keys, so they stay conservative.
TARGET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")


def registry_path() -> Path:
    """Resolve the registry location from the environment, honouring overrides."""
    explicit = os.getenv("VULNORAIQ_RUNTIME_TARGETS_PATH")
    if explicit:
        return Path(explicit)
    output_root = Path(os.getenv("VULNORAIQ_WEB_OUTPUT_ROOT", "reports/output/webui"))
    return output_root / "runtime_targets.yaml"


def load() -> dict[str, dict[str, Any]]:
    """Return every registered runtime target, keyed by target id."""
    path = registry_path()
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    targets = data.get("targets") or {}
    if not isinstance(targets, dict):
        return {}
    return {str(name): target for name, target in targets.items() if isinstance(target, dict)}


def save(target_id: str, target: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist one runtime target.

    The definition goes through the same validation as a configured target, so a
    runtime-registered target can never bypass target-type, URL, or scope rules.
    """
    safe_id = target_id.strip()
    if not TARGET_ID_RE.fullmatch(safe_id):
        raise ValueError(
            "target id must be 2-81 chars and contain only letters, numbers, hyphens, or underscores"
        )
    validated = validate_target_definition(safe_id, target)
    targets = load()
    targets[safe_id] = validated
    _write(targets)
    return {"target_id": safe_id, "target": validated}


def delete(target_id: str) -> bool:
    """Remove one runtime target. Returns False when it was not registered."""
    targets = load()
    if target_id not in targets:
        return False
    del targets[target_id]
    _write(targets)
    return True


def delete_many(target_ids: list[str]) -> int:
    """Remove several runtime targets in one write. Returns the number removed."""
    targets = load()
    removed = [tid for tid in target_ids if targets.pop(tid, None) is not None]
    if removed:
        _write(targets)
    return len(removed)


def merge_into(configured: dict[str, Any]) -> dict[str, Any]:
    """Overlay runtime targets onto configured ones, runtime winning on conflict."""
    return {**configured, **load()}


def _write(targets: dict[str, dict[str, Any]]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"targets": targets}, sort_keys=True), encoding="utf-8")
