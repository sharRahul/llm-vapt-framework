# Agent Lab: deploy any AI agent → working scannable target (design / plan)

**Date:** 2026-07-03
**Status:** Design agreed, implementation deferred to next session.
**Author:** Rahul Sharma (with Claude)

## Goal

A user must be able to point VulnoraIQ at **any AI agent project** and have VulnoraIQ
do everything needed to test it, with **zero manual/external steps**:

```
import agent source → build Docker image → run the container
  → auto-register a WORKING scannable target (correct method, endpoint, body, response)
  → scan
```

Today the user (and Claude, during manual testing of the AIRA vulnerable chatbot)
had to do the Docker build, `docker run`, host-port juggling, and hand-fix the
target adapter config. All of that must be baked into Agent Lab.

Acceptance: deploy the real third-party **AIRA Vulnerable-AI-Chatbot** through the
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
to pass through new fields. No new subsystem.

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

## Testing / acceptance

- Unit: analyzer endpoint detection + ranking; `_register_targets` output for
  GET/text and POST/JSON agents; `_free_host_port` returns a bindable port;
  `_running_in_container` toggles base_url.
- Integration/E2E: AIRA deployed and scanned entirely through Agent Lab, evidence
  contains AIRA's real responses (e.g. the sensitive-info refusal), zero manual
  steps. This is the definition of done for the user's request.

## Out of scope

- **AIGoat** (AWS Lambda/Terraform) and **Raiker** (needs a running local
  OpenAI-compatible model server + built SPA) — neither runs keyless/offline, so
  they cannot be the zero-external acceptance target. AIRA is the real-agent proof.
  Support for cloud/model-server-backed agents can be a later increment.
- No new UI framework work beyond surfacing the reachable URL / target id.
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
