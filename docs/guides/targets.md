# Target configuration

VulnoraIQ requires at least one configured target before any scan can run. There is no default scan target.

| Path | File | Use |
| --- | --- | --- |
| Docker deployment | `config/targets.docker.yaml` | Target configuration for Docker Compose (VULNORAIQ_TARGET_CONFIG=targets.docker.yaml). |
| Host-native | `config/targets.yaml` | Target configuration for local package or source installs. |

## Configuring a target

Add your target to the active config file (e.g. `config/targets.yaml`) with the following fields:

- A unique target ID (the YAML key)
- `type`: one of `http_json`, `chat_completions`, `ollama_generate`, `rag_query`, `webhook_json`, `agent_tool_loop`
- `base_url` and `endpoint_path` (or full `endpoint`)
- `method`: `POST` or `GET`
- `response_extraction_path`: JSON path to the text response
- `timeout`, `rate_limit`, `retry` settings
- `authorisation_required: true`
- `safety_profile`: e.g. `local_lab_safe`
- `environment`: `local`, `lab`, `internal`, or `production-like`
- `owner.contact`: team contact email

See the commented template in `config/targets.yaml` and the safety profiles in `config/safety_profiles.yaml`.

When testing outside Docker, keep targets on loopback unless you have written permission and a safety profile designed for the environment.

## Required target fields

A configured target should state:

- target name and type;
- `base_url` plus `endpoint_path`, or a full `endpoint`;
- method and request template/body template;
- response extraction path;
- timeout and rate limit;
- environment label;
- owner/contact where applicable;
- `authorisation_required: true` for all targets;
- safety profile;
- tags that describe the target shape and environment.

## Runtime target management

The React WebUI target workspace currently calls backend APIs for:

- `GET /api/targets` — configured and runtime target inventory;
- `POST /api/targets/save` — save a runtime target;
- `POST /api/targets/delete` — delete a runtime target;
- `POST /api/targets/{id}/validate` — validate connectivity and response extraction;
- `GET /api/scans` and `POST /api/scans` — show recent jobs and launch authorised scans.

## Safety rules

- All targets require explicit authorisation (`--authorised` in CLI, authorisation gate in WebUI).
- Secrets must be referenced through environment variables, not committed config values.
- Public or external hosts must be disallowed unless the safety profile explicitly permits them for an approved environment.
- Headers, request bodies, responses, evidence, and reports are passed through redaction before persistence.
- Docker lab targets should use Docker service names, not host `localhost`.

## Approved real-environment GenAI validation

Synthetic validation remains the default. Real-environment GenAI validation is supported only for approved internal environments and requires explicit authorisation, an allow-list or allowed host pattern, environment-variable credential references, dry-run defaults, rate limits, timeouts, audit logging, and evidence redaction. Templates are provided in `config/targets/templates/` for OpenAI-compatible LLM APIs, RAG endpoints, local model servers, agent framework endpoints, provider gateways, and vector-store-backed apps. Do not put real credentials in target YAML; use `token_env_var`/`auth_token_env` references.
