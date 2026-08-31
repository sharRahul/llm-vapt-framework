# Real authorised AI agent testing

VulnoraIQ supports real, bounded testing only for systems you own or are explicitly authorised to assess. Non-demo targets require `--authorised` in CLI and an authorisation confirmation in WebUI workflows.

## Run the local mock agent

```bash
python examples/local_agent/server.py --port 9090
```

Optional modes: `--mode normal`, `--mode vulnerable`, or `--mode remediated`.

## Configure a real target

Edit `config/targets.yaml` and add a target with `type`, `base_url`, `endpoint_path`, `method`, `headers`, `request_body_template`, `response_extraction_path`, `timeout`, `retry`, `rate_limit`, `authorisation_required`, `safety_profile`, `tags`, `owner`, and `environment`.

Secrets must be referenced with `auth_token_env` or `token_env_var`; never place tokens directly in YAML.

Supported target types:

- `http_json`
- `chat_completions`
- `ollama_generate`
- `webhook_json`
- `rag_query`
- `agent_tool_loop`

## Validate connectivity

```bash
vulnoraiq targets validate --target local_mock_agent
```

The validator sends a harmless health prompt, validates HTTP/JSON response parsing, applies the response extraction path, and prints a normalized preview with secrets redacted.

## Run scans from CLI

```bash
vulnoraiq scan --target local_mock_agent --profile ai_agent_foundation --authorised
vulnoraiq scan --target local_rag_app --profile rag_security --authorised --output reports/output/local-rag.md --json-output reports/output/local-rag.json
```

## Run scans from WebUI

Start the hosted UI, open the browser, review `/api/targets` or the Targets section, validate the target, confirm authorisation for non-demo targets, select a profile, and start the scan. Progress is available through the existing Server-Sent Events endpoint at `/api/scans/{job_id}/events`.

## Evidence and findings

Real scans write sanitized evidence artifacts under `reports/output/evidence/<job_id>/`. Findings include severity, confidence, risk score, reproduction steps, remediation guidance, OWASP/MITRE mappings when available, and status.

## Troubleshooting

- Invalid URL: only `http` and `https` URLs are supported.
- External host blocked: loopback, private, `.local`, and `.internal` hosts are allowed by default. Only set `allow_external: true` for explicitly authorised scopes.
- Auth failure: confirm the token environment variable is set.
- Bad JSON or invalid mapping: fix `response_extraction_path` (dot path such as `choices.0.message.content`).
- Timeout: increase `timeout` or check target health.

## WebUI Target CRUD and external-host override

The hosted React console includes a **Targets** tab where operators can view configured targets, add or edit runtime targets, update request/response mapping, set the environment, provide owner/contact metadata, test connectivity, and delete runtime targets. Saved targets are written to `reports/output/webui/runtime_targets.yaml` by default and merged with `config/targets.yaml` at scan time.

The **Allow external host** toggle maps to `allow_external: true`. Keep it disabled for local/lab/internal testing. Enable it only for an explicitly authorised external or production-like scope; non-demo scans still require the separate authorisation confirmation before execution.
