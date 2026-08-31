# Plan: automated coverage for the Agent Lab deploy flow

**Status:** proposed
**Addresses:** [TO_BE_FIXED.md](TO_BE_FIXED.md) TBF-6
**Size:** small — CI job plus one fixture agent

## Problem

"Import an agent → build it → run it → get a working scan target → scan it" is
VulnoraIQ's flagship flow. It has **no automated coverage of the success path.**

What is covered today:

- Unit tests for endpoint detection, contract resolution, target-id
  sanitisation, and the health-gate helpers — all with Docker mocked out.
- CI builds the image and smoke-tests the `vulnoraiq-web` container.

What is not covered: an actual `docker build` of an imported project, an actual
container run, the health gate passing, the auto-registered target being
scannable, and cleanup removing both container and target.

Every regression fixed in this area — wrong port detection, a health gate
satisfied by Docker's port proxy, a free-port probe that misreported busy ports,
a form overriding a correctly detected contract — was found by hand. The next one
will be too.

## Work

### 1. A fixture agent in the repository

`tests/fixtures/agents/echo-agent/` — a deliberately minimal HTTP agent:

```text
app.py            # Flask, GET /get?msg=  -> plain text; GET /health -> ok
requirements.txt  # flask only
Dockerfile        # EXPOSE 5000, app.run(port=5000)
```

Shaped to exercise the cases that have actually broken: a `GET` inference
endpoint with a query parameter and a plain-text response, a non-default port
declared both in `app.run(...)` and in `EXPOSE`, and an infrastructure route
(`/health`) the endpoint ranker must skip.

A second fixture, `broken-agent/`, with an entrypoint that exits immediately —
the health gate must reject it and clean up.

### 2. An integration test, skipped without Docker

```python
@pytest.mark.docker
@pytest.mark.skipif(not docker_available(), reason="Docker engine not running")
def test_import_deploy_scan_and_clean_up(tmp_path):
    ...
```

The assertions that matter:

- the analyzer selects `GET /get`, param `msg`, response shape `text` — not `/`
  and not `/health`;
- the deploy publishes the detected port on loopback and health-gates on a real
  HTTP response;
- a runtime target is registered, and its config matches the detected contract;
- a scan against that target completes and produces findings;
- `remove` deletes the container **and** the registered target;
- the broken agent is rejected, its container removed, and its logs returned in
  the error.

Marked so the default `pytest -q` stays Docker-free. Local runs without Docker
skip; CI runs them.

### 3. CI

Extend the existing `docker` job — it already has a Docker daemon:

```yaml
- name: Agent Lab integration tests
  run: pytest -m docker -q
```

### 4. A browser pass over the deploy flow

Extend the hosted Playwright spec to import the fixture agent through the
console, deploy it, and start a scan on the auto-created target — so the UI half
of the flow is covered too, not only the API.

## Definition of done

- `pytest -m docker` covers import → analyse → build → run → health-gate →
  register → scan → remove.
- The broken-agent case asserts cleanup and an actionable error.
- CI runs them on every pull request.
- `pytest -q` without Docker still passes, skipping them.

## Why a fixture and not a real agent

Earlier manual testing used real third-party agents (AIRA, Raiker). They found
genuine bugs, but they are large, network-dependent, and change underneath the
test. The fixtures encode the *shapes* those agents exposed, in a form CI can
build in seconds.
