"""In-container smoke checks for the Docker Lab.

Run inside the Compose ``test-runner`` service, which shares the lab network
with ``vulnoraiq-web``:

    docker compose --profile test run --rm test-runner python scripts/docker_smoke_test.py

It verifies the things that can only be checked from inside the lab: that the
web service is reachable over the private network, that target scope is enforced
in the container's own environment, and that any evidence already written
carries no secrets.

It deliberately does not assert that reports exist. VulnoraIQ ships no default
target, so a fresh lab has run no scan — asserting otherwise would make this
script fail on a correctly configured deployment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WEB_URL = os.getenv("VULNORAIQ_SMOKE_WEB_URL", "http://vulnoraiq-web:8787")
SECRET_MARKERS = ("sk-live", "password=", "bearer ey", "-----begin")


def get_json(url: str) -> dict:
    """GET a JSON document, treating a 4xx/5xx body as a valid response."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode())


def check_web_service_is_reachable() -> None:
    health = get_json(f"{WEB_URL}/healthz")
    assert health.get("status") == "ok", f"unexpected health response: {health}"

    ready = get_json(f"{WEB_URL}/readyz")
    assert "targets_loaded" in ready, f"unexpected readiness response: {ready}"
    print(f"  web service reachable; readiness={ready['status']} targets={ready['targets_loaded']}")


def check_target_scope_is_enforced() -> None:
    """A public host must be refused from inside the container, not just on a dev box."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from integrations.target_adapters import validate_url; "
            "validate_url({'base_url':'https://example.com','endpoint_path':'/',"
            "'safety_profile':'docker_lab'})",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0, "an out-of-scope host was accepted inside the container"
    assert "blocked" in result.stdout.lower(), result.stdout
    print("  out-of-scope target refused inside the container")


def check_evidence_carries_no_secrets() -> None:
    evidence_root = Path(os.getenv("VULNORAIQ_EVIDENCE_DIR", "/data/evidence"))
    files = sorted(evidence_root.rglob("*.json")) if evidence_root.exists() else []
    if not files:
        print("  no evidence written yet (expected on a fresh lab); redaction check skipped")
        return
    contents = "\n".join(path.read_text(errors="ignore") for path in files[:20]).lower()
    for marker in SECRET_MARKERS:
        assert marker not in contents, f"evidence contains an unredacted secret marker: {marker}"
    print(f"  {len(files)} evidence file(s) checked; no secret markers found")


def main() -> int:
    if not Path("/.dockerenv").exists():
        print("WARNING: this smoke test is meant to run inside the Compose test-runner service")

    checks = (
        ("web service", check_web_service_is_reachable),
        ("target scope", check_target_scope_is_enforced),
        ("evidence redaction", check_evidence_carries_no_secrets),
    )
    failures = 0
    for name, check in checks:
        print(f"{name}:")
        try:
            check()
        except AssertionError as exc:
            print(f"  FAIL: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001 - report, do not mask, an unexpected fault
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            failures += 1

    if failures:
        print(f"\ndocker smoke test FAILED: {failures} check(s) failed")
        return 1
    print("\ndocker smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
