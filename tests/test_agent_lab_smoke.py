from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import yaml

from webui import agent_analysis, agent_lab, server

ROOT = Path(__file__).resolve().parents[1]


def test_project_id_accepts_real_names():
    assert agent_lab.normalise_project_id("realagent") == "realagent"


def test_project_id_rejects_fixture_terms():
    for name in ["demo-agent", "mock-agent", "fake-agent", "fixture-agent"]:
        try:
            agent_lab.normalise_project_id(name)
        except ValueError:
            continue
        raise AssertionError(name)


def test_project_id_rejects_path_like_names():
    for name in ["../agent", "..\\agent", "nested/agent", "nested\\agent"]:
        try:
            agent_lab.normalise_project_id(name)
        except ValueError:
            continue
        raise AssertionError(name)


def test_agent_lab_e2e_fixtures_describe_a_healthy_and_broken_agent():
    echo = ROOT / "tests" / "fixtures" / "agents" / "echo-agent"
    broken = ROOT / "tests" / "fixtures" / "agents" / "broken-agent"

    assert (echo / "app.py").is_file()
    assert (echo / "requirements.txt").read_text(encoding="utf-8").strip() == "flask"
    assert "EXPOSE 5000" in (echo / "Dockerfile").read_text(encoding="utf-8")
    assert (broken / "Dockerfile").is_file()


def test_provider_env_maps_local_model():
    env = agent_lab._provider_env({"kind": "custom_env", "base_url": "http://localhost:9000/v1", "model": "local-model"})
    assert env["OPENAI_BASE_URL"] == "http://localhost:9000/v1"
    assert env["MODEL"] == "local-model"


def test_agent_lab_console_is_the_only_ui_and_covers_every_import_deploy_control():
    source = (ROOT / "webui" / "console" / "src" / "components" / "projects" / "ProjectImporter.tsx").read_text(
        encoding="utf-8"
    )

    assert "Import ZIP archive" in source
    assert "Refresh mapped folders" in source
    assert "Custom environment variables" in source
    assert "Container port" in source
    assert "Run baseline scan" in source
    assert "Imported projects" in source
    assert not (ROOT / "webui" / "static" / "agent-lab").exists()


def test_console_icon_only_navigation_has_accessible_labels():
    header = (ROOT / "webui" / "console" / "src" / "components" / "HeaderBar.tsx").read_text(encoding="utf-8")

    assert "aria-label={label}" in header


def test_legacy_agent_lab_path_redirects_to_projects_console():
    web = server.create_server("127.0.0.1", 0)
    thread = Thread(target=web.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", web.server_port, timeout=3)
        connection.request("GET", "/agent-lab")
        response = connection.getresponse()
        assert response.status == 302
        assert response.getheader("Location") == "/#/projects"
    finally:
        web.shutdown()
        web.server_close()
        thread.join(timeout=3)


def test_detect_endpoints_handles_bare_flask_route():
    # A bare @app.route without methods= must not crash endpoint detection
    # (regression: optional regex group returned None -> None.upper()).
    text = '@app.route("/")\n@app.route("/get", methods=["POST"])\n@app.route("/refresh")'
    endpoints = agent_analysis.detect_endpoints(text)
    pairs = {(e["method"], e["path"]) for e in endpoints}
    assert ("GET", "/") in pairs
    assert ("POST", "/get") in pairs
    assert ("GET", "/refresh") in pairs


def test_remove_deployment_resolves_identifier_and_avoids_false_success(tmp_path, monkeypatch):
    record = {
        "deployment_id": "safe-echo-agent-1700000000",
        "project_id": "safe-echo-agent",
        "container_name": "vulnoraiq-agent-lab-safe-echo-agent",
    }
    deployments_file = tmp_path / "deployments.yaml"
    deployments_file.write_text(yaml.safe_dump({"deployments": [record]}), encoding="utf-8")
    monkeypatch.setattr(agent_lab, "DEPLOYMENTS_PATH", deployments_file)
    monkeypatch.setattr(agent_lab, "_ensure_roots", lambda: None)

    state = {"exists": False}
    calls: list[list[str]] = []

    def fakerun_docker(args):
        calls.append(args)
        if args[:2] == ["ps", "-aq"]:
            return ("abc123" if state["exists"] else "", "")
        return ("", "")

    monkeypatch.setattr(agent_lab, "run_docker", fakerun_docker)

    # Resolve by deployment_id; container absent -> removed must be False and
    # no `docker rm` is issued (no false success that leaks a container).
    result = agent_lab.remove_deployment("safe-echo-agent-1700000000")
    assert result["container_name"] == "vulnoraiq-agent-lab-safe-echo-agent"
    assert result["removed"] is False
    assert not any(call[:2] == ["rm", "-f"] for call in calls)

    # Resolve by project_id; container present -> removed True and record pruned.
    deployments_file.write_text(yaml.safe_dump({"deployments": [record]}), encoding="utf-8")
    state["exists"] = True
    calls.clear()
    result = agent_lab.remove_deployment("safe-echo-agent")
    assert result["removed"] is True
    assert ["rm", "-f", "vulnoraiq-agent-lab-safe-echo-agent"] in calls
    assert agent_lab.list_deployments() == []
