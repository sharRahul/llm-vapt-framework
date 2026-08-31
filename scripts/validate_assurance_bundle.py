from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REQUIRED = {
    "assurance/manifest.json",
    "assurance/checksums.sha256",
    "assurance/test_inventory.txt",
    "assurance/repository_metadata.json",
    "docs/security/security-model.md",
    "docs/security/assurance.md",
    "docs/guides/targets.md",
    "benchmarks/fixtures/aitg/aitg_32_manifest.yaml",
}
FORBIDDEN = ("independently certified", "externally assured", "guaranteed vulnerability detection")


def main() -> int:
    out = Path("dist/assurance/vulnoraiq-assurance-bundle.zip")
    subprocess.check_call([sys.executable, "scripts/build_assurance_bundle.py", "--output", str(out)])
    with zipfile.ZipFile(out) as bundle:
        names = set(bundle.namelist())
        missing = REQUIRED - names
        excluded = [name for name in names if ".env" in name or "runtime_targets" in name or name.endswith("jobs.db")]
        text = "\n".join(
            bundle.read(name).decode("utf-8", "ignore").lower()
            for name in names
            if name.endswith((".md", ".txt", ".json"))
        )
    overclaims = [wording for wording in FORBIDDEN if wording in text]
    if missing or excluded or overclaims:
        print({"missing": sorted(missing), "excluded_present": excluded, "overclaims": overclaims})
        return 1
    print("Assurance bundle validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
