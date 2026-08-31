from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXCLUDES = (".env", "jobs.db", "runtime_targets", "node_modules/", ".git/")
INCLUDE = [
    "README.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "package.json",
    "docs/security/security-model.md",
    "docs/security/assurance.md",
    "docs/security/sandboxing.md",
    "docs/guides/targets.md",
    "benchmarks/fixtures/aitg/aitg_32_manifest.yaml",
    "config/attack_profiles.yaml",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/assurance/vulnoraiq-assurance-bundle.zip")
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": git(["rev-parse", "HEAD"]),
        "version": git(["describe", "--tags", "--always"]),
        "files": [],
    }
    files = manifest["files"]
    assert isinstance(files, list)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in INCLUDE:
            path = Path(name)
            if path.exists() and not any(excluded in name for excluded in EXCLUDES):
                bundle.write(path, name)
                files.append({"path": name, "sha256": sha(path), "bytes": path.stat().st_size})
        test_inventory = "\n".join(sorted(str(path) for path in Path("tests").glob("**/test*.py")))
        bundle.writestr("assurance/test_inventory.txt", test_inventory)
        bundle.writestr(
            "assurance/ci_workflows.txt",
            "\n".join(sorted(str(path) for path in Path(".github/workflows").glob("*.yml"))),
        )
        bundle.writestr(
            "assurance/repository_metadata.json",
            json.dumps({key: manifest[key] for key in ("generated_at", "commit", "version")}, indent=2),
        )
        bundle.writestr(
            "assurance/release_checklist.txt",
            Path("docs/development/release-process.md").read_text(encoding="utf-8")
            if Path("docs/development/release-process.md").exists()
            else "",
        )
        bundle.writestr("assurance/manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        bundle.writestr("assurance/checksums.sha256", "\n".join(f"{item['sha256']}  {item['path']}" for item in files))
    print(out)


if __name__ == "__main__":
    main()
