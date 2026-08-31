# HTTP API

The console and any integration talk to the same API, served by
`webui/server.py` (`vulnoraiq-web`). Everything is JSON except the static assets,
the scan event stream, and `/metrics`.

## Conventions

- **Base URL** — `http://127.0.0.1:8787` by default.
- **Authentication** — send the token header named by `/api/session`
  (`X-VulnoraIQ-Token` unless configured otherwise). In `local_admin` mode no
  token is required and every request is the local admin.
- **CSRF** — every `POST` and `PATCH` requires an `X-CSRF-Token` header holding a
  token from `GET /api/csrf-token`. Tokens are scoped to the session and expire
  (`VULNORAIQ_CSRF_TOKEN_TTL`).
- **Content type** — mutating requests send `Content-Type: application/json`.
- **Errors** — `{"error": "<message>"}` with the matching status. Internal
  exceptions are never returned to the caller.
- **Request id** — supply `X-Request-ID` to correlate a call with audit records;
  one is generated when absent, and always echoed back.
- **Rate limiting** — per client IP; exceeding it returns `429`.

## Status codes

| Code | Meaning |
| --- | --- |
| `200` / `202` | Success; `202` when work was queued. |
| `400` | Invalid request body or parameter. |
| `401` | Authentication required or failed. |
| `403` | Missing permission, or missing/invalid CSRF token. |
| `404` | No such resource. |
| `415` | Mutating request was not `application/json`. |
| `429` | Rate limit exceeded, or the scan queue is full. |
| `500` | Internal error (details are logged, not returned). |
| `502` | An upstream tool (Docker, git) failed. |
| `503` | Not ready (`/readyz` only). |

## Permissions

| Permission | Roles | Gates |
| --- | --- | --- |
| `view_scans` | viewer, analyst, admin | Reading scans, findings, assistant endpoints. |
| `download_artifacts` | viewer, analyst, admin | Downloading report artefacts for own scans. |
| `view_all_scans`, `download_all_artifacts` | admin | Other users' scans and artefacts. |
| `start_configured_scan` | admin | Starting a scan. |
| `manage_runtime` | admin | Targets, agents, Agent Lab, full configuration. |

## Service

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/healthz` | none | Liveness plus process start time. |
| `GET` | `/readyz` | none | Readiness; `503` until targets and profiles load. |
| `GET` | `/metrics` | required unless explicitly disabled | Prometheus text exposition. |
| `GET` | `/api/session` | none | Whether auth is enabled, and the caller's identity and permissions. |
| `GET` | `/api/csrf-token` | yes | A CSRF token for this session. |
| `GET` | `/` and `/static/...` | none | The built console. |

## Configuration and targets

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| `GET` | `/api/config` | `view_scans` | Targets and profiles. Non-admins receive profile descriptions only. |
| `GET` | `/api/targets` | `view_scans` | Configured plus runtime targets. |
| `POST` | `/api/targets/save` | `manage_runtime` | Validate and register a runtime target. Body: `{"id": "...", "target": {...}}`. |
| `POST` | `/api/targets/delete` | `manage_runtime` | Remove a runtime target. Body: `{"id": "..."}`. |
| `POST` | `/api/targets/{id}/validate` | `view_scans` | Connectivity check against a configured target. |

A target definition is validated on save: unsupported types, malformed endpoint
paths, credentials embedded in a URL, and out-of-scope hosts are all rejected
before the target can ever be scanned.

## Scans

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| `POST` | `/api/scans` | `start_configured_scan` | Queue a scan. Body: `{"target": "...", "profile": "baseline", "authorised": true}`. Returns `202` with the job. |
| `GET` | `/api/scans` | `view_scans` | Jobs visible to the caller. |
| `GET` | `/api/scans/{id}` | `view_scans` | One job with its event history. |
| `GET` | `/api/scans/{id}/events` | `view_scans` | Server-sent events: progress, findings, completion. Honours `Last-Event-ID`. |
| `GET` | `/api/scans/{id}/findings` | `view_scans` | Findings with their current remediation state. |
| `GET` | `/api/scans/{id}/findings/{finding_id}` | `view_scans` | One finding. |
| `GET` | `/api/scans/{id}/findings/{finding_id}/history` | `view_scans` | Audit trail of state changes. |
| `PATCH` | `/api/scans/{id}/findings/{finding_id}` | `view_scans` | Update triage state. |
| `POST` | `/api/scans/{id}/findings/{finding_id}/actions` | `view_scans` | Same update, as an action post. |
| `GET` | `/api/scans/{id}/artifact/{name}` | `download_artifacts` | Download a generated artefact. |

Artefact names come from the job's own output map (`markdown`, `json`, `sarif`,
`dashboard_markdown`, `dashboard_html`); arbitrary paths are refused.

Finding status must be one of `open`, `triaged`, `in_progress`, `accepted_risk`,
`false_positive`, `fixed`, `wont_fix`. `false_positive` and `accepted_risk`
require a reason. Patch bodies are redacted before storage and only the
remediation fields are writable.

### Event stream

```text
event: scan_started      data: {"scan_id": ..., "progress": {...}, ...}
event: finding_created   data: {...}
event: heartbeat         data: {...}
event: done              data: {<final job>}
```

A stream ends at the terminal event or at `VULNORAIQ_SSE_MAX_STREAM_SECONDS`.

## Agents (prebuilt images)

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| `GET` | `/api/agents` | `view_scans` | Running agent containers and available templates. |
| `GET` | `/api/agents/{id}/logs` | `view_scans` | Recent container logs. |
| `POST` | `/api/agents/deploy` | `manage_runtime` | Deploy from a template or an image. |
| `POST` | `/api/agents/{id}/start`, `/stop`, `/remove` | `manage_runtime` | Lifecycle actions. |
| `POST` | `/api/agents/templates` | `manage_runtime` | Save a deployable template. |
| `POST` | `/api/agents/templates/{key}/delete` | `manage_runtime` | Delete a template. |

## Agent Lab (imported projects)

All Agent Lab endpoints require `manage_runtime`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/agent-lab` | Full workspace state: projects, deployments, provider presets, profiles, targets. |
| `GET` | `/api/agent-lab/projects` | Imported and mapped projects. |
| `GET` | `/api/agent-lab/projects/{id}/analyze` | Detected framework, ports, endpoints, environment variables, and the selected inference endpoint. |
| `GET` | `/api/agent-lab/projects/{id}/dockerfile` | The project's Dockerfile, or one generated for it. |
| `GET` | `/api/agent-lab/deployments` | Deployment history. |
| `POST` | `/api/agent-lab/import/git` | Clone from an allowed git host. |
| `POST` | `/api/agent-lab/import/archive` | Import a base64 ZIP. |
| `POST` | `/api/agent-lab/projects/{id}/deploy` | Build, run, health-gate, and register a target. |
| `POST` | `/api/agent-lab/projects/{id}/delete` | Delete an imported project. |
| `POST` | `/api/agent-lab/deployments/{id}/remove` | Remove the container and the targets it registered. |

A deploy only registers a target once the container is running and actually
answering HTTP. A container that never serves is removed rather than turned into
a broken target.

## Assistant

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| `GET` | `/api/assistant/config` | `view_scans` | Provider, allowed models, and local model status. |
| `POST` | `/api/assistant/chat` | `view_scans` | Ask a question, optionally about a finding. |
| `POST` | `/api/assistant/explain` | `view_scans` | Plain-language explanation of one finding. |
| `POST` | `/api/findings/cve` | `view_scans` | Look up CVE records matching a finding. |

Assistant output is advisory. Responses carry a `safety_note` saying so, and are
never presented as scanner-confirmed evidence — see
[findings and evidence](../guides/findings.md).

## Related

- [CLI reference](cli.md)
- [Environment variables](environment-variables.md)
- [Security model](../security/security-model.md)
