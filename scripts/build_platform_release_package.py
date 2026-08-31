from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_VERSION = "0.3.0"
DEFAULT_OUTPUT_DIR = Path("dist/release")

ROOT_FILES = [
    "README.md",
    "ACCEPTABLE_USE.md",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "launch-vulnoraiq-webui.py",
    "launch-vulnoraiq-webui.bat",
    "launch-vulnoraiq-webui.command",
    "launch-vulnoraiq-webui.sh",
    "launch-vulnoraiq-docker-lab.bat",
    "launch-vulnoraiq-docker-lab.command",
    "launch-vulnoraiq-docker-lab.sh",
    "VulnoraIQ.desktop",
]

ROOT_DIRS = [
    "agent_testing",
    "benchmarks",
    "config",
    "core",
    "dashboards",
    "docs",
    "examples",
    "integrations",
    "modules",
    "payloads",
    "rag_testing",
    "reports",
    "scripts",
    "webui",
]

EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".key", ".pem"}
EXCLUDED_NAME_FRAGMENTS = (".secret", "_secret")
PLATFORMS = {"windows", "linux", "macos"}
EXECUTABLE_LAUNCHERS = {
    "launch-vulnoraiq-webui.command",
    "launch-vulnoraiq-webui.sh",
    "launch-vulnoraiq-docker-lab.command",
    "launch-vulnoraiq-docker-lab.sh",
    "VulnoraIQ.desktop",
}
PACKAGE_EXTENSIONS = {
    "windows": "zip",
    "linux": "tar.gz",
    "macos": "dmg",
}


@dataclass(frozen=True)
class ReleasePackage:
    platform: str
    version: str
    output: Path
    file_count: int


def package_extension(platform: str) -> str:
    if platform not in PACKAGE_EXTENSIONS:
        supported = ", ".join(sorted(PACKAGE_EXTENSIONS))
        raise ValueError(f"Unsupported platform {platform!r}; expected one of: {supported}")
    return PACKAGE_EXTENSIONS[platform]


def _is_generated_output(path: Path) -> bool:
    return len(path.parts) >= 2 and path.parts[0] == "reports" and path.parts[1] == "output"


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_PARTS:
        return True
    if _is_generated_output(path):
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    lowered = str(path).lower()
    if any(fragment in lowered for fragment in EXCLUDED_NAME_FRAGMENTS):
        return True
    if path.parts and path.parts[0] == "config":
        name = path.name.lower()
        return name.startswith("local") or ".local" in name
    return False


def _tracked_files() -> set[Path] | None:
    """Every file git tracks, or None when this is not a git checkout.

    Walking the filesystem picks up whatever a developer happens to have on
    disk. That is how a local `node_modules` (99 MB) and a local
    `docs/owasp-pdfs/` (66 MB) ended up inside a release package: both are
    git-ignored, and neither was on the hand-maintained exclusion list. Any
    future ignored directory would have leaked the same way, including a local
    `.env`. Git already knows exactly which files belong to the project, so ask
    it instead of maintaining a denylist that can only ever be incomplete.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return {Path(name) for name in result.stdout.split("\0") if name}


def _iter_release_files() -> list[Path]:
    tracked = _tracked_files()
    files: list[Path] = []

    def include(path: Path) -> bool:
        if not path.is_file() or _is_excluded(path):
            return False
        # Outside a git checkout (for example rebuilding from an extracted
        # package) fall back to the exclusion list alone.
        return tracked is None or path in tracked

    for raw_file in ROOT_FILES:
        path = Path(raw_file)
        if path.exists() and include(path):
            files.append(path)
    for raw_dir in ROOT_DIRS:
        path = Path(raw_dir)
        if not path.exists() or not path.is_dir():
            continue
        files.extend(item for item in sorted(path.rglob("*")) if include(item))
    return sorted(set(files), key=lambda item: item.as_posix())


def _readme_for(platform: str, version: str) -> str:
    desktop_launcher = {
        "windows": "launch-vulnoraiq-webui.bat",
        "linux": "VulnoraIQ.desktop or launch-vulnoraiq-webui.sh",
        "macos": "launch-vulnoraiq-webui.command",
    }[platform]
    desktop_terminal = {
        "windows": "launch-vulnoraiq-webui.bat",
        "linux": "./launch-vulnoraiq-webui.sh",
        "macos": "./launch-vulnoraiq-webui.command",
    }[platform]
    docker_lab_terminal = {
        "windows": "launch-vulnoraiq-docker-lab.bat",
        "linux": "./launch-vulnoraiq-docker-lab.sh",
        "macos": "./launch-vulnoraiq-docker-lab.command",
    }[platform]
    return f"""VulnoraIQ {version} {platform} release package

This package is for local/self-hosted authorised AI security assessment only.

Desktop Mode quick start
------------------------
1. Install Docker Desktop or Docker Engine with Docker Compose v2.
2. Install Python 3.10 or newer for this source-style package.
3. Extract this package to a normal writable folder.
4. Double-click: {desktop_launcher}

Desktop Mode runs VulnoraIQ on the host machine, uses Docker only for sandboxed
Agent Lab runtimes, and stores output under scan-reports/ and agent-lab/.

Terminal alternative
--------------------
Open a terminal in this extracted folder and run:

   {desktop_terminal}

Advanced Docker Lab Mode
------------------------
To run the full Compose lab with VulnoraIQ itself inside Docker, run:

   {docker_lab_terminal}

Cross-platform Python alternatives:

   python scripts/desktop_launch.py
   python scripts/bootstrap_launch.py

Security and acceptable use
---------------------------
Use VulnoraIQ only against systems you own or are explicitly authorised to assess.
See ACCEPTABLE_USE.md, SECURITY.md, and LICENSE before use.

Release verification
--------------------
When downloaded from GitHub Actions or GitHub Releases, verify SHA256SUMS.txt and
GitHub artifact attestations before use. If maintainer GPG signing secrets were
configured, also verify the .asc detached signatures.

Production/internal server mode
-------------------------------
For shared or internal-server deployments, do not expose local launcher mode.
Use vulnoraiq-web with production environment validation and auth enabled.
"""


def _write_zip_file(archive: zipfile.ZipFile, archive_path: str, data: bytes, executable: bool = False) -> None:
    info = zipfile.ZipInfo(archive_path)
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if executable else 0o644
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, data)


def _prepare_stage_dir(stage_dir: Path, release_files: list[Path], platform: str, version: str) -> None:
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    (stage_dir / "START_HERE.txt").write_text(_readme_for(platform, version), encoding="utf-8")
    for file_path in release_files:
        destination = stage_dir / file_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)
        if file_path.name in EXECUTABLE_LAUNCHERS:
            destination.chmod(0o755)


def _build_zip(output: Path, prefix: str, release_files: list[Path], platform: str, version: str) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_zip_file(archive, f"{prefix}/START_HERE.txt", _readme_for(platform, version).encode("utf-8"))
        for file_path in release_files:
            archive_name = f"{prefix}/{file_path.as_posix()}"
            executable = file_path.name in EXECUTABLE_LAUNCHERS
            _write_zip_file(archive, archive_name, file_path.read_bytes(), executable=executable)


def _build_tar_gz(output: Path, stage_dir: Path, prefix: str) -> None:
    with tarfile.open(output, "w:gz") as archive:
        archive.add(stage_dir, arcname=prefix)


def _build_dmg(output: Path, stage_dir: Path, prefix: str) -> None:
    hdiutil = shutil.which("hdiutil")
    if hdiutil is None:
        raise RuntimeError("macOS .dmg creation requires hdiutil and must run on macOS")
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "VulnoraIQ",
            "-srcfolder",
            str(stage_dir),
            "-ov",
            "-format",
            "UDZO",
            str(output),
        ],
        check=True,
    )
    if not output.exists():
        raise RuntimeError(f"hdiutil did not create expected image: {output}")


def build_platform_package(
    platform: str,
    version: str = DEFAULT_VERSION,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> ReleasePackage:
    if platform not in PLATFORMS:
        supported = ", ".join(sorted(PLATFORMS))
        raise ValueError(f"Unsupported platform {platform!r}; expected one of: {supported}")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    release_files = _iter_release_files()
    prefix = f"vulnoraiq-{version}-{platform}"
    extension = package_extension(platform)
    output = output_root / f"{prefix}.{extension}"
    stage_dir = output_root / prefix
    _prepare_stage_dir(stage_dir, release_files, platform, version)
    if platform == "windows":
        _build_zip(output, prefix, release_files, platform, version)
    elif platform == "linux":
        _build_tar_gz(output, stage_dir, prefix)
    else:
        _build_dmg(output, stage_dir, prefix)
    return ReleasePackage(platform, version, output, len(release_files) + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build VulnoraIQ platform release packages.")
    parser.add_argument("--platform", choices=sorted(PLATFORMS), action="append", required=True)
    parser.add_argument("--version", default=os.getenv("VULNORAIQ_RELEASE_VERSION", DEFAULT_VERSION))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    for platform in args.platform:
        package = build_platform_package(platform, args.version, args.output_dir)
        print(f"Built {package.output} ({package.file_count} files)")


if __name__ == "__main__":
    main()
