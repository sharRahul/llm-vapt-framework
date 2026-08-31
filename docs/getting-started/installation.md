# Installation and deployment

How to install and deploy VulnoraIQ `0.3.0`, and the posture each path is supported for.

> **Supported posture:** self-hosted laptop/workstation/internal-server AI security testing lab for approved assessments.  
> **Safe default:** Docker Compose lab with loopback-only WebUI publishing.  
> **Not claimed:** certified VAPT-grade assurance or permission to test systems without explicit approval.

## 1. Recommended Docker-first lab

Use this path for local AI-agent testing, target validation, scan execution, evidence capture, reports, and WebUI target management.

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open <http://localhost:8787>.

The WebUI is published on host loopback only through `127.0.0.1:8787:8787`. Keep this posture for single-user laptop/workstation operation.

The Docker lab sets:

```text
VULNORAIQ_CONFIG_DIR=/app/config
VULNORAIQ_TARGET_CONFIG=targets.docker.yaml
VULNORAIQ_JOB_STORE_PATH=/data/jobs.db
VULNORAIQ_WEB_OUTPUT_ROOT=/data/reports
VULNORAIQ_EVIDENCE_DIR=/data/evidence
```

## 2. Docker services

| Service | Description |
| --- | --- |
| `vulnoraiq-web` | Hosted WebUI, scanner, CLI, SQLite job store, reports, evidence, audit logs, healthcheck. |
| `test-runner` | Optional test profile service (includes mock agent). |

The lab network is private/internal. Do not replace it with host networking for normal use.

## 3. Production-mode internal server

For shared/internal-server use, run behind a reverse proxy with TLS and enable auth.

```bash
export VULNORAIQ_ENV=production
export VULNORAIQ_AUTH_ENABLED=true
export VULNORAIQ_ADMIN_TOKEN="$(openssl rand -hex 32)"
export VULNORAIQ_JOB_STORE_BACKEND=sqlite
export VULNORAIQ_JOB_STORE_PATH=/data/jobs.db
export VULNORAIQ_WEB_OUTPUT_ROOT=/data/reports
export VULNORAIQ_EVIDENCE_DIR=/data/evidence
export # Legacy/user-file auth path is disabled for production; keep VULNORAIQ_WEB_USERS_PATH unset.

python scripts/validate_runtime_production_config.py
vulnoraiq-web --host 127.0.0.1 --port 8787
```

Production mode fails closed when required controls are missing or unsafe.

## 4. Production Checklist

Before exposing the service beyond local loopback, confirm:

- `VULNORAIQ_ADMIN_TOKEN` is set to a strong secret;
- `VULNORAIQ_WEB_USERS_PATH` is not used as a production credential source;
- the service is behind a trusted reverse proxy;
- TLS is enabled at the reverse proxy;
- `/healthz`, `/readyz`, and `/metrics` are reachable only as intended;
- audit logs are stored under a controlled path;
- backup and restore procedures for SQLite, reports, and evidence are tested;
- retention policy is defined;
- only approved targets and safety profiles are configured.

## 5. Reverse proxy, identity, and TLS

For remote internal access:

- terminate TLS at a trusted reverse proxy;
- keep `vulnoraiq-web` bound to loopback or an internal network;
- configure trusted proxy CIDRs before trusting forwarded headers;
- use strong environment-backed tokens or trusted reverse-proxy identity;
- protect `/healthz`, `/readyz`, and `/metrics` according to your internal monitoring model;
- store logs, reports, and backups in controlled locations with retention rules.

Trusted proxy identity is currently the enterprise identity bridge. Direct OIDC/JWT support is intentionally deferred and documented in `docs/future-plans/OIDC_JWT_AUTH_PLAN.md`.

## 6. Local standalone launcher

The local launcher remains supported for laptop/workstation development use.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
python launch-vulnoraiq-webui.py
```

Launcher mode is loopback/local. Do not use launcher-mode auth-disabled defaults for shared deployments.

## 7. Validation and data paths

Run before release or shared deployment:

```bash
ruff check .
mypy .
pytest -q
python -m pip check
pip-audit
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
python scripts/validate_runtime_production_config.py
```

For browser flow validation:

```bash
npm install
npx playwright install chromium --with-deps
npm run test:webui:hosted
```

For Docker validation:

```bash
python scripts/docker_smoke_test.py
```

| Path | Purpose |
| --- | --- |
| `/data/jobs.db` | SQLite job persistence. |
| `/data/reports` | Markdown, JSON, SARIF, dashboard, and HTML outputs. |
| `/data/evidence` | Evidence files. |
| `/data/audit` | Structured audit logs. |

Back up SQLite and report/evidence paths according to the runbook before upgrades or release validation.

## 8. Deployment limitations

The current codebase is suitable for self-hosted local/internal use with documented controls. Remaining maturity items include direct OIDC/JWT, SIEM-specific rule packs, native OS certificate-signed installers, multi-instance shared state, external independent review, and stronger approved-environment validation.

For approved internal GenAI validation, start from `config/targets/templates/`, keep `dry_run: true` until change approval, reference credentials only via environment variables, configure host allow-lists and rate limits, and review evidence handling before retaining reports.

## Related

- [Configuration](configuration.md) — what you actually need to set.
- [Environment variables](../reference/environment-variables.md) — every variable, with defaults and sensitivity.
- [Secrets](../security/secrets.md) — where credentials may live.
- [Troubleshooting](../guides/troubleshooting.md) — when startup does not go to plan.
