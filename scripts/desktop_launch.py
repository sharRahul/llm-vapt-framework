from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WEBUI_URL = "http://127.0.0.1:8787"
HEALTH_URL = f"{WEBUI_URL}/healthz"
POLL_TIMEOUT = 120.0
POLL_INTERVAL = 2.0
DESKTOP_AGENT_NETWORK = "vulnoraiq-desktop-agent-lab"


def _set_default_env(env: dict[str, str], key: str, value: Path | str) -> None:
    env.setdefault(key, str(value))


def _prepare_desktop_environment() -> dict[str, str]:
    scan_root = ROOT / "scan-reports"
    agent_root = ROOT / "agent-lab"
    mounted_projects_root = ROOT / "projects"
    for path in [
        scan_root,
        scan_root / "reports",
        scan_root / "evidence",
        scan_root / "exports",
        agent_root,
        agent_root / "projects",
        mounted_projects_root,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    _set_default_env(env, "VULNORAIQ_RUN_MODE", "desktop")
    _set_default_env(env, "VULNORAIQ_AUTH_MODE", "local_admin")
    # Nora runs in-process on the host. "auto" offloads the GGUF to the GPU first
    # (NVIDIA/CUDA) and falls back to CPU when no GPU build is available — Desktop
    # Mode is where Nora gets the host GPU; Docker is only for sandboxed agents.
    _set_default_env(env, "VULNORAIQ_ASSISTANT_GPU_LAYERS", "auto")
    _set_default_env(env, "VULNORAIQ_HOST", "127.0.0.1")
    _set_default_env(env, "VULNORAIQ_PORT", "8787")
    _set_default_env(env, "VULNORAIQ_JOB_STORE_PATH", scan_root / "jobs.db")
    _set_default_env(env, "VULNORAIQ_WEB_OUTPUT_ROOT", scan_root / "reports")
    _set_default_env(env, "VULNORAIQ_RUNTIME_TARGETS_PATH", scan_root / "reports" / "runtime_targets.yaml")
    _set_default_env(env, "VULNORAIQ_EVIDENCE_DIR", scan_root / "evidence")
    _set_default_env(env, "VULNORAIQ_AGENT_LAB_ROOT", agent_root)
    _set_default_env(env, "VULNORAIQ_AGENT_LAB_PROJECTS_ROOT", agent_root / "projects")
    _set_default_env(env, "VULNORAIQ_AGENT_LAB_DEPLOYMENTS", agent_root / "deployments.yaml")
    _set_default_env(env, "VULNORAIQ_PROJECTS_ROOT", mounted_projects_root)
    _set_default_env(env, "VULNORAIQ_AGENT_NETWORK", DESKTOP_AGENT_NETWORK)
    return env


def _run(command: list[str], env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=env, check=check, text=True, capture_output=True)


def _check_docker() -> None:
    try:
        _run(["docker", "info"])
    except FileNotFoundError as exc:
        raise SystemExit("Docker was not found. Install Docker Desktop or make sure docker is on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Docker engine is not running."
        raise SystemExit(f"Docker Desktop / Docker Engine is not ready.\n{message}") from exc


def _ensure_docker_network(network_name: str) -> None:
    inspected = _run(["docker", "network", "inspect", network_name], check=False)
    if inspected.returncode == 0:
        return
    created = _run(["docker", "network", "create", network_name], check=False)
    if created.returncode != 0:
        detail = created.stderr.strip() or created.stdout.strip() or "unknown Docker error"
        raise SystemExit(f"Could not create Docker network {network_name}: {detail}")


def _wait_for_webui(timeout: float = POLL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(HEALTH_URL, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except (OSError, URLError):
            pass
        time.sleep(POLL_INTERVAL)
    return False


def main() -> None:
    env = _prepare_desktop_environment()
    print("============================================================")
    print(" VulnoraIQ Desktop Mode")
    print("============================================================")
    print("VulnoraIQ will run natively on this machine as a local single-user admin session.")
    print("Docker will be used only for sandboxed imported agents and local LLM/test runtimes.")
    print("No VulnoraIQ Docker container is created in Desktop Mode.")
    print(f"Reports folder: {ROOT / 'scan-reports'}")
    print(f"Agent Lab managed imports: {ROOT / 'agent-lab' / 'projects'}")
    print(f"Agent Lab mapped project folder: {ROOT / 'projects'}")
    print("Place an AI agent folder under ./projects/<agent-name>/ and click Agent Lab > Mapped folder > Refresh Projects.")
    print("")

    _check_docker()
    _ensure_docker_network(env["VULNORAIQ_AGENT_NETWORK"])

    process = subprocess.Popen(
        [sys.executable, "-m", "webui.server", "--host", "127.0.0.1", "--port", "8787"],
        cwd=ROOT,
        env=env,
    )

    def _stop(_signum: int | None = None, _frame: object | None = None) -> None:
        if process.poll() is None:
            process.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    print("Waiting for VulnoraIQ WebUI...")
    if _wait_for_webui():
        print(f"VulnoraIQ WebUI is ready: {WEBUI_URL}")
        webbrowser.open(WEBUI_URL)
    else:
        print(f"VulnoraIQ did not become ready within {int(POLL_TIMEOUT)}s. Open {WEBUI_URL} manually after checking logs.")

    try:
        process.wait()
    finally:
        if process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    main()
