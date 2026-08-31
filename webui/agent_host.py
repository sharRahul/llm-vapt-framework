from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from webui.docker_cli import DockerCommandError, loopback_publish, run_docker

LOGGER = logging.getLogger("vulnoraiq.webui.agent_host")
CONFIG_ROOT = Path(os.getenv("VULNORAIQ_CONFIG_DIR", "config"))
TEMPLATES_PATH = CONFIG_ROOT / "agent_templates.yaml"
AGENT_LABEL = "vulnoraiq.agent"
AGENT_NETWORK = os.getenv("VULNORAIQ_AGENT_NETWORK", "vulnoraiq_vulnoraiq-lab")


def _container_name(agent_id: str) -> str:
    return f"vulnoraiq-agent-{agent_id}"


def load_templates() -> dict[str, Any]:
    if not TEMPLATES_PATH.exists():
        return {}
    data = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8")) or {}
    return data.get("templates", {})


def save_template(key: str, template: dict[str, Any]) -> dict[str, Any]:
    """Persist a deployable agent template to config/agent_templates.yaml."""
    data: dict[str, Any] = {}
    if TEMPLATES_PATH.exists():
        data = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8")) or {}
    templates = data.setdefault("templates", {})
    templates[key] = template
    TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_PATH.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return template


def delete_template(key: str) -> bool:
    if not TEMPLATES_PATH.exists():
        return False
    data = yaml.safe_load(TEMPLATES_PATH.read_text(encoding="utf-8")) or {}
    templates = data.get("templates", {})
    if key not in templates:
        return False
    del templates[key]
    TEMPLATES_PATH.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return True


class AgentHost:
    def list_agents(self) -> list[dict[str, Any]]:
        try:
            out, _ = run_docker(
                ["ps", "-a", "--filter", f"label={AGENT_LABEL}", "--format", "{{.ID}}\t{{.Label \"vulnoraiq.agent.id\"}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
            )
            if not out:
                return []
            agents = []
            for line in out.split("\n"):
                parts = line.strip().split("\t")
                if len(parts) >= 4:
                    agents.append({
                        "container_id": parts[0],
                        "id": parts[1],
                        "image": parts[2],
                        "status": parts[3],
                        "ports": parts[4] if len(parts) > 4 else "",
                    })
            return agents
        except DockerCommandError as exc:
            LOGGER.warning("Failed to list agents: %s", exc)
            return []

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        for agent in self.list_agents():
            if agent["id"] == agent_id:
                return agent
        return None

    def deploy(self, agent_id: str, template_key: str | None = None, image: str | None = None, env: dict[str, str] | None = None, port: int | None = None) -> dict[str, Any]:
        name = _container_name(agent_id)
        existing = self.get_agent(agent_id)
        if existing:
            raise ValueError(f"Agent '{agent_id}' is already running (container {existing['container_id']})")

        templates = load_templates()
        if template_key and template_key in templates:
            tmpl = templates[template_key]
            image_name = tmpl.get("image", image or "")
            build = tmpl.get("build")
            ports = tmpl.get("ports", [])
            default_env = dict(tmpl.get("env", {}))
            if env:
                default_env.update(env)
            env = default_env
            if build:
                ctx = build.get("context", ".")
                df = build.get("dockerfile", "Dockerfile")
                LOGGER.info("Building image %s from %s", image_name, ctx)
                run_docker(["build", "-t", image_name, "-f", df, ctx])
        else:
            if not image:
                raise ValueError("Either template_key or image must be provided")
            image_name = image
            # Publish the agent's port so VulnoraIQ can reach it at
            # 127.0.0.1:<port> and register it as a scannable target.
            ports = [f"{port}:{port}"] if port else []

        cmd = [
            "run",
            "-d",
            "--name",
            name,
            "--label",
            f"{AGENT_LABEL}={agent_id}",
            "--label",
            f"vulnoraiq.agent.id={agent_id}",
            "--network",
            AGENT_NETWORK,
            # Assessment targets are untrusted by definition: drop every Linux
            # capability and block privilege escalation inside the container.
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
        ]
        for p in ports:
            cmd += ["-p", loopback_publish(str(p))]
        if env:
            for k, v in env.items():
                if v:
                    cmd += ["-e", f"{k}={v}"]
        cmd.append(image_name)
        try:
            out, _ = run_docker(cmd)
        except DockerCommandError as exc:
            raise DockerCommandError(f"Failed to deploy agent '{agent_id}': {exc}") from exc

        container_id = out.strip()
        return {"container_id": container_id, "agent_id": agent_id, "name": name, "image": image_name, "status": "deployed", "port": port}

    def stop(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        run_docker(["stop", agent["container_id"]])
        return True

    def start(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        run_docker(["start", agent["container_id"]])
        return True

    def remove(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        try:
            run_docker(["rm", "-f", agent["container_id"]])
        except DockerCommandError:
            pass
        return True

    def logs(self, agent_id: str, tail: int = 50) -> str:
        agent = self.get_agent(agent_id)
        if not agent:
            return ""
        out, _ = run_docker(["logs", "--tail", str(tail), agent["container_id"]])
        return out

    def ensure_network(self) -> None:
        try:
            run_docker(["network", "inspect", AGENT_NETWORK])
        except DockerCommandError:
            LOGGER.info("Creating network %s", AGENT_NETWORK)
            run_docker(["network", "create", AGENT_NETWORK])


_HOST = AgentHost()


def list_agents() -> list[dict[str, Any]]:
    return _HOST.list_agents()


def get_agent(agent_id: str) -> dict[str, Any] | None:
    return _HOST.get_agent(agent_id)


def deploy_agent(agent_id: str, template_key: str | None = None, image: str | None = None, env: dict[str, str] | None = None, port: int | None = None) -> dict[str, Any]:
    _HOST.ensure_network()
    return _HOST.deploy(agent_id, template_key, image, env, port)


def stop_agent(agent_id: str) -> bool:
    return _HOST.stop(agent_id)


def start_agent(agent_id: str) -> bool:
    return _HOST.start(agent_id)


def remove_agent(agent_id: str) -> bool:
    return _HOST.remove(agent_id)


def agent_logs(agent_id: str, tail: int = 50) -> str:
    return _HOST.logs(agent_id, tail)


def list_templates() -> dict[str, Any]:
    return load_templates()


def template_targets(template_key: str) -> list[dict[str, Any]]:
    templates = load_templates()
    tmpl = templates.get(template_key, {})
    return tmpl.get("targets", [])
