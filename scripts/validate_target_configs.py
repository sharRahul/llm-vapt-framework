"""Validate every configured target definition, including runtime targets.

Shipping no targets is the intended safe default — VulnoraIQ has no default
target, so a fresh checkout cannot assess anything until an operator says what
they are authorised to assess. That is reported, not treated as a failure. Only
an *invalid* target definition fails this check.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import runtime_targets  # noqa: E402
from integrations.target_adapters import validate_target_definition  # noqa: E402


def _configured_targets(config_path: Path) -> dict[str, dict]:
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    targets = data.get("targets") or {}
    return targets if isinstance(targets, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate configured and runtime target definitions.")
    parser.add_argument(
        "--config",
        default=str(
            Path(os.getenv("VULNORAIQ_CONFIG_DIR", "config"))
            / os.getenv("VULNORAIQ_TARGET_CONFIG", "targets.yaml")
        ),
        help="Target configuration file to validate.",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    targets = {
        **{name: ("configured", target) for name, target in _configured_targets(config_path).items()},
        **{name: ("runtime", target) for name, target in runtime_targets.load().items()},
    }

    if not targets:
        print(f"No targets configured in {config_path} or the runtime registry.")
        print("This is the expected default: VulnoraIQ ships with no target and assesses nothing until you add one.")
        return 0

    failures = 0
    for name, (source, target) in sorted(targets.items()):
        try:
            validated = validate_target_definition(name, target)
        except ValueError as exc:
            print(f"FAIL  {name} ({source}): {exc}")
            failures += 1
        else:
            print(f"ok    {name} ({source}) {validated.get('type')} -> {validated.get('base_url')}")

    print(f"\n{len(targets) - failures}/{len(targets)} target definitions are valid.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
