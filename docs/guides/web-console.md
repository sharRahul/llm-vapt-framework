# Web console

The VulnoraIQ web console is the React 18 + TypeScript SecOps console in `webui/console/`, built to `webui/static/console/` and served by the Python hosted WebUI entry point.

Static files under `webui/static/console/` are build output for the React console and are included as Python package data. The former standalone Agent Lab page redirects to the console’s **Projects** view.

## Start the recommended Docker lab

```bash
docker compose build
docker compose up -d
```

Open <http://localhost:8787>.

## WebUI workspace areas

| Area | Current behaviour |
| --- | --- |
| Dashboard / overview | Shows high-level security and assessment status using React console data models and live backend scan progress. |
| Target management | Loads configured/runtime targets, supports search and environment filters, shows readiness metrics and status pills, validates targets, saves/deletes runtime targets, launches authorised scans, and refreshes recent jobs. Direct LLM, RAG, and agent HTTP endpoints are authored in place (target type, base URL, endpoint path, model, response extraction path, request body template). Targets backed by a deployed Agent Lab container keep their base URL/endpoint locked to the container. |
| Projects / Agent Lab | The **Projects** console view imports real agent projects by local-folder upload, ZIP upload, Git import, or mapped-folder refresh; configures providers, custom runtime variables, and container ports; builds/runs containers (containerized, hybrid, or external-endpoint modes); and launches authorised scans. Deploying an agent auto-produces a **working** scan target matching its real HTTP contract — including `GET`/query and plain-text responses — on an auto-selected free host port with a run-mode-aware base URL, health-gated before registration. External/hybrid modes require an authorization acknowledgement. |
| Findings and intelligence | Provides analyst-facing panels for findings, triage context, persisted remediation/status actions, finding history, and assistant-backed analysis. |
| Assessment options | Uses configured profiles and single-test options from `config/attack_profiles.yaml`. |

## Current backend API wiring

The WebUI is wired to target management, scan launch/progress, finding actions/history, assistant chat/config, and experimental Agent Lab endpoints.

Agent Lab write actions require authentication, `manage_runtime`, and CSRF protection. The scan launch path keeps the non-demo authorisation guard. Target validation uses the same target adapter/connectivity logic as the CLI. Assistant requests require authentication and CSRF protection and pass model controls from the React panel to the assistant.

Local folder upload is intentionally browser-mediated: the user selects a folder, the browser packages the selected files, and Agent Lab imports them through the archive import API. The backend does not receive arbitrary local filesystem paths.

See [`agents.md`](agents.md) for the Agent Lab API and operator workflow.

## Assistant model controls

The Ask VulnorAIQ panel sends live chat payloads to `/api/assistant/chat`. Operators can adjust:

- model selection from the server-provided allow-list;
- temperature, constrained by backend validation;
- instruction text used for the backend assistant request.

The default backend provider is local/deterministic so self-hosted deployments work without outbound network access. Operators can configure provider settings with environment variables documented in deployment/runbook material. Assistant output is advisory and requires human review before closure or remediation.

## Remaining WebUI backend work

Current future maturity work is focused on enterprise identity, SIEM/SOAR integrations, signed/native packaging, external independent assurance, and promoting Agent Lab from experimental after its hardening backlog is complete.

## Operator flow

1. Start Desktop Mode or Docker Lab Mode and open the WebUI.
2. Go to the target workspace to author a direct LLM/RAG/agent HTTP endpoint (**Add**, then set target type, base URL, endpoint path, and response extraction path), or use Project Importer / Agent Lab for imported real agents.
3. For imported agents, import through local folder upload, ZIP upload, Git import, or mapped folder refresh.
4. Search or filter for the target or project.
5. Validate target connectivity, or build/run an Agent Lab project to generate a target.
6. Review the readiness checklist.
7. Select an assessment profile or focused single-test option.
8. Confirm authorisation for non-demo targets.
9. Launch the scan.
10. Review recent jobs, findings, live progress, assistant guidance, and report artifacts.

## Development flow

```bash
cd webui/console
npm install
npm run typecheck
npm run build
```

The production build emits assets into `webui/static/console/`. The Python hosted server serves the built console; Node is not required at runtime.

## Browser test flow

```bash
npm install
npx playwright install chromium --with-deps
npm run test:webui:hosted
```

The hosted WebUI Playwright flow is also part of the GitHub Actions CI path on Python 3.12.

## Security boundary

Launcher/local mode is for loopback laptop/workstation use. For shared/internal-server use, enable production mode, auth, reverse-proxy/TLS controls, and the documented deployment/runbook process. Do not expose Agent Lab on a shared server without an explicit risk decision because it can build and run local containers.

## Live scan progress and finding actions

The hosted React console now consumes `/api/scans/{scan_id}/events` with `EventSource` for persisted live progress. The target workspace shows stream state, latest phase, progress, event timeline, finding count, completion, and error states. Finding remediation/status APIs are available under `/api/scans/{scan_id}/findings/...`; mutations require authentication and CSRF protection and create persistent history/audit records.

While a run is not finished, the header shows a **Stop** control next to **Run Scan**. Stopping is a safety control, not a convenience: it ends the run after the request already in flight, and the result is recorded as `cancelled` rather than `failed`. The scanned-asset card names the actual outcome — completed, cancelled, timed out, or failed — because a run an operator stopped and a run the target rejected call for different next steps.

## Reading a finding

The finding detail pane leads with the badges that decide how much weight the finding carries: severity, risk score, provenance (**Observed**, **Inferred**, or **AI-assisted**), and triage status. Below the explanation, a collapsed **Raw evidence** section lists the request/response artefacts the scan captured; opening one shows the exact exchange with the target. See [Findings and evidence](findings.md) for what each field means and what it does not claim.

## Related

- [HTTP API reference](../reference/api.md) — every endpoint the console uses.
- [Findings and evidence](findings.md) — how to read what the console shows.
- [Frontend build](../development/frontend-build.md) — rebuilding the console.
