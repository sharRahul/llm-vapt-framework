"""Report whether a usable Docker runtime is available for VulnoraIQ containers."""

from __future__ import annotations

import argparse
import json
import sys

from webui.docker_cli import DockerCommandError, docker_path, run_docker


def docker_report() -> dict[str, object]:
    path = docker_path()
    if path is None:
        return {
            "available": False,
            "path": None,
            "message": "Docker CLI not found on PATH. Install Docker Desktop or Docker Engine.",
        }
    try:
        version, _ = run_docker(["info", "--format", "{{.ServerVersion}}"], timeout=20)
    except DockerCommandError as exc:
        return {"available": False, "path": path, "message": f"Docker CLI found but the engine is not ready: {exc}"}
    return {"available": True, "path": path, "message": f"Docker engine {version} is ready."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether Docker is available for VulnoraIQ agent containers.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = parser.parse_args()

    report = docker_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["message"])
        if report.get("path"):
            print(f"Docker CLI: {report['path']}")
    return 0 if report["available"] else 1


if __name__ == "__main__":
    sys.exit(main())
