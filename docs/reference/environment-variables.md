# Environment variables

Every environment variable VulnoraIQ reads, what it does, and whether it holds a
secret. This page is the source of truth — the repository intentionally contains
no `.env` file of any kind.

Set values through your operating system environment, an untracked local `.env`
file, Docker Compose, or your CI/CD secret store. A copyable starting point
lives at [`config/environment.template`](../../config/environment.template);
copy it to a local `.env` (which is git-ignored) and edit it there.

**Never commit a value marked "Yes" in the *Sensitive* column.**

## Runtime and mode

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_RUN_MODE` | Selects the deployment mode. Desktop Mode publishes agent targets on loopback; Docker Lab Mode reaches them by container DNS. | Optional | `docker_lab` | `desktop`, `native`, `docker_lab`, `lab` | Launchers, Agent Lab, auth | No |
| `VULNORAIQ_ENV` | Enables production hardening checks at startup. | Optional | *(unset)* | `production` | Auth, production checks | No |
| `VULNORAIQ_HOST` | Interface the web server binds. | Optional | `127.0.0.1` | Host or IP | Web server | No |
| `VULNORAIQ_PORT` | Port the web server binds. | Optional | `8787` | 1–65535 | Web server | No |
| `VULNORAIQ_LOG_LEVEL` | Python logging level for application logs. | Optional | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Web server | No |
| `VULNORAIQ_IN_CONTAINER` | Forces "running inside a container" detection when `/.dockerenv` is absent. | Optional | *(unset)* | any non-empty value | Agent Lab | No |

## Authentication and authorisation

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_AUTH_MODE` | Authentication mode. `local_admin` is a single-user loopback session with no token. | Optional | `token` | `local_admin`, `token`, `trusted_proxy` | Auth | No |
| `VULNORAIQ_AUTH_ENABLED` | Legacy alias: `false` selects `local_admin`. Prefer `VULNORAIQ_AUTH_MODE`. | Optional | *(unset)* | `true`, `false` | Auth | No |
| `VULNORAIQ_ADMIN_TOKEN` | Admin bearer token. Required in production, minimum 20 characters. | Required in production | *(unset)* | Random string ≥ 20 chars | Auth | **Yes** |
| `VULNORAIQ_ANALYST_TOKEN` | Analyst bearer token. | Optional | *(unset)* | Random string | Auth | **Yes** |
| `VULNORAIQ_VIEWER_TOKEN` | Viewer bearer token. | Optional | *(unset)* | Random string | Auth | **Yes** |
| `VULNORAIQ_WEB_USERS_PATH` | Path to the file-based user list (non-production only). | Optional | `config/web_users.yaml` | Filesystem path | Auth | No |
| `VULNORAIQ_LOCAL_ADMIN_BIND_OK` | Permits `local_admin` on a non-loopback bind inside a container. Lab Mode only. | Optional | `false` | `true`, `false` | Auth | No |
| `VULNORAIQ_TRUST_PROXY_HEADERS` | Honour `X-Forwarded-For` and proxy identity headers. | Optional | `false` | `true`, `false` | Web security | No |
| `VULNORAIQ_TRUSTED_PROXY_CIDRS` | Comma-separated CIDRs allowed to send proxy headers. Required when the above is `true`. | Conditional | *(empty)* | `10.0.0.0/8,192.168.0.0/16` | Web security | No |
| `VULNORAIQ_METRICS_AUTH_REQUIRED` | Require authentication on `/metrics`. Always enforced in production. | Optional | `true` | `true`, `false` | Web server | No |

## Request limits and concurrency

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_MAX_REQUEST_BODY` | Maximum accepted request body, in bytes. | Optional | `10485760` | Positive integer | Web server | No |
| `VULNORAIQ_RATE_LIMIT_MAX` | Requests allowed per client per window. | Optional | `60` | Positive integer | Web security | No |
| `VULNORAIQ_RATE_LIMIT_WINDOW` | Rate-limit window, in seconds. | Optional | `60` | Positive integer | Web security | No |
| `VULNORAIQ_CSRF_TOKEN_TTL` | CSRF token lifetime, in seconds. | Optional | `300` | Positive integer | Web security | No |
| `VULNORAIQ_MAX_CONCURRENT_SCANS` | Scans allowed to run at once. | Optional | `5` | Positive integer | Scan runner | No |
| `VULNORAIQ_SCAN_QUEUE_LIMIT` | Scans admitted (running plus waiting) before new requests are refused. | Optional | `20` | Positive integer | Scan runner | No |
| `VULNORAIQ_SCAN_SLOT_WAIT_SECONDS` | How long a queued scan waits for a runner slot before failing. | Optional | `900` | Positive number | Scan runner | No |
| `VULNORAIQ_SSE_MAX_STREAM_SECONDS` | Maximum lifetime of one scan event stream. | Optional | `3600` | Positive number | Web server | No |

## Storage paths

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_CONFIG_DIR` | Directory holding the YAML configuration set. | Optional | `config` | Directory path | Scanner, web server | No |
| `VULNORAIQ_TARGET_CONFIG` | Target file name inside the config directory. | Optional | `targets.yaml` | File name | Scanner, web server | No |
| `VULNORAIQ_SAFETY_PROFILE_PATH` | Explicit path to `safety_profiles.yaml`. | Optional | `<config dir>/safety_profiles.yaml` | File path | Target adapters | No |
| `VULNORAIQ_WEB_OUTPUT_ROOT` | Root directory for generated reports and artefacts. | Optional | `reports/output/webui` | Directory path | Web server | No |
| `VULNORAIQ_RUNTIME_TARGETS_PATH` | Registry file for targets created at run time. | Optional | `<output root>/runtime_targets.yaml` | File path | Runtime targets | No |
| `VULNORAIQ_JOB_STORE_BACKEND` | Scan job persistence backend. | Optional | `sqlite` | `sqlite`, `json` | Job store | No |
| `VULNORAIQ_JOB_STORE_PATH` | Scan job database/file path. | Optional | `<output root>/jobs.db` | File path | Job store | No |
| `VULNORAIQ_EVIDENCE_DIR` | Directory for captured request/response evidence. | Optional | *(unset)* | Directory path | Real-target scans | No |

## Targets and scope control

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_ALLOWED_TARGET_HOSTS` | Deployment-wide allowlist of target hosts. Nothing outside it is contacted. | Optional | *(empty — no extra restriction)* | `api.internal.example,*.lab.example` | Target adapters | No |
| `VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS` | Permits synthetic demo/fixture targets. Never enable against real systems. | Optional | `false` | `true`, `false` | Scanner, web server | No |

Individual targets may reference their own credential variable through
`token_env_var` / `auth_token_env` in the target definition (for example
`auth_token_env: MY_AGENT_TOKEN`). Those variables are **sensitive**; supply
them from a secret store, never from a tracked file.

## Docker and Agent Lab

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_DOCKER_BINARY` | Docker executable name or path. | Optional | `docker` | Executable name/path | Docker boundary | No |
| `VULNORAIQ_DOCKER_COMMAND_TIMEOUT` | Timeout for a single `docker` invocation, in seconds. | Optional | `600` | Positive integer | Docker boundary | No |
| `VULNORAIQ_AGENT_NETWORK` | Docker network agent containers join. | Optional | `vulnoraiq_vulnoraiq-lab` | Docker network name | Agent Lab, agent host | No |
| `VULNORAIQ_AGENT_LAB_ROOT` | Root directory for Agent Lab state. | Optional | `/data/agent_lab` | Directory path | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_PROJECTS_ROOT` | Directory for imported (managed) agent projects. | Optional | `<lab root>/projects` | Directory path | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_DEPLOYMENTS` | Deployment registry file. | Optional | `<lab root>/deployments.yaml` | File path | Agent Lab | No |
| `VULNORAIQ_PROJECTS_ROOT` | Read-only directory of externally mapped agent projects. | Optional | `/app/projects` | Directory path | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS` | Git hosts Agent Lab may clone from. | Optional | `github.com,gitlab.com,bitbucket.org` | Comma-separated hosts | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_MAX_IMPORT_BYTES` | Maximum imported project size, in bytes. | Optional | `52428800` | Positive integer | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_MAX_IMPORT_FILES` | Maximum file count in an imported project. | Optional | `2000` | Positive integer | Agent Lab | No |
| `VULNORAIQ_AGENT_LAB_HEALTH_TIMEOUT` | Seconds to wait for a deployed agent to serve HTTP before the deploy is aborted. | Optional | `30` | Positive integer | Agent Lab | No |

## Assistant (Nora)

The in-app assistant is optional. Without the `assistant` extra installed,
VulnoraIQ falls back to templated explanations and none of these apply.

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_ASSISTANT_PROVIDER` | Assistant provider identifier. | Optional | `local` | `local` | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL` | Default assistant model name. | Optional | `nora-assistant` | Model name | Assistant | No |
| `VULNORAIQ_ASSISTANT_ALLOWED_MODELS` | Comma-separated models a client may request. | Optional | The default model | Model names | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL_DIR` | Directory holding local GGUF weights. | Optional | Platform cache directory | Directory path | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL_PATH` | Explicit path to a GGUF file. | Optional | *(unset)* | File path | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL_FILE` | GGUF file name inside the model directory. | Optional | Built-in name | File name | Assistant | No |
| `VULNORAIQ_ASSISTANT_LOCAL_MODEL_FILE` | Alternative local GGUF file name. | Optional | *(unset)* | File name | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL_REPO` | Hugging Face repository used for first-run download. | Optional | Built-in repository | `owner/repo` | Assistant | No |
| `VULNORAIQ_ASSISTANT_MODEL_URL` | Direct URL used for first-run download. | Optional | *(unset)* | HTTPS URL | Assistant | No |
| `VULNORAIQ_ASSISTANT_AUTODOWNLOAD` | Allow downloading weights on first use. | Optional | `true` | `true`, `false` | Assistant | No |
| `VULNORAIQ_ASSISTANT_GPU_LAYERS` | Layers to offload to GPU. `auto` tries GPU then falls back to CPU. | Optional | `auto` | `auto`, integer | Assistant | No |
| `VULNORAIQ_ASSISTANT_CTX` | Assistant context window, in tokens. | Optional | Built-in default | Positive integer | Assistant | No |
| `VULNORAIQ_ASSISTANT_READ_ROOT` | Root directory the assistant may read documentation from. | Optional | Repository root | Directory path | Assistant tools | No |
| `VULNORAIQ_ASSISTANT_FETCH_MAX_BYTES` | Maximum bytes fetched by the assistant's web tool. | Optional | Built-in default | Positive integer | Assistant tools | No |
| `VULNORAIQ_CVE_TIMEOUT` | Timeout for CVE lookups, in seconds. | Optional | Built-in default | Positive number | CVE lookup | No |

## Agent Lab model providers

These supply defaults for the provider presets offered when deploying an agent.
They are not used by VulnoraIQ itself.

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_OLLAMA_BASE_URL` | Default Ollama base URL offered in the preset. | Optional | `http://host.docker.internal:11434/v1` | URL | Agent Lab | No |
| `VULNORAIQ_OLLAMA_MODEL` | Default Ollama model name. | Optional | *(empty)* | Model name | Agent Lab | No |
| `VULNORAIQ_LMSTUDIO_BASE_URL` | Default LM Studio base URL. | Optional | `http://host.docker.internal:1234/v1` | URL | Agent Lab | No |
| `VULNORAIQ_LMSTUDIO_MODEL` | Default LM Studio model name. | Optional | *(empty)* | Model name | Agent Lab | No |
| `VULNORAIQ_OPENROUTER_MODEL` | Default OpenRouter model name. | Optional | *(empty)* | Model name | Agent Lab | No |

An API key supplied when deploying an agent is passed to that agent's container
as `OPENAI_API_KEY` (and `OPENROUTER_API_KEY` for OpenRouter). It is **sensitive**
and is redacted from deployment records and logs.

## Release tooling

| Variable | Purpose | Required | Default | Valid values | Used by | Sensitive |
| --- | --- | --- | --- | --- | --- | --- |
| `VULNORAIQ_RELEASE_VERSION` | Overrides the version stamped into a release package. | Optional | Version from `pyproject.toml` | Version string | Release packaging | No |

## Safe example

```text
VULNORAIQ_RUN_MODE=docker_lab
VULNORAIQ_AUTH_MODE=token
VULNORAIQ_ADMIN_TOKEN=<generate-a-random-token-of-at-least-20-characters>
VULNORAIQ_MAX_CONCURRENT_SCANS=2
```

## Related

- [Configuration reference](configuration.md) — the YAML configuration files.
- [Secrets handling](../security/secrets.md) — where credentials are allowed to live.
