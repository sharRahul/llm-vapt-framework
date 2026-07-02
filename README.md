# VulnoraIQ

**VulnoraIQ** is a self-hosted internal application for controlled laptop/server AI security testing of LLM applications, RAG systems, AI agents, and orchestration layers.

It provides a browser WebUI, CLI, Agent Lab, target configuration, scan execution, evidence capture, reports, audit logs, and validation workflows. Findings are assessment evidence for human review; VulnoraIQ does not claim certified VAPT-grade assurance. See [`docs/ASSESSMENT_ASSURANCE.md`](docs/ASSESSMENT_ASSURANCE.md).

For operator setup and usage, see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md). For the maintained documentation index, see [`docs/README.md`](docs/README.md).

## Product direction

VulnoraIQ has two explicit run modes.

| Mode | Best for | Where VulnoraIQ runs | Where imported AI agents run | Report location |
| --- | --- | --- | --- | --- |
| **Desktop Mode** | Normal desktop/laptop users | Host machine | Docker containers | `./scan-reports/` |
| **Advanced Docker Lab Mode** | Servers, VMs, CI, dev/test labs | Docker Compose container | Docker containers | Docker `/data` volume or mapped folders |

Desktop Mode and Docker Lab Mode use a **local single-user/admin WebUI session** by default. Production or shared internal-server deployments must explicitly enable token auth and provide an admin token.

```text
User clicks launcher
  -> VulnoraIQ WebUI opens
  -> User imports/selects an AI agent in Agent Lab
  -> VulnoraIQ stores WebUI imports under agent-lab/projects/
  -> User configures API key, local LLM, remote LLM, CPU/GPU runtime
  -> Docker runs only the sandboxed imported agent/runtime
  -> VulnoraIQ auto-creates a target
  -> User runs authorised scans from the WebUI
  -> Results are visible on the dashboard and saved under scan-reports/
```

## Current status

| Area | Status |
| --- | --- |
| Version | `0.3.0` beta |
| WebUI | React browser console served by `webui.assistant_server` / `vulnoraiq-web`. |
| Desktop Mode | Primary launchers start VulnoraIQ on the host, create local `scan-reports/`, `agent-lab/`, and optional mapped `projects/` folders, and open a guarded local single-user/admin WebUI session. |
| Advanced Docker Lab Mode | Full Docker Compose lab remains available through explicit Docker Lab launchers and manual Compose commands. |
| Agent Lab | Experimental workflow at `/agent-lab` for importing real AI-agent projects through local folder upload, ZIP upload, Git import, or mapped folders; configuring provider/runtime settings; building/running agents in Docker; auto-creating targets; and launching scans. |
| Persistence | SQLite job store, reports, evidence, audit logs, and Agent Lab metadata. |
| Identity | `local_admin` mode for desktop/lab scope; production token auth and reverse-proxy identity are available for hardened internal deployments. Direct OIDC/JWT is future work. |
| Documentation | Active docs now point to current guides/status/assurance docs. Completed or superseded planning docs are staged under `docs/ready-to-remove/` for maintainer review. |
| CI | Normal PR/main checks are consolidated into `.github/workflows/ci.yml`. The duplicate `Python CI` workflow has been removed. |

## Prerequisites

| Run path | Requirements |
| --- | --- |
| Desktop Mode from source/package | Docker Engine or Docker Desktop with Docker Compose v2, Python 3.10 or newer, internet access for first dependency/image builds, and a modern browser. |
| Advanced Docker Lab / Docker GUI lab | Docker Engine or Docker Desktop with Docker Compose v2, internet access for first image/dependency builds, and a modern browser. |
| Agent Lab GPU mode | Host GPU container support. Agent Lab passes Docker GPU runtime flags; it does not install host GPU drivers. |
| Local Ollama / LM Studio | Provider running on the host. Agent containers reach host providers through `host.docker.internal` where supported/configured. |
| Development tests | Python 3.10 or newer, Node.js 20 or newer, npm, Playwright browser dependencies, and a modern browser. |

## Quick start: Desktop Mode

Use this for normal laptop/workstation use.

| Platform | Launcher |
| --- | --- |
| Windows | `launch-vulnoraiq-webui.bat` |
| macOS | `launch-vulnoraiq-webui.command` |
| Linux | `launch-vulnoraiq-webui.sh` |

Desktop Mode performs the following steps:

1. starts VulnoraIQ natively on the host;
2. opens a guarded local single-user/admin WebUI session on `127.0.0.1` using `VULNORAIQ_AUTH_MODE=local_admin`;
3. checks Docker is available for sandboxed Agent Lab runtimes;
4. creates local output folders;
5. starts the WebUI on `127.0.0.1:8787`;
6. opens the browser.

Desktop Mode **does not create a `vulnoraiq-web` Docker container**. Docker containers appear only when you import/deploy an AI agent or local test runtime. Use Docker Lab Mode when you intentionally want the VulnoraIQ WebUI itself to run inside Docker.

Desktop Mode folder contract:

```text
scan-reports/
  jobs.db
  reports/
  evidence/
  audit/
  exports/

agent-lab/
  projects/          # WebUI imports: local folder upload, ZIP upload, Git import
  deployments.yaml

projects/            # optional mapped AI-agent folders
  <agent-name>/
```

After startup, open:

```text
http://127.0.0.1:8787
```

Agent Lab is available at:

```text
http://127.0.0.1:8787/agent-lab
```

## Quick start: Advanced Docker Lab Mode

Use this for servers, VMs, CI, or fully containerised development/testing.

| Platform | Launcher |
| --- | --- |
| Windows | `launch-vulnoraiq-docker-lab.bat` |
| macOS | `launch-vulnoraiq-docker-lab.command` |
| Linux | `launch-vulnoraiq-docker-lab.sh` |

Manual equivalent:

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open:

```text
http://127.0.0.1:8787
```

Useful Docker Lab commands:

```bash
docker compose exec vulnoraiq-web vulnoraiq targets list
docker compose exec vulnoraiq-web vulnoraiq reports list
docker compose exec vulnoraiq-web vulnoraiq jobs list
docker compose logs vulnoraiq-web
```

Stop Docker Lab Mode:

```bash
docker compose down
```

Only use this when you intentionally want to delete local Docker volumes, jobs, reports, evidence, audit logs, and Agent Lab imports:

```bash
docker compose down -v
```

## Agent Lab workflow

Agent Lab is the WebUI flow for testing real AI agents.

```text
Import Agent
  -> Configure LLM/API keys
  -> Select CPU/GPU runtime
  -> Build/Run sandboxed Docker container
  -> Auto-create VulnoraIQ target
  -> Run authorised scan
  -> Review dashboard, evidence, and reports
```

Recommended import options:

| Option | Typical use |
| --- | --- |
| **Local folder upload** | Select an AI-agent source folder in the browser and import it into managed `agent-lab/projects/`. This is the preferred desktop flow. |
| **ZIP upload** | Upload a prepared project archive. |
| **Git URL** | Import from an approved Git host. |
| **Mapped folder** | Place projects under `./projects/<agent-name>/` and refresh them as read-only mapped projects. |

Supported provider patterns include Ollama, LM Studio, OpenRouter, custom OpenAI-compatible endpoints, and custom environment variables.

In Desktop Mode, VulnoraIQ scans sandboxed agents through published localhost endpoints. In Advanced Docker Lab Mode, VulnoraIQ can scan sandboxed agents through Docker container DNS.

Agent Lab remains experimental because it builds and runs operator-provided code. Import and test only code and systems you own or are explicitly authorised to assess.

## Configure a direct target

You do not need Agent Lab to test an AI system you already run. In the **Targets** workspace, click **Add** and author a direct endpoint:

| Field | Example |
| --- | --- |
| Target type | `http_json`, `chat_completions`, `ollama_generate`, `webhook_json`, `rag_query`, `agent_tool_loop` |
| Base URL | `http://127.0.0.1:8000` (loopback/private host of the system under test) |
| Endpoint path | `/v1/chat/completions` |
| Model | `gpt-4o-mini` / `llama3` (chat/Ollama types) |
| Response extraction path | `choices.0.message.content` |
| Request body template | `{ "prompt": "{{prompt}}" }` (or `{}` to use the type default) |

Use **Test connectivity** to validate, then **Start authorised scan**. External (non-loopback/non-private) hosts are blocked unless `allow_external` is explicitly enabled for a system you own or are authorised to assess. The CLI reads the same targets from `config/targets.yaml`.

## Source/package local development

Install from a source checkout:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

Run Desktop Mode backend directly:

```bash
python scripts/desktop_launch.py
```

Run Docker Lab backend directly:

```bash
python scripts/bootstrap_launch.py
```

Run only the WebUI server in guarded local single-user/admin mode:

```bash
VULNORAIQ_AUTH_MODE=local_admin vulnoraiq-web --host 127.0.0.1 --port 8787
```

`VULNORAIQ_AUTH_ENABLED=false` remains only as a backward-compatible alias for older launchers and Compose files. New code should use `VULNORAIQ_AUTH_MODE=local_admin`.

## Security boundary

VulnoraIQ is intended for authorised local or controlled internal use.

- Keep local launchers bound to `127.0.0.1`.
- Do not expose the WebUI on a shared network without production auth, TLS, reverse proxy controls, audit retention, and backups.
- Store API keys outside the repository and pass them through approved environment/secret handling.
- Treat reports and findings as evidence requiring human review.
- Review imported Agent Lab source before running it.

Production/internal-server mode requires explicit hardening. For a shared internal server, configure production auth, a trusted reverse proxy, TLS, audit retention, and backups before exposing the service.

```bash
export VULNORAIQ_ENV=production
export VULNORAIQ_AUTH_MODE=token
export VULNORAIQ_ADMIN_TOKEN=<strong-admin-token>
export VULNORAIQ_JOB_STORE_BACKEND=sqlite
export VULNORAIQ_JOB_STORE_PATH=/data/jobs.db
export VULNORAIQ_WEB_OUTPUT_ROOT=/data/reports
python scripts/validate_runtime_production_config.py
vulnoraiq-web --host 127.0.0.1 --port 8787
```

Use trusted reverse-proxy identity only when the proxy authenticates users and strips spoofed identity headers. Direct OIDC/JWT remains future work and is not required for current local single-user use.

## Validation

Core validation commands:

```bash
ruff check .
mypy .
pytest -q
python -m pip check
pip-audit
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_aitg_full_coverage.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
python scripts/validate_runtime_production_config.py
```

WebUI browser flow:

```bash
cd webui/console
npm install
npm run typecheck
npm run build
cd ../..
npm install
npx playwright install chromium --with-deps
npm run test:webui:hosted
```

Normal PR/main CI runs through `.github/workflows/ci.yml`. Release artifact builds, Python package publishing, and supply-chain image/SBOM workflows remain separate release/manual workflows so they do not duplicate the normal CI gate.
