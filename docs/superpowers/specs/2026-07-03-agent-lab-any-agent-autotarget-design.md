# Agent Lab: deploy any AI agent → working scannable target (design / plan)

**Date:** 2026-07-03
**Status:** Implemented — endpoint-contract detection + ranking, contract-derived
auto-targets, free-port + run-mode-aware `base_url`, health-gated registration
with cleanup, External/Hybrid deployment modes, authorization acknowledgement,
and the deployment-summary UI landed in `webui/agent_lab.py`,
`webui/assistant_server.py`, `webui/static/agent-lab/`, with unit tests in
`tests/test_agent_lab_autotarget.py`. Remaining: the live AIRA Docker E2E
(requires a Docker host) is documented as the manual acceptance test.
**Author:** Rahul Sharma (with Claude)

## Intended use / authorization boundary

Agent Lab is intended for **authorized AI red teaming, security testing, and
pre-deployment vulnerability discovery**. It is designed to help security teams,
developers, and model/application owners validate AI agents and LLM-backed
applications before production release.

The workflow assumes the user has permission to import, deploy, interact with, and
scan the target agent or model endpoint. Agent Lab should not be used against
unauthorized third-party systems, unauthorized cloud endpoints, model APIs, or applications without explicit
authorization.

Key intended use cases:

- testing internal AI agents before deployment;
- validating authorized third-party/open-source agents in a local lab environment;
- reproducing vulnerabilities in deliberately vulnerable AI applications;
- checking prompt-injection, data-leakage, unsafe-output, tool-use, and policy
  bypass risks in controlled environments;
- generating evidence for remediation and security sign-off.

The product should make the authorized-testing assumption visible in the UI and
documentation.

## Goal

A user must be able to point VulnoraIQ at **any AI agent project, local model-serving
app, or compatible external LLM endpoint** and have VulnoraIQ do everything needed
to test it, with **minimal to zero manual/external steps**:

```
import agent or model source → build Docker image → run the container
  → auto-register a WORKING scannable target (correct method, endpoint, body, response)
  → scan
```

Today the user (and Claude, during manual testing of the AIRA vulnerable chatbot)
had to do the Docker build, `docker run`, host-port juggling, and hand-fix the
target adapter config. All of that must be baked into Agent Lab.

Acceptance: deploy the real third-party **[AIRA Vulnerable-AI-Chatbot](https://github.com/aira-security/Vulnerable-AI-Chatbot)** through the
Agent Lab flow end-to-end (import → deploy → auto-target → scan) with **no manual
`docker` commands and no manual target edits**, and get a completed scan with real
interaction evidence.

## Background / current architecture

Two agent subsystems exist:

1. **`webui/agent_host.py`** + `/api/agents/*` + React **Agents** tab
   (`webui/console/src/components/agents/`). Deploys a prebuilt image or a saved
   template. Simpler path.
2. **`webui/agent_lab.py`** + `/api/agent-lab/*` + static `/agent-lab` page
   (`webui/static/agent-lab/`). Full pipeline: import (folder upload / ZIP / Git /
   mapped folder) → `analyze_agent_project` → build Dockerfile (existing or
   generated) → `docker build` → `docker run` (hardened, GPU options) →
   `_register_targets` → deploy record. **This is the pipeline in scope.**

Analysis today is split across two analyzers:
- `webui/project_analyzer.py` — richer: detects framework, ports, endpoints with
  `method`, `param_style` (`query` vs `json`), and `param_key` (`msg`/`prompt`/
  `input`/`query`), env vars, and can generate a Dockerfile.
- `webui/agent_lab.py::_detect_endpoints` — poorer: detects method + path but
  **hardcodes** `param_style:"json"`, `param_key:"prompt"`. `deploy_agent_project`
  uses this weaker one, so the query/`msg` detection is lost.

## Gaps that force manual work (root causes)

1. **Auto-target ignores the detected contract.** `agent_lab._register_targets`
   hardcodes, for `http_json`: `method` from payload/default `POST`,
   `request_body_template={"prompt":"{{prompt}}"}`,
   `response_extraction_path:"response"`. AIRA is `GET /get?msg=` returning **plain
   text**, so the auto-target would POST the wrong params to the wrong shape and
   extract from a non-existent `response` key → fails. The analyzer already knows
   the real contract; it is discarded.

2. **Weaker endpoint detection in the deploy path.** `agent_lab._detect_endpoints`
   drops `param_style`/`param_key`, and does not skip non-inference routes (`/`,
   `/health`, `/healthz`, `/refresh`, static). It can pick the wrong endpoint.

3. **`base_url` not reachable in Desktop Mode.** `_register_targets` builds
   `base_url = http://{container_name}:{port}` (container DNS). That only resolves
   when VulnoraIQ itself runs inside the agent Docker network (Docker Lab Mode). In
   Desktop Mode (VulnoraIQ on the host) the scanner cannot resolve the container
   name; it must use `http://127.0.0.1:<published-port>`.

4. **Host-port collision / no free-port selection.** Deploy publishes
   `127.0.0.1:<port>:<port>` (container port == host port). If the host port is
   taken (real failure hit during manual testing: host `5000` was occupied), the
   run fails or the target is unreachable. Agent Lab must auto-pick a free host
   port and map `host_free:container_port`, then use `host_free` in `base_url`.

## Proposed design

Keep all changes inside `webui/agent_lab.py` and `webui/project_analyzer.py`, with
a possible small touch in `webui/hosted_server.py` only if the deploy handler needs
to pass through new fields. 

Deployment modes:
1. Containerized local agent
   - build image
   - run container
   - register target
2. External endpoint agent
   - no Docker build
   - user supplies base URL / auth config
   - register OpenAI-compatible or custom HTTP target
3. Hybrid agent
   - run local app container
   - app depends on external model provider or local model server

### 1. Unify + enrich endpoint detection

- Make `agent_lab.analyze_agent_project` reuse (or match) `project_analyzer`'s
  richer endpoint detection so each endpoint carries:
  `{ method, path, param_style: "query"|"json", param_key, response_shape: "json"|"text", response_path? }`.
- Add endpoint ranking to select the inference endpoint:
  - Prefer paths containing `chat`, `ask`, `get`, `query`, `predict`, `invoke`,
    `completion`, `message`, `run`, `api`.
  - Deprioritize / skip `/`, `/health`, `/healthz`, `/ready`, `/readyz`,
    `/refresh`, `/static/...`, `/favicon.ico`, `/docs`, `/openapi.json`.
  - Prefer endpoints that read a user param (`msg`/`prompt`/`input`/`query`).
- Response shape: infer `text` when the handler returns a bare string / `str(...)` /
  `PlainTextResponse`; infer `json` when it returns `jsonify`/`JSONResponse`/dict.
  Default to `text` when unknown (safer: adapter returns the whole body).

### 2. Derive adapter config from the detected contract

Rewrite `_register_targets` (http_json branch) to build config from the chosen
endpoint instead of hardcoding:

- `method` = endpoint.method (GET/POST/PUT)
- `endpoint_path` = endpoint.path
- `request_body_template` = `{ <param_key>: "{{prompt}}" }`
  (GET → the adapter already sends the body dict as query params; POST → JSON body)
- `response_extraction_path`:
  - `""` (empty) when `response_shape == "text"` → adapter returns the whole body
  - detected JSON path (e.g. `response`, `output`, `choices.0.message.content`)
    when `response_shape == "json"`; fall back to trying common keys
    (`output`/`response`/`text`/`content`) which the http_json adapter already
    supports.
- Keep `chat_completions` branch as-is (already correct for OpenAI-shaped agents).
- Allow an explicit `payload.target` override to still win (manual override path).

### 3. Run-mode-aware base_url + free host port

- Add `_running_in_container()` — true if `/.dockerenv` exists or
  `VULNORAIQ_IN_CONTAINER` is set.
- Add `_free_host_port(preferred)` — try the agent's detected/preferred port; if
  taken, bind `127.0.0.1:0` to get a free ephemeral port.
- Publish `127.0.0.1:<host_free>:<container_port>`.
- `base_url`:
  - Desktop Mode (not in container): `http://127.0.0.1:<host_free>`
  - Docker Lab Mode (in container): `http://<container_name>:<container_port>`
    (unchanged behaviour for that mode).
- Persist both container port and host port in the deployment record so
  stop/start/remove and the UI can show the reachable URL.

### 4. Surface + docs

- Ensure the `/agent-lab` deploy response returns the auto-registered `target_id(s)`
  and the reachable `base_url` so the user can go straight to Targets/Workspace and
  scan.
- Update `docs/AGENT_LAB.md`, `docs/WEBUI_GUIDE.md` (Agent Lab row), and
  `CHANGELOG.md` to state that deploying any agent now auto-produces a working
  target matching the agent's real HTTP contract (incl. GET/query and text
  responses) on a free host port.
- Display an authorization notice before deployment/scanning:
  "Only deploy and scan agents, models, or endpoints you own or are explicitly
  authorized to test."
- For External endpoint and Hybrid agent modes, require the user to acknowledge
  that they are authorized to test the supplied endpoint and that any configured
  credentials are approved for security testing.
- Document authorized-use expectations, safe lab setup, credential handling, and
  pre-production testing guidance.

### 5. Deployment reliability, cleanup, and observability

- Add a post-run health check before registering the target:
  - wait for the selected port to respond;
  - retry with timeout;
  - surface build/run/health errors clearly in the UI.
- Capture and expose deployment logs:
  - Docker build logs;
  - container startup logs;
  - target registration errors;
  - scanner interaction errors.
- Implement cleanup on failed deployment:
  - remove failed containers;
  - avoid orphaned images/containers where safe;
  - release deployment records only after successful registration.
- Persist selected endpoint contract:
  `{ method, path, param_style, param_key, response_shape, response_path }`.
- Persist deployment metadata:
  `{ deployment_mode, image_id, container_id, container_port, host_port,
     base_url, target_ids, health_status, created_at, updated_at }`.
- Never persist raw API keys or secrets in deployment records.
  Use environment variables, secret references, or runtime-only injection.

## Implementation steps (next session)

1. Enrich `project_analyzer` endpoint detection with `response_shape` + ranking
   helper; add unit tests (Flask GET `/get?msg=` text; FastAPI POST `/chat` JSON;
   endpoint ranking skips `/health`).
2. Point `agent_lab.analyze_agent_project` at the unified detection (drop the weaker
   inline `_detect_endpoints`, or upgrade it to parity).
3. Rewrite `_register_targets` to derive config from the chosen endpoint; unit-test
   the produced target config for AIRA-shaped and chat-completions-shaped agents.
4. Add `_running_in_container` + `_free_host_port`; wire host:container publishing
   and run-mode base_url into `deploy_agent_project`; adjust the deployment record.
5. Manual E2E (the acceptance test): via the Agent Lab flow, import the AIRA
   project, deploy it (Docker build+run happen inside VulnoraIQ), confirm the
   auto-registered target is `GET /get`, `{msg:{{prompt}}}`, empty response path,
   `base_url http://127.0.0.1:<free>`; run a baseline scan to completion and confirm
   real AIRA responses appear in the evidence — all with **no manual docker/target
   steps**.
6. Run full gate: `ruff`, `mypy`, `pytest`, console `npm run build` if any TS
   changes; update docs; commit; push.
7. Add External endpoint mode:
   - accept base URL, adapter type, auth configuration, and endpoint contract;
   - register target without Docker build/run;
   - require authorization acknowledgement.
8. Add Hybrid agent mode:
   - build/run local app container;
   - collect external model-server configuration;
   - inject required environment variables;
   - register the app endpoint as the scan target.
9. Add deployment summary UI:
   - show detected contract, reachable URL, selected endpoint, target ID,
     health status, logs, and deployment mode;
   - add one-click Run baseline scan.
10. Add production hardening:
    - health checks;
    - deployment timeout handling;
    - cleanup on failure;
    - safe credential handling;
    - structured error messages.

## Testing / acceptance

- Unit: analyzer endpoint detection + ranking; `_register_targets` output for
  GET/text and POST/JSON agents; `_free_host_port` returns a bindable port;
  `_running_in_container` toggles base_url.
- Integration/E2E: AIRA deployed and scanned entirely through Agent Lab, evidence
  contains AIRA's real responses (e.g. the sensitive-info refusal), zero manual
  steps. This is the definition of done for the user's request.
- External endpoint mode:
  - register OpenAI-compatible endpoint without Docker build;
  - register custom HTTP endpoint with explicit method/path/body/response config;
  - authorization acknowledgement is required.
- Hybrid mode:
  - local app receives model-server config through environment variables;
  - target registration uses the local app endpoint, not the model-server endpoint;
  - missing model-server config produces an actionable error.
- UI:
  - deployment summary displays reachable URL, selected endpoint, target ID,
    health status, logs, and Run scan action.
- Reliability:
  - failed build is surfaced clearly;
  - failed container startup cleans up correctly;
  - failed health check does not register a broken target;
  - raw secrets are not persisted in deployment records.

## Included Extensions

Agent Lab must support non-self-contained agents through the deployment modes
defined above.

- **AIGoat**
  - **[AISecurityConsortium/AIGoat](https://github.com/AISecurityConsortium/AIGoat)**
    appears suitable as a future local-container acceptance target if it can run
    locally through Docker or a standard app server flow.
  - **[orcasecurity-research/AIGoat](https://github.com/orcasecurity-research/AIGoat)**
    is AWS/Terraform-backed infrastructure and should be treated as an
    External endpoint or cloud/IaC-backed target rather than a normal local
    Docker agent.
- **[Raiker](https://github.com/sharRahul/Raiker)**
  - Treat as a **Hybrid agent**:
    local app/container + externally configured OpenAI-compatible model endpoint.
  - Agent Lab should allow the user to configure the required model-server base URL,
    auth settings, and any required environment variables before deployment.
- **External endpoint agents**
  - Allow users to register an existing base URL without building a container.
  - Support OpenAI-compatible endpoints and custom HTTP JSON/text endpoints.
  - Require authorization acknowledgement before saving or scanning the target.
- **Hybrid agents**
  - Run the local app container.
  - Configure external dependencies such as Ollama, vLLM, LM Studio, Azure OpenAI,
    OpenAI-compatible APIs, or other cloud-hosted model services.
  - Store only safe credential references or environment-variable names, not raw
    secrets in deployment records.
  - For this implementation phase, keep **[AIRA](https://github.com/aira-security/Vulnerable-AI-Chatbot)** as the primary real-agent proof because it is self-contained enough to validate import → build → run → auto-target → scan with zero manual Docker or target edits.

- Consider a richer Agent Lab UI that displays the detected contract, reachable URL,
  selected endpoint, target ID, deployment mode, logs, health status, and a one-click
  “Run scan” action.
  - **Richer Agent Lab UI**
  - Display the detected contract.
  - Show reachable URL, selected endpoint, target ID, deployment mode, logs, and health status.
  - Add one-click actions for:
    - Open target
    - Run baseline scan
    - View logs
    - Stop/remove deployment

## Out of scope

- Not vendoring third-party agent source into the repo (user imports the agent).

## Notes from the manual-testing session that motivated this

- AIRA built fine from its own Dockerfile; ran on container port 5000. Host 5000 was
  occupied, so it had to be remapped to 5055 manually → motivates free-port
  selection.
- AIRA endpoint is `GET /get?msg=<prompt>`, plain-text response. The direct-target
  editor gained a **GET method** selector and `{{prompt}}`→query-param handling in a
  prior commit (`239e3a5`); the same contract must be produced **automatically** by
  Agent Lab.
- The `http_json` adapter already supports GET (sends body dict as query params) and
  non-JSON responses (falls back to returning the text body), so no adapter changes
  are expected — the work is in analysis + auto-target config + host reachability.
