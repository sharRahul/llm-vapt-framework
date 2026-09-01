"""How a template deploy reaches Docker, and what the bundled agent supports."""

from __future__ import annotations

from pathlib import Path

import pytest

from webui import agent_host


@pytest.fixture
def docker_calls(monkeypatch):
    """Capture every docker invocation instead of running one."""
    calls: list[list[str]] = []

    def fake_run_docker(args, timeout=None):  # noqa: ARG001 - signature parity
        calls.append(list(args))
        return ("container-id", "")

    monkeypatch.setattr(agent_host, "run_docker", fake_run_docker)
    monkeypatch.setattr(agent_host.AgentHost, "list_agents", lambda self: [])
    monkeypatch.setattr(agent_host.AgentHost, "ensure_network", lambda self: None)
    return calls


def _template(context: str, dockerfile: str = "Dockerfile") -> dict:
    return {
        "sample": {
            "image": "vulnoraiq/sample:local",
            "build": {"context": context, "dockerfile": dockerfile},
            "ports": ["8080:8080"],
            "env": {"LLM_PROVIDER": "ollama"},
            "targets": [{"id": "agent-sample", "config": {"name": "sample"}}],
        }
    }


def test_template_dockerfile_resolves_against_its_build_context(monkeypatch, docker_calls) -> None:
    """`-f Dockerfile <ctx>` resolved against the server's cwd, not the context.

    Every template therefore built VulnoraIQ's own root image instead of the
    agent's, and the build failed on a Dockerfile that was never meant for it.
    """
    monkeypatch.setattr(agent_host, "load_templates", lambda: _template("docker/agents/http-llm-agent"))
    agent_host.AgentHost().deploy("sample-agent", template_key="sample")

    build = next(call for call in docker_calls if call[0] == "build")
    dockerfile = Path(build[build.index("-f") + 1])
    assert dockerfile == Path("docker/agents/http-llm-agent/Dockerfile")
    assert build[-1] == "docker/agents/http-llm-agent"


def test_an_absolute_dockerfile_path_is_left_alone(monkeypatch, docker_calls, tmp_path) -> None:
    explicit = tmp_path / "Custom.Dockerfile"
    explicit.write_text("FROM scratch\n", encoding="utf-8")
    monkeypatch.setattr(agent_host, "load_templates", lambda: _template(".", str(explicit)))
    agent_host.AgentHost().deploy("sample-agent", template_key="sample")

    build = next(call for call in docker_calls if call[0] == "build")
    assert build[build.index("-f") + 1] == str(explicit)


def test_supplied_environment_overrides_the_template_default(monkeypatch, docker_calls) -> None:
    """A provider chosen in the console must beat the template's Ollama default."""
    monkeypatch.setattr(agent_host, "load_templates", lambda: _template("docker/agents/http-llm-agent"))
    agent_host.AgentHost().deploy(
        "sample-agent",
        template_key="sample",
        env={"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "secret"},
    )

    run = next(call for call in docker_calls if call[0] == "run")
    env_values = [run[index + 1] for index, item in enumerate(run) if item == "-e"]
    assert "LLM_PROVIDER=anthropic" in env_values
    assert "LLM_PROVIDER=ollama" not in env_values
    assert "LLM_API_KEY=secret" in env_values


def test_removing_an_agent_removes_the_targets_its_deploy_registered(monkeypatch, docker_calls) -> None:
    """A dead container must not be left in the target list reading "ready"."""
    deleted: list[list[str]] = []
    monkeypatch.setattr(agent_host, "load_templates", lambda: _template("."))
    monkeypatch.setattr(
        agent_host.AgentHost,
        "get_agent",
        lambda self, agent_id: {"container_id": "abc123", "id": agent_id, "image": "vulnoraiq/sample:local"},
    )

    def record(ids: list[str]) -> int:
        deleted.append(list(ids))
        return len(ids)

    monkeypatch.setattr(agent_host.runtime_targets, "delete_many", record)

    assert agent_host.AgentHost().remove("sample-agent") is True
    # Both registration paths: the custom-image naming rule and the template's
    # own declared target ids, matched through the image the container ran.
    assert deleted == [["agent-sample", "agent-sample-agent"]]


def test_removing_an_agent_that_is_not_running_changes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(agent_host.AgentHost, "get_agent", lambda self, agent_id: None)
    monkeypatch.setattr(
        agent_host.runtime_targets,
        "delete_many",
        lambda ids: pytest.fail("targets must not be deleted for an agent that was never there"),
    )
    assert agent_host.AgentHost().remove("ghost") is False


def test_the_bundled_agent_routes_every_offered_provider() -> None:
    """Every preset the console offers must reach a call path in the agent.

    Adding a preset to the console without a branch here would have deployed an
    agent that answers each assessment prompt with "Unsupported LLM_PROVIDER".
    """
    source = Path("docker/agents/http-llm-agent/app.py").read_text(encoding="utf-8")
    for provider in ("ollama", "lmstudio", "openai", "anthropic", "openrouter"):
        assert f'"{provider}"' in source, f"the bundled agent cannot serve '{provider}'"
    # Anthropic is not OpenAI-shaped; these are the parts that differ.
    assert "x-api-key" in source
    assert "anthropic-version" in source
    assert "/v1/messages" in source
