"""Tests for Agent Lab "deploy any agent -> working scannable target".

Covers the pieces added so that importing/deploying an agent auto-produces a
scan target matching the agent's real HTTP contract (GET/query + text as well
as POST/JSON), on a free host port, with a run-mode-aware base URL, plus the
external endpoint deployment mode.
"""

from __future__ import annotations

import re
import socket

import pytest

from webui import agent_lab

AIRA_SOURCE = '''
# FILE: app.py
from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def index():
    return "AIRA chatbot"


@app.route("/health")
def health():
    return "ok"


@app.route("/get")
def get_bot_response():
    user_text = request.args.get("msg")
    return str(english_bot.get_response(user_text))
'''

FASTAPI_SOURCE = '''
# FILE: main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/chat")
def chat(body: dict):
    prompt = body["prompt"]
    return {"response": generate(prompt)}
'''


# --- endpoint detection + ranking -------------------------------------------------


def test_detect_endpoints_recovers_aira_get_query_text_contract():
    endpoints = agent_lab._detect_endpoints(AIRA_SOURCE)
    by_path = {e["path"]: e for e in endpoints}
    get = by_path["/get"]
    assert get["method"] == "GET"
    assert get["param_style"] == "query"
    assert get["param_key"] == "msg"
    assert get["response_shape"] == "text"


def test_detect_endpoints_recovers_fastapi_post_json_contract():
    endpoints = agent_lab._detect_endpoints(FASTAPI_SOURCE)
    chat = {e["path"]: e for e in endpoints}["/chat"]
    assert chat["method"] == "POST"
    assert chat["param_style"] == "json"
    assert chat["param_key"] == "prompt"
    assert chat["response_shape"] == "json"
    assert chat["response_path"] == "response"


def test_select_inference_endpoint_skips_health_and_root_for_aira():
    endpoints = agent_lab._detect_endpoints(AIRA_SOURCE)
    selected = agent_lab.select_inference_endpoint(endpoints)
    assert selected is not None
    assert selected["path"] == "/get"


def test_select_inference_endpoint_prefers_chat_over_infra():
    endpoints = agent_lab._detect_endpoints(FASTAPI_SOURCE)
    selected = agent_lab.select_inference_endpoint(endpoints)
    assert selected["path"] == "/chat"


def test_select_inference_endpoint_none_for_empty():
    assert agent_lab.select_inference_endpoint([]) is None


def test_analyze_exposes_selected_endpoint(tmp_path, monkeypatch):
    # analyze_agent_project must publish the authoritative selected endpoint so
    # the WebUI preview matches what the deploy path registers.
    proj = tmp_path / "projects" / "aira"
    proj.mkdir(parents=True)
    (proj / "app.py").write_text(AIRA_SOURCE, encoding="utf-8")
    monkeypatch.setattr(agent_lab, "MANAGED_PROJECTS_ROOT", proj.parent)
    monkeypatch.setattr(agent_lab, "MOUNTED_PROJECTS_ROOT", tmp_path / "none")
    info = agent_lab.analyze_agent_project("aira")
    assert info["selected_endpoint"] is not None
    assert info["selected_endpoint"]["path"] == "/get"
    assert info["selected_endpoint"]["method"] == "GET"
    assert info["selected_endpoint"]["param_key"] == "msg"


# --- contract-derived target config ----------------------------------------------


def _capture_save_fn():
    saved: dict[str, dict] = {}

    def save(target_id: str, config: dict):
        saved[target_id] = config
        return {"target_id": target_id, "config": config}

    return save, saved


def test_register_targets_builds_aira_get_text_config():
    save, saved = _capture_save_fn()
    contract = {
        "method": "GET",
        "path": "/get",
        "param_style": "query",
        "param_key": "msg",
        "response_shape": "text",
        "response_path": "",
    }
    ids = agent_lab._register_targets(
        save_target_fn=save,
        project_id="aira",
        base_url="http://127.0.0.1:5055",
        target_type="http_json",
        contract=contract,
        safety_profile="local_lab_safe",
    )
    cfg = saved[ids[0]]
    assert cfg["type"] == "http_json"
    assert cfg["method"] == "GET"
    assert cfg["endpoint_path"] == "/get"
    assert cfg["base_url"] == "http://127.0.0.1:5055"
    assert cfg["request_body_template"] == {"msg": "{{prompt}}"}
    # text response -> empty extraction path so the adapter returns the whole body
    assert cfg["response_extraction_path"] == ""


def test_register_targets_builds_post_json_config_with_detected_key():
    save, saved = _capture_save_fn()
    contract = {
        "method": "POST",
        "path": "/chat",
        "param_style": "json",
        "param_key": "prompt",
        "response_shape": "json",
        "response_path": "response",
    }
    ids = agent_lab._register_targets(
        save_target_fn=save,
        project_id="bot",
        base_url="http://bot-container:8000",
        target_type="http_json",
        contract=contract,
        safety_profile="local_lab_safe",
    )
    cfg = saved[ids[0]]
    assert cfg["method"] == "POST"
    assert cfg["request_body_template"] == {"prompt": "{{prompt}}"}
    assert cfg["response_extraction_path"] == "response"


def test_runtime_target_id_sanitises_dots_and_length():
    # Dotted project ids (allowed by PROJECT_ID_RE) must not produce an invalid
    # runtime target id that dead-ends the deploy.
    tid = agent_lab._runtime_target_id("socket.io", "http_json")
    assert tid == "agent-lab-socket-io-http-json"
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,80}", tid)
    long_tid = agent_lab._runtime_target_id("a" * 80, "chat_completions")
    assert len(long_tid) <= 81
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,80}", long_tid)


def test_register_targets_uses_sanitised_id(monkeypatch):
    save, saved = _capture_save_fn()
    ids = agent_lab._register_targets(
        save_target_fn=save,
        project_id="my.dotted.agent",
        base_url="http://127.0.0.1:9000",
        target_type="http_json",
        contract={"method": "POST", "path": "/chat", "param_key": "prompt", "response_shape": "json", "response_path": ""},
        safety_profile="local_lab_safe",
    )
    assert "." not in ids[0]
    assert ids[0] == "agent-lab-my-dotted-agent-http-json"


def test_register_targets_chat_completions_unchanged():
    save, saved = _capture_save_fn()
    ids = agent_lab._register_targets(
        save_target_fn=save,
        project_id="oai",
        base_url="http://oai:8000",
        target_type="chat_completions",
        contract={"path": "/v1/chat/completions"},
        safety_profile="local_lab_safe",
    )
    cfg = saved[ids[0]]
    assert cfg["type"] == "chat_completions"
    assert cfg["response_extraction_path"] == "choices.0.message.content"
    assert cfg["request_body_template"]["messages"][0]["content"] == "{{prompt}}"


def test_resolve_contract_prefers_explicit_override():
    info = {"endpoints": agent_lab._detect_endpoints(AIRA_SOURCE)}
    contract = agent_lab._resolve_endpoint_contract(
        info,
        {"method": "post", "endpoint_path": "/ask", "response_extraction_path": "answer"},
        "http_json",
    )
    assert contract["method"] == "POST"
    assert contract["path"] == "/ask"
    assert contract["response_path"] == "answer"
    assert contract["response_shape"] == "json"


def test_resolve_contract_uses_detected_endpoint_by_default():
    info = {"endpoints": agent_lab._detect_endpoints(AIRA_SOURCE)}
    contract = agent_lab._resolve_endpoint_contract(info, {}, "http_json")
    assert contract["path"] == "/get"
    assert contract["method"] == "GET"
    assert contract["param_key"] == "msg"
    assert contract["response_shape"] == "text"


# --- run-mode base_url + free host port ------------------------------------------


def test_running_in_container_respects_run_mode(monkeypatch):
    monkeypatch.setenv("VULNORAIQ_RUN_MODE", "desktop")
    assert agent_lab._running_in_container() is False
    monkeypatch.setenv("VULNORAIQ_RUN_MODE", "docker_lab")
    monkeypatch.setenv("VULNORAIQ_IN_CONTAINER", "1")
    assert agent_lab._running_in_container() is True


def test_free_host_port_returns_bindable_port():
    port = agent_lab._free_host_port()
    # The returned port must be immediately bindable.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
    assert 1 <= port <= 65535


def test_free_host_port_falls_back_when_preferred_taken():
    # Occupy a port, then confirm _free_host_port picks a different, free one.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        taken = busy.getsockname()[1]
        chosen = agent_lab._free_host_port(taken)
        assert chosen != taken
        assert agent_lab._port_is_free(chosen)


def test_wait_for_port_true_when_listening_and_false_when_closed():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert agent_lab._wait_for_port(f"http://127.0.0.1:{port}", timeout=2) is True
    # Socket is closed now; pick a very short timeout on a likely-free port.
    free = agent_lab._free_host_port()
    assert agent_lab._wait_for_port(f"http://127.0.0.1:{free}", timeout=1) is False


# --- external endpoint deployment mode -------------------------------------------


def test_external_deploy_registers_target_without_docker(tmp_path, monkeypatch):
    deployments_file = tmp_path / "deployments.yaml"
    monkeypatch.setattr(agent_lab, "DEPLOYMENTS_PATH", deployments_file)
    monkeypatch.setattr(agent_lab, "_ensure_roots", lambda: None)

    def fail_docker(args):  # deploying external must never touch docker
        raise AssertionError(f"docker should not be called: {args}")

    monkeypatch.setattr(agent_lab, "_run_docker", fail_docker)

    save, saved = _capture_save_fn()
    payload = {
        "deployment_mode": "external",
        "authorization_acknowledged": True,
        "base_url": "http://127.0.0.1:9000",
        "target": {
            "type": "http_json",
            "endpoint_path": "/chat",
            "method": "POST",
            "response_extraction_path": "reply",
        },
    }
    result = agent_lab.deploy_agent_project("external-agent", payload, save)
    assert result.deployment_mode == "external"
    assert result.container_id == ""
    assert result.base_url == "http://127.0.0.1:9000"
    cfg = saved[result.target_ids[0]]
    assert cfg["endpoint_path"] == "/chat"
    assert cfg["method"] == "POST"
    assert cfg["response_extraction_path"] == "reply"


def test_external_deploy_requires_authorization_ack(monkeypatch):
    save, _ = _capture_save_fn()
    payload = {"deployment_mode": "external", "base_url": "http://127.0.0.1:9000"}
    with pytest.raises(ValueError, match="authorization_acknowledged"):
        agent_lab.deploy_agent_project("external-agent", payload, save)


def test_external_deploy_requires_base_url(monkeypatch):
    save, _ = _capture_save_fn()
    payload = {"deployment_mode": "external", "authorization_acknowledged": True}
    with pytest.raises(ValueError, match="base_url"):
        agent_lab.deploy_agent_project("external-agent", payload, save)


def test_deploy_rejects_unknown_mode(monkeypatch):
    save, _ = _capture_save_fn()
    with pytest.raises(ValueError, match="deployment_mode"):
        agent_lab.deploy_agent_project("agent", {"deployment_mode": "bogus"}, save)
