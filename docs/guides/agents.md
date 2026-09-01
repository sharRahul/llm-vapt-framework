# Experimental Agent Lab

The Agent Lab is an experimental VulnoraIQ WebUI workflow for importing a real AI-agent project, configuring its model provider, running it in Docker, auto-registering a VulnoraIQ target, and launching an authorised scan.

Open **Projects** in the VulnoraIQ console (`http://localhost:8787/#/projects`).
The old `/agent-lab` path redirects there so existing bookmarks remain useful.

## Authorized-use boundary

Agent Lab is intended for **authorized AI red teaming, security testing, and pre-deployment vulnerability discovery**: testing internal AI agents before deployment, validating authorized third-party/open-source agents in a local lab, reproducing vulnerabilities in deliberately vulnerable applications, and generating evidence for remediation sign-off.

Only import, deploy, and scan agents, models, or endpoints you own or are explicitly authorized to test. For External endpoint and Hybrid deployment modes the WebUI requires an explicit authorization acknowledgement before it will register the target, and only approved credentials should be configured. Credentials are passed to the runtime as environment variables and are never persisted in deployment records or target YAML.

## Deploy any agent → working scannable target

Deploying an agent now auto-produces a **working** scan target that matches the agent's real HTTP contract — with **no manual `docker` commands and no manual target edits**:

```text
import agent source → build image → run container (free host port)
  → health-check → auto-register a target (correct method/endpoint/body/response)
  → scan
```

The analyzer recovers the request/response contract from the agent's source and Agent Lab derives the target config from it:

- **Method / endpoint** — the inference endpoint is selected by ranking detected routes (paths such as `chat`, `ask`, `get`, `query`, `predict`, `invoke`, and routes that read a user param score higher; infrastructure routes such as `/`, `/health`, `/refresh`, `/docs`, and static paths are skipped).
- **Request body** — keyed by the detected user parameter (`msg` / `prompt` / `input` / `query` / …). For `GET` endpoints the `http_json` adapter sends the body as query parameters, so a chatbot exposed as `GET /get?msg=` registers correctly.
- **Response extraction** — plain-text responses register with an empty extraction path (the adapter returns the whole body); JSON responses use the detected key (e.g. `response`, `output`) or fall back to the whole body.

An operator can still override any of these from the target editor; explicit overrides always win.

## Deployment modes

| Mode | Behaviour |
| --- | --- |
| Containerized local agent | Build the image, run the container on a free host port, health-check it, and register a target for the local app endpoint. |
| Hybrid agent | Run the local app container but point it at an external model provider (Ollama, vLLM, LM Studio, OpenAI-compatible, cloud). The app endpoint is the scan target; the external model configuration is injected as environment variables. Requires an authorization acknowledgement. |
| External endpoint agent | No Docker build. The operator supplies a reachable base URL and the target contract; Agent Lab registers an OpenAI-compatible or custom HTTP target directly. Requires an authorization acknowledgement. |

## Run-mode-aware reachability and free host ports

Agent Lab publishes the container on `127.0.0.1:<free-host-port>:<container-port>` and picks a free host port automatically, so a busy host port (for example host `5000` already in use) never blocks a deployment.

The registered target's `base_url` depends on where VulnoraIQ itself runs:

| VulnoraIQ run mode | Registered `base_url` |
| --- | --- |
| Desktop Mode (on the host) | `http://127.0.0.1:<host-port>` |
| Docker Lab Mode (in a container on the agent network) | `http://<container-name>:<container-port>` |

The run mode is detected from `VULNORAIQ_RUN_MODE`, `VULNORAIQ_IN_CONTAINER`, or the presence of `/.dockerenv`.

## What it does

| Step | Capability |
| --- | --- |
| Import Agent | Import a real project from an approved Git host, upload a ZIP archive, select and upload a local folder from the browser, or use a mapped `./projects/<name>` directory. |
| Configure LLM/API keys | Select Ollama, LM Studio, OpenRouter, a custom OpenAI-compatible endpoint, or custom environment variables. |
| Select CPU/GPU | Run CPU-only, all NVIDIA GPUs, or a specific GPU device list. |
| Build/Run | Use the project's Dockerfile or generate one for common Python/Node agent projects in the managed Agent Lab project area. |
| Auto-create target | Register a runtime target using `http_json` or `chat_completions` target contracts. |
| Test with VulnoraIQ | Launch an authorised scan against the generated runtime target from the same WebUI flow. |

No demo, mock, fake, or fixture projects are created by this workflow. Project IDs containing those terms are rejected in normal Agent Lab runtime.

## Import modes

### Local folder upload

Use this as the recommended desktop/laptop flow when the AI agent source code already exists on your machine.

1. Open **Projects** in the console.
2. Choose **Local folder upload**.
3. Select the local AI-agent source folder in the browser folder picker.
4. Optionally provide a Project ID. If omitted, VulnoraIQ derives it from the selected top-level folder name.
5. Click **Upload Selected Folder**.

The browser packages the selected folder into a ZIP archive and sends it to the existing Agent Lab archive import API. The backend extracts it into managed Agent Lab storage:

```text
./agent-lab/projects/<project-id>/          # Desktop Mode
/data/agent_lab/projects/<project-id>/      # Docker Lab Mode
```

This avoids giving the backend permission to read arbitrary local filesystem paths. The browser only sends files the operator explicitly selected.

Browser support note: folder selection uses the browser directory-upload control. Chromium-based browsers and current Edge/Chrome support it. If a browser does not expose folder selection, use ZIP archive import instead.

### ZIP archive import

Use this when folder upload is not available or when you already have a prepared project archive.

The backend supports ZIP archive import at `POST /api/agent-lab/import/archive`. The archive is size-limited, file-count-limited, and extracted with path traversal checks into the managed Agent Lab project area.

### Git import

Use the Git URL form with an HTTPS repository URL. By default the allowed Git hosts are:

```text
github.com,gitlab.com,bitbucket.org
```

Configure this allow-list with:

```text
VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS=github.com,gitlab.com,bitbucket.org
```

Git URLs must not embed credentials. Private repository import should use a controlled host-side checkout, local folder upload, ZIP upload, or a future credential broker rather than placing credentials in the URL.

### Mapped folder

Mapped folders remain available for operators who want a persistent host-visible project location.

In Desktop Mode, the launcher creates:

```text
./projects/
```

Place projects there as:

```text
./projects/<agent-name>/
```

In Docker Lab Mode, Compose mounts:

```text
./projects:/app/projects:ro
```

Folders placed there appear as read-only mapped projects after refresh. If a mapped project has no Dockerfile, either add one to that folder or import/upload it into the managed Agent Lab area so VulnoraIQ can generate one.

## Provider configuration

The Agent Lab exposes provider presets for:

| Provider | Typical endpoint |
| --- | --- |
| Ollama | `http://host.docker.internal:11434/v1` |
| LM Studio | `http://host.docker.internal:1234/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Anthropic | `https://api.anthropic.com/v1` |
| Custom OpenAI-compatible | Operator-provided base URL |
| Custom environment only | Operator-provided environment variables |

The backend maps provider settings into common environment variables used by many agent frameworks:

```text
OPENAI_BASE_URL
OPENAI_API_BASE
OPENAI_API_KEY
OPENROUTER_API_KEY
ANTHROPIC_BASE_URL
ANTHROPIC_API_KEY
ANTHROPIC_MODEL
OLLAMA_HOST
MODEL
OPENAI_MODEL
VULNORAIQ_LLM_PROVIDER
VULNORAIQ_LLM_MODEL
```

API keys are not written to the repository or runtime target YAML. They are passed to the launched Docker container as runtime environment variables. Operators should still treat Docker inspect output, process metadata, and container logs as sensitive.

## CPU and GPU runtime

| UI option | Docker runtime behaviour |
| --- | --- |
| CPU only | No GPU flags are added. |
| All NVIDIA GPUs | Adds `--gpus all`. |
| Specific GPU device IDs | Adds `--gpus device=<ids>`. |

GPU mode requires the host Docker runtime to be configured for NVIDIA GPU containers. The Agent Lab does not install host GPU drivers.

## Docker build/run behaviour

The Agent Lab builds a project image tagged as:

```text
vulnoraiq-agent-lab-<project-id>
```

It runs a container named:

```text
vulnoraiq-agent-lab-<project-id>
```

The container is attached to the VulnoraIQ lab network and is labelled with `vulnoraiq.agent=agent-lab` and `vulnoraiq.agent.id=<project-id>`.

The run command applies:

```text
--security-opt no-new-privileges:true
--cap-drop ALL
```

Optional runtime limits include memory and CPU settings.

## Auto-created runtime targets

The deployment step registers a runtime target in the same runtime target store used by the WebUI target manager.

Generated target defaults:

```yaml
authorisation_required: true
environment: agent_lab
safety_profile: local_lab_safe
```

Supported generated target types:

| Target type | Use case |
| --- | --- |
| `http_json` | Agent endpoint accepts JSON (`{ "prompt": "..." }`), query params (`GET /get?msg=`), or returns plain text. Method, endpoint, body key, and response extraction are derived from the detected contract. |
| `chat_completions` | Agent exposes an OpenAI-compatible `/v1/chat/completions` endpoint. |

The deploy response returns the auto-registered `target_ids`, the reachable `base_url`, the `health_status`, and the selected `endpoint_contract`, so the operator can go straight to a scan.

## Deployment reliability and observability

- **Health gate** — after the container starts, Agent Lab waits (with retries, `VULNORAIQ_AGENT_LAB_HEALTH_TIMEOUT` seconds) for the reachable URL to accept connections before registering a target. A container that never becomes reachable does **not** register a broken target.
- **Cleanup on failure** — a failed health check removes the container (and surfaces its recent logs in the error) rather than leaking it; a failed build removes any Agent-Lab-generated `Dockerfile`.
- **Deployment metadata** — each deployment record persists `deployment_mode`, `image_tag`, `container_id`, `container_port`, `host_port`, `base_url`, `health_status`, `endpoint_contract`, `target_ids`, and `created_at`/`updated_at`. Raw API keys and secrets are never persisted.

## Deployment summary

After a deploy the WebUI shows a summary card with the detected contract, reachable URL, selected endpoint, target ID, container/host ports, deployment mode, and health status, plus one-click **Run baseline scan** and **Stop / remove deployment** actions.

## Testing flow

1. Start Desktop Mode or Docker Lab Mode.
2. Open **Projects** in the console.
3. Import a real agent project using **Local folder upload**, ZIP upload, Git import, or mapped folder refresh.
4. Select the imported/mapped project and review Project Analysis.
5. Configure the provider, model, and key/environment values.
6. Choose CPU/GPU mode and runtime limits.
7. Choose the target contract and endpoint path.
8. Build/run the agent.
9. Select the auto-created target.
10. Launch an authorised VulnoraIQ scan.
11. Review findings, evidence, and reports in the main WebUI.

## Cleanup

`POST /api/agent-lab/deployments/<id>/remove` tears down a deployed agent container and prunes its deployment record. The `<id>` may be the `deployment_id`, the `project_id`, or the `container_name`; it is resolved against the deployment registry to find the real container. The response reports `removed: true` only when a matching container actually existed and was removed, and `removed: false` (with `records_removed` for any stale metadata) otherwise, so a wrong or stale identifier cannot report a false success while leaving a container running.

## Security boundary

The Agent Lab requires Docker build/run access. In Desktop Mode this is through the host Docker CLI/API. In Docker Lab Mode this is provided through the Docker socket mount in the `vulnoraiq-web` container. Both are powerful and should be treated as experimental local-lab capabilities.

Do not expose the default WebUI beyond loopback unless production auth, reverse proxy, TLS, audit retention, and backup controls are configured.

## Configuration reference

| Variable | Purpose | Desktop Mode default | Docker Lab default |
| --- | --- | --- | --- |
| `VULNORAIQ_AGENT_LAB_ROOT` | Agent Lab data root. | `./agent-lab` | `/data/agent_lab` |
| `VULNORAIQ_AGENT_LAB_PROJECTS_ROOT` | Managed imported project root. | `./agent-lab/projects` | `/data/agent_lab/projects` |
| `VULNORAIQ_AGENT_LAB_DEPLOYMENTS` | Deployment metadata YAML. | `./agent-lab/deployments.yaml` | `/data/agent_lab/deployments.yaml` |
| `VULNORAIQ_PROJECTS_ROOT` | Mapped read-only project root. | `./projects` | `/app/projects` |
| `VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS` | Allowed Git import hosts. | `github.com,gitlab.com,bitbucket.org` | `github.com,gitlab.com,bitbucket.org` |
| `VULNORAIQ_AGENT_LAB_MAX_IMPORT_BYTES` | Max import size. | `52428800` | `52428800` |
| `VULNORAIQ_AGENT_LAB_MAX_IMPORT_FILES` | Max import file count. | `2000` | `2000` |
| `VULNORAIQ_AGENT_LAB_HEALTH_TIMEOUT` | Seconds to wait for a started container to become reachable before aborting. | `30` | `30` |
| `VULNORAIQ_AGENT_NETWORK` | Docker network for launched agents. | `vulnoraiq-desktop-agent-lab` | `vulnoraiq_vulnoraiq-lab` |
| `VULNORAIQ_IN_CONTAINER` | Set inside the VulnoraIQ container to force Docker Lab Mode reachability (container-DNS `base_url`). | unset | set |
