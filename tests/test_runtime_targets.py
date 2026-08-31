"""The runtime target registry shared by the API layer and the scanner.

Targets registered at run time have to mean the same thing to the server that
created them and to the scanner that reads them, and they must go through the
same validation as a committed target.
"""

from __future__ import annotations

import pytest
import yaml

from core import runtime_targets


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("VULNORAIQ_RUNTIME_TARGETS_PATH", str(tmp_path / "runtime_targets.yaml"))
    yield


def _target(base_url: str = "http://127.0.0.1:9000") -> dict:
    return {
        "name": "local agent",
        "type": "http_json",
        "base_url": base_url,
        "endpoint_path": "/chat",
        "method": "POST",
        "request_body_template": {"prompt": "{{prompt}}"},
        "response_extraction_path": "response",
        "authorisation_required": True,
        "safety_profile": "local_lab_safe",
    }


def test_save_then_load_round_trip() -> None:
    runtime_targets.save("agent-one", _target())

    targets = runtime_targets.load()
    assert set(targets) == {"agent-one"}
    assert targets["agent-one"]["endpoint_path"] == "/chat"


def test_save_validates_the_target_definition() -> None:
    with pytest.raises(ValueError, match="unsupported target type"):
        runtime_targets.save("bad-type", {**_target(), "type": "not-a-type"})


def test_save_rejects_out_of_scope_hosts() -> None:
    with pytest.raises(ValueError, match="external targets are blocked"):
        runtime_targets.save("public", _target("https://example.com"))


def test_save_rejects_ids_that_would_escape_the_registry() -> None:
    for bad_id in ("../escape", "with/slash", "a", "has space"):
        with pytest.raises(ValueError, match="target id must be"):
            runtime_targets.save(bad_id, _target())


def test_delete_reports_whether_the_target_existed() -> None:
    runtime_targets.save("agent-one", _target())

    assert runtime_targets.delete("agent-one") is True
    assert runtime_targets.delete("agent-one") is False


def test_delete_many_removes_only_the_named_targets() -> None:
    runtime_targets.save("agent-one", _target())
    runtime_targets.save("agent-two", _target())
    runtime_targets.save("agent-three", _target())

    removed = runtime_targets.delete_many(["agent-one", "agent-three", "never-existed"])

    assert removed == 2
    assert set(runtime_targets.load()) == {"agent-two"}


def test_merge_into_lets_runtime_targets_win() -> None:
    runtime_targets.save("shared", _target("http://127.0.0.1:9999"))

    merged = runtime_targets.merge_into({"shared": {"base_url": "http://127.0.0.1:1111"}, "configured": {}})

    assert merged["shared"]["base_url"] == "http://127.0.0.1:9999"
    assert "configured" in merged


def test_registry_file_is_plain_yaml_under_a_targets_key() -> None:
    runtime_targets.save("agent-one", _target())

    data = yaml.safe_load(runtime_targets.registry_path().read_text(encoding="utf-8"))

    assert list(data) == ["targets"]
    assert "agent-one" in data["targets"]


def test_scanner_sees_targets_registered_at_runtime() -> None:
    """The registry is the single source of truth for both layers."""
    from core.scanner import Scanner

    runtime_targets.save("agent-one", _target())
    config = Scanner()._load_config()

    assert "agent-one" in config["targets"]["targets"]


def test_corrupt_registry_is_treated_as_empty_not_fatal() -> None:
    runtime_targets.registry_path().parent.mkdir(parents=True, exist_ok=True)
    runtime_targets.registry_path().write_text("- not a mapping\n", encoding="utf-8")

    assert runtime_targets.load() == {}


def test_target_config_validator_treats_no_targets_as_the_safe_default(tmp_path, capsys) -> None:
    """Shipping no target is intended: VulnoraIQ must assess nothing by default."""
    from scripts.validate_target_configs import main

    empty = tmp_path / "targets.yaml"
    empty.write_text("targets: {}\n", encoding="utf-8")

    assert main(["--config", str(empty)]) == 0
    assert "expected default" in capsys.readouterr().out


def test_target_config_validator_fails_on_an_invalid_definition(tmp_path, capsys) -> None:
    from scripts.validate_target_configs import main

    bad = tmp_path / "targets.yaml"
    bad.write_text(
        "targets:\n  broken:\n    type: http_json\n    base_url: https://example.com\n    endpoint_path: /\n",
        encoding="utf-8",
    )

    assert main(["--config", str(bad)]) == 1
    assert "FAIL  broken" in capsys.readouterr().out


def test_target_config_validator_accepts_a_valid_definition(tmp_path, capsys) -> None:
    from scripts.validate_target_configs import main

    good = tmp_path / "targets.yaml"
    good.write_text(
        "targets:\n  local:\n    name: local\n    type: http_json\n"
        "    base_url: http://127.0.0.1:9000\n    endpoint_path: /chat\n",
        encoding="utf-8",
    )

    assert main(["--config", str(good)]) == 0
    assert "ok    local" in capsys.readouterr().out
