# Docker Lab mode

VulnoraIQ supports two local run modes:

- **Desktop Mode**: VulnoraIQ runs on the host machine and Docker is used only for sandboxed Agent Lab runtimes.
- **Docker Lab Mode**: VulnoraIQ itself runs inside Docker Compose, alongside sandboxed imported agents.

This document covers **Docker Lab Mode**, which is best for servers, VMs, CI, reproducible development labs, and full-stack container testing.

## Start Docker Lab mode with the platform launcher

| Platform | Launcher |
| --- | --- |
| Windows | `launch-vulnoraiq-docker-lab.bat` |
| macOS | `launch-vulnoraiq-docker-lab.command` |
| Linux | `launch-vulnoraiq-docker-lab.sh` |

Each Docker Lab launcher performs these steps:

1. checks Docker is installed and running;
2. runs `docker compose build`;
3. runs `docker compose up -d`;
4. shows `docker compose ps`;
5. waits for `vulnoraiq-web` to become healthy;
6. opens <http://127.0.0.1:8787> in the default browser.

## Manual Docker startup

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open <http://localhost:8787>.

The WebUI is published as `127.0.0.1:8787:8787`. Keep this loopback binding for normal laptop/workstation use. Do not change it to `8787:8787` unless you are intentionally moving to a shared/internal-server deployment with production auth, reverse proxy, TLS, and documented network controls.

## Services

| Service | Purpose |
| --- | --- |
| `vulnoraiq-web` | Non-root hosted WebUI and CLI container. Stores `/data/jobs.db`, `/data/reports`, `/data/evidence`, `/data/audit`, and Agent Lab imports under `/data/agent_lab`. |
| `test-runner` | Optional Docker-only utility service under the `test` profile. |

All services run on the private `vulnoraiq-lab` bridge network. The Compose file does not use host networking or privileged mode. Experimental Agent Lab intentionally uses local Docker engine access from the WebUI container so it can build and run imported agent projects.

## Current Docker target configuration

The Docker service sets:

```text
VULNORAIQ_CONFIG_DIR=/app/config
VULNORAIQ_TARGET_CONFIG=targets.docker.yaml
VULNORAIQ_JOB_STORE_PATH=/data/jobs.db
VULNORAIQ_WEB_OUTPUT_ROOT=/data/reports
VULNORAIQ_EVIDENCE_DIR=/data/evidence
VULNORAIQ_AGENT_LAB_ROOT=/data/agent_lab
VULNORAIQ_AGENT_LAB_PROJECTS_ROOT=/data/agent_lab/projects
```

Docker lab targets are defined in `config/targets.docker.yaml`. You must configure your own targets with real endpoints, or use Agent Lab to auto-create runtime targets for imported real agent projects.

## Experimental Agent Lab in Docker Lab mode

Open:

```text
http://localhost:8787/agent-lab
```

Agent Lab supports importing a real project, configuring model-provider environment, choosing CPU or GPU runtime options, building/running the agent, creating a runtime target, and launching an authorised scan.

In Docker Lab Mode, auto-created Agent Lab targets use container DNS, for example `http://vulnoraiq-agent-lab-<project>:8000`, because the scanner runs inside Docker on the same network.

For local LLM providers running on the host, Docker Compose configures `host.docker.internal` through the host gateway.

GPU mode requires host Docker support for GPU containers. Agent Lab only passes runtime options; it does not install host drivers.

## Desktop Mode comparison

Desktop Mode is documented in [Desktop Mode](desktop-mode.md). In that mode, VulnoraIQ runs on the host, reports are written under `scan-reports/`, Agent Lab projects are written under `agent-lab/`, and auto-created targets use published localhost ports so the host scanner can reach the sandboxed Docker container.

## CLI from Docker

```bash
docker compose exec vulnoraiq-web vulnoraiq targets list
docker compose exec vulnoraiq-web vulnoraiq targets validate --target <target_name>
docker compose exec vulnoraiq-web vulnoraiq scan --target <target_name> --profile ai_agent_foundation --authorised
docker compose exec vulnoraiq-web vulnoraiq reports list
docker compose exec vulnoraiq-web vulnoraiq jobs list
docker compose exec vulnoraiq-web vulnoraiq jobs show --job-id <job-id>
```

## WebUI workflow

1. Start Docker Compose through a Docker Lab launcher or manual Docker commands.
2. Open <http://localhost:8787>.
3. Use the target workspace to search/filter targets, or open `/agent-lab` to import and run a real agent.
4. Validate target connectivity.
5. Confirm the authorisation checklist.
6. Select a profile such as `ai_agent_foundation`, `baseline`, `rag`, `agent`, `full`, or a single focused profile.
7. Start the scan.
8. Review live progress, findings, policy status, recent jobs, and report outputs.
9. Update finding status/remediation actions when needed.

## Smoke and acceptance checks

```bash
python scripts/docker_smoke_test.py
python scripts/validate_target_configs.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
python scripts/validate_production_testing_readiness.py --run-functional --output-dir reports/output/production-readiness
```

For browser testing on a host with Playwright installed:

```bash
npm install
npx playwright install chromium --with-deps
npm run test:webui:hosted
```

## Stop the lab

```bash
docker compose down
```

Use a volume reset only when you intentionally want to remove jobs, reports, evidence, Agent Lab imports, and audit data:

```bash
docker compose down -v
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Launcher says Docker was not found | Install Docker Desktop or make sure the Docker CLI is on PATH. |
| Launcher says Docker is not running | Start Docker Desktop and wait until it is ready. |
| WebUI does not open | `docker compose ps`, then `docker compose logs vulnoraiq-web` |
| WebUI is not reachable from another device | Expected for the local lab; it is bound to `127.0.0.1` on the host |
| Target validation fails | Check the target endpoint is reachable from inside the container |
| No reports appear | Check `/data/reports` in the container and `VULNORAIQ_WEB_OUTPUT_ROOT` |
| Jobs are missing | Check `/data/jobs.db` and whether the Docker volume was reset |
| Browser tests fail locally | Confirm Playwright Chromium is installed and the environment can download browser binaries |

## Assurance boundary

Passing Docker smoke tests proves the lab wiring, target adapters, scanner path, and report/evidence generation work. It does not prove real-world target assurance or certified VAPT-grade coverage. Agent Lab scans are evidence from the imported agent runtime and still require human review.
