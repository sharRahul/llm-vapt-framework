from __future__ import annotations

import tarfile
from pathlib import Path

from scripts.build_platform_release_package import build_platform_package, package_extension


def test_build_linux_platform_release_package_creates_tar_gz_archive(tmp_path: Path) -> None:
    package = build_platform_package("linux", version="0.2.0-test", output_dir=tmp_path)

    assert package.output.exists()
    assert package.output.name == "vulnoraiq-0.2.0-test-linux.tar.gz"
    assert package.file_count > 1
    assert package_extension("windows") == "zip"
    assert package_extension("linux") == "tar.gz"
    assert package_extension("macos") == "dmg"

    with tarfile.open(package.output, "r:gz") as archive:
        names = set(archive.getnames())

    prefix = "vulnoraiq-0.2.0-test-linux/"
    assert f"{prefix}START_HERE.txt" in names
    assert f"{prefix}README.md" in names
    assert f"{prefix}ACCEPTABLE_USE.md" in names
    assert f"{prefix}LICENSE" in names
    assert f"{prefix}launch-vulnoraiq-webui.py" in names
    assert f"{prefix}launch-vulnoraiq-webui.sh" in names
    assert f"{prefix}config/targets.yaml" in names
    assert f"{prefix}examples/local_demo_targets/owasp_fixture_targets.py" in names
    assert f"{prefix}webui/static/console/index.html" in names
    assert all("reports/output" not in name for name in names)
    assert all("__pycache__" not in name for name in names)


def test_release_package_never_ships_git_ignored_content() -> None:
    """A release package must contain only files the project actually tracks.

    Selection used to walk the filesystem against a hand-maintained deny list.
    A developer's git-ignored `webui/console/node_modules` (99 MB) and
    `docs/owasp-pdfs/` (66 MB) were both copied into the artifact, and any
    future ignored directory - a local `.env` included - would have leaked the
    same way.
    """
    from scripts.build_platform_release_package import _iter_release_files, _tracked_files

    tracked = _tracked_files()
    assert tracked is not None, "this test must run inside a git checkout"

    selected = _iter_release_files()
    assert selected, "the packager selected no files at all"

    untracked = [path for path in selected if path not in tracked]
    assert untracked == [], f"release package would ship untracked files: {untracked[:10]}"

    # Match ignored roots by prefix. A bare component check would wrongly flag
    # webui/static/agent-lab/, which is tracked and does ship.
    forbidden_prefixes = (
        "node_modules/",
        "docs/owasp-pdfs/",
        "scan-reports/",
        "agent-lab/",
        ".venv/",
        "model/",
        "reports/output/",
    )
    leaked = [
        p
        for p in selected
        if "node_modules" in p.parts or p.as_posix().startswith(forbidden_prefixes)
    ]
    assert leaked == [], f"release package would ship ignored directories: {leaked[:10]}"
    assert not [p for p in selected if p.name.startswith(".env")], "release package would ship an env file"


def test_release_package_still_contains_what_it_needs() -> None:
    from scripts.build_platform_release_package import _iter_release_files

    selected = {path.as_posix() for path in _iter_release_files()}

    for required in (
        "README.md",
        "pyproject.toml",
        "config/targets.yaml",
        "config/environment.template",
        "core/scanner.py",
        "webui/server.py",
        "docs/README.md",
    ):
        assert required in selected, f"release package is missing {required}"

    assert any(p.startswith("webui/static/console/") for p in selected), "the built console must ship"
