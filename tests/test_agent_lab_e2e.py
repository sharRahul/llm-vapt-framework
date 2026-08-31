"""Docker-backed regression coverage for the full Agent Lab success and failure paths."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.request import urlopen

import pytest

from core import runtime_targets
from core.scanner import Scanner
from webui import agent_lab
from webui.docker_cli import docker_available, run_docker

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.docker
@pytest.mark.skipif(not docker_available(), reason="Docker Engine is not running")
def test_agent_lab_import_deploy_scan_and_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real container becomes a scannable runtime target and leaves no residue."""
    projects = tmp_path / "projects"
    deployments = tmp_path / "deployments.yaml"
    runtime_targets_path = tmp_path / "runtime_targets.yaml"
    network = f"vulnoraiq-agent-lab-e2e-{tmp_path.name[-8:]}".lower()
    monkeypatch.setattr(agent_lab, "AGENT_LAB_ROOT", tmp_path)
    monkeypatch.setattr(agent_lab, "MANAGED_PROJECTS_ROOT", projects)
    monkeypatch.setattr(agent_lab, "MOUNTED_PROJECTS_ROOT", tmp_path / "mounted")
    monkeypatch.setattr(agent_lab, "DEPLOYMENTS_PATH", deployments)
    monkeypatch.setattr(agent_lab, "DEFAULT_AGENT_NETWORK", network)
    monkeypatch.setattr(agent_lab, "HEALTH_CHECK_TIMEOUT", 3)
    monkeypatch.setenv("VULNORAIQ_RUNTIME_TARGETS_PATH", str(runtime_targets_path))
    monkeypatch.setenv("VULNORAIQ_RUN_MODE", "desktop")

    shutil.copytree(ROOT / "tests" / "fixtures" / "agents" / "echo-agent", projects / "echo-agent")
    shutil.copytree(ROOT / "tests" / "fixtures" / "agents" / "broken-agent", projects / "broken-agent")
    run_docker(["network", "create", network])
    deployment = None
    try:
        deployment = agent_lab.deploy_agent_project(
            "echo-agent",
            {"deployment_mode": "container", "ports": [5000], "target": {"type": "http_json"}},
            runtime_targets.save,
        )
        assert deployment.health_status == "healthy"
        assert deployment.endpoint_contract["method"] == "GET"
        assert deployment.endpoint_contract["path"] == "/get"
        assert deployment.target_ids and runtime_targets.load()[deployment.target_ids[0]]["endpoint_path"] == "/get"
        with urlopen(f"{deployment.base_url}/get?msg=verified", timeout=5) as response:  # noqa: S310
            assert response.read().decode("utf-8") == "verified"

        scan = Scanner(config_dir=ROOT / "config").scan(
            deployment.target_ids[0], "test_owasp_llm01_prompt_injection", authorised=True
        )
        assert scan.target_name == deployment.target_ids[0]
        assert scan.findings

        removal = agent_lab.remove_deployment(deployment.deployment_id)
        assert removal["removed"] is True
        assert removal["targets_removed"] == 1
        assert deployment.target_ids[0] not in runtime_targets.load()
        deployment = None

        with pytest.raises(RuntimeError, match="deployment aborted and container removed"):
            agent_lab.deploy_agent_project(
                "broken-agent",
                {"deployment_mode": "container", "ports": [8000], "target": {"type": "http_json"}},
                runtime_targets.save,
            )
        containers, _ = run_docker(["ps", "-aq", "--filter", "name=^vulnoraiq-agent-lab-broken-agent$"])
        assert not containers
    finally:
        if deployment is not None:
            agent_lab.remove_deployment(deployment.deployment_id)
        run_docker(["network", "rm", network])
