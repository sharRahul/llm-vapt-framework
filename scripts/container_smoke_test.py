#!/usr/bin/env python3
"""Container smoke test: build, run, and verify the VulnoraIQ Docker image.

Usage:
    python scripts/container_smoke_test.py [--image vulnoraiq:production-candidate]
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.error
import urllib.request

LOGGER = logging.getLogger("container_smoke_test")

SMOKE_PORT = 18787


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    LOGGER.info("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def test_health(url: str, retries: int = 10, delay: float = 2.0) -> bool:
    for i in range(retries):
        try:
            resp = urllib.request.urlopen(f"{url}/healthz", timeout=5)
            data = json.loads(resp.read().decode())
            if data.get("status") == "ok":
                LOGGER.info("Health check passed (attempt %d)", i + 1)
                return True
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
            LOGGER.info("Health check attempt %d: %s", i + 1, exc)
        time.sleep(delay)
    return False


def test_readyz(url: str) -> bool:
    """The readiness probe must answer and report an accurate state.

    A fresh container ships no targets on purpose - VulnoraIQ has no default
    target - so ``not_ready`` with zero targets is the correct answer, returned
    as 503. Demanding a 2xx here would fail the safe default and push someone
    towards shipping a target just to make CI green.
    """
    try:
        resp = urllib.request.urlopen(f"{url}/readyz", timeout=5)
        status, data = resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code != 503:
            LOGGER.error("Readiness probe returned an unexpected status: %d", exc.code)
            return False
        status, data = exc.code, json.loads(exc.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        LOGGER.error("Readiness check failed: %s", exc)
        return False

    if "status" not in data or "targets_loaded" not in data:
        LOGGER.error("Readiness body is missing expected fields: %s", data)
        return False
    if status == 503:
        if data["status"] != "not_ready" or data["targets_loaded"] != 0:
            LOGGER.error("503 readiness must mean not_ready with no targets: %s", data)
            return False
        LOGGER.info("Readiness check passed: not_ready with 0 targets (the expected default)")
        return True
    LOGGER.info("Readiness check passed: ready with %s target(s)", data["targets_loaded"])
    return True


def test_production_fails_without_token(url: str) -> bool:
    try:
        resp = urllib.request.urlopen(f"{url}/api/scans", timeout=5)
        LOGGER.error("Expected 401 but got %d", resp.status)
        return False
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            LOGGER.info("Production mode correctly rejected unauthenticated request (401)")
            return True
        LOGGER.error("Expected 401 but got %d", exc.code)
        return False
    except urllib.error.URLError as exc:
        LOGGER.error("Request failed: %s", exc)
        return False


def test_production_refuses_to_start_without_a_token(image: str) -> bool:
    """Production mode must refuse to start when no admin token is configured.

    This is the fail-closed property the whole production gate exists for, so a
    container smoke test should prove it rather than assume it.
    """
    name = "vulnoraiq-smoke-nostart"
    run(["docker", "rm", "-f", name])
    result = run(["docker", "run", "--rm", "--name", name, "-e", "VULNORAIQ_ENV=production", image], timeout=90)
    run(["docker", "rm", "-f", name])

    if result.returncode == 0:
        LOGGER.error("Container started in production mode with no admin token; it must refuse.")
        return False
    output = f"{result.stdout}\n{result.stderr}".lower()
    if "admin_token" not in output and "production" not in output:
        LOGGER.error("Container exited, but not for the expected reason:\n%s", output[:800])
        return False
    LOGGER.info("Production mode correctly refused to start without an admin token")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Container smoke test for VulnoraIQ")
    parser.add_argument("--image", default="vulnoraiq:production-candidate", help="Docker image to test")
    parser.add_argument("--port", type=int, default=SMOKE_PORT, help="Host port to bind")
    parser.add_argument("--no-build", action="store_true", help="Skip docker build")
    args = parser.parse_args()

    image = args.image
    port = args.port
    url = f"http://127.0.0.1:{port}"
    container_name = "vulnoraiq-smoke-test"

    results: dict[str, bool] = {}

    if not args.no_build:
        LOGGER.info("Building image %s...", image)
        result = run(["docker", "build", "-t", image, "."])
        if result.returncode != 0:
            LOGGER.error("Docker build failed:\n%s", result.stderr)
            sys.exit(1)
        LOGGER.info("Build succeeded")
    else:
        LOGGER.info("Skipping build (--no-build)")

    # Clean up any previous container
    run(["docker", "rm", "-f", container_name])

    LOGGER.info("Checking production mode fails closed without a token...")
    if not test_production_refuses_to_start_without_a_token(image):
        sys.exit(1)

    LOGGER.info("Starting container %s...", container_name)
    # The image binds 0.0.0.0 inside the container, which production mode only
    # permits behind a trusted proxy — Docker's published-port proxy is exactly
    # that here. Configuring the container the way a hardened deployment is
    # configured is the point: a smoke test that cannot satisfy the product's
    # own startup checks is testing nothing.
    result = run([
        "docker", "run", "-d", "--name", container_name,
        "-p", f"127.0.0.1:{port}:8787",
        "-e", "VULNORAIQ_ENV=production",
        "-e", "VULNORAIQ_ADMIN_TOKEN=smoke-test-container-token-2024",
        "-e", "VULNORAIQ_TRUST_PROXY_HEADERS=true",
        "-e", "VULNORAIQ_TRUSTED_PROXY_CIDRS=127.0.0.0/8,172.16.0.0/12,10.0.0.0/8",
        image,
    ])
    if result.returncode != 0:
        LOGGER.error("Container start failed:\n%s", result.stderr)
        sys.exit(1)

    container_id = result.stdout.strip()
    LOGGER.info("Container started: %s", container_id)

    passed = 0
    failed = 0

    try:
        LOGGER.info("Test 1: Health endpoint...")
        ok = test_health(url)
        results["health_endpoint"] = ok
        if ok:
            passed += 1
        else:
            failed += 1
            # A container that never serves has already logged the reason,
            # usually a production check refusing the configuration. Print it
            # rather than leaving only "connection refused" in the output.
            logs = run(["docker", "logs", "--tail", "60", container_name])
            LOGGER.error("Container did not serve. Last logs:\n%s\n%s", logs.stdout, logs.stderr)

        LOGGER.info("Test 2: Readiness endpoint...")
        ok = test_readyz(url)
        results["readiness_endpoint"] = ok
        if ok:
            passed += 1
        else:
            failed += 1

        LOGGER.info("Test 3: Production mode rejects unauthenticated...")
        ok = test_production_fails_without_token(url)
        results["production_auth_required"] = ok
        if ok:
            passed += 1
        else:
            failed += 1

    finally:
        LOGGER.info("Cleaning up container %s...", container_name)
        run(["docker", "rm", "-f", container_name])

    LOGGER.info("=== Smoke Test Results ===")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        LOGGER.info("  %s: %s", name, status)
    LOGGER.info("Passed: %d / %d", passed, len(results))

    if failed > 0:
        LOGGER.error("Smoke test FAILED: %d test(s) failed", failed)
        sys.exit(1)

    LOGGER.info("All container smoke tests passed.")


if __name__ == "__main__":
    main()
