# Migration guide: VulnoraIQ 0.3.0

This guide covers migration from legacy `0.0.1.x` style deployments to the current `0.3.0` codebase.

## Current migration summary

| Area | Legacy state | Current `0.3.0` state |
| --- | --- | --- |
| Deployment default | Host-native demo/server | Docker-first safe lab for real local AI-agent testing. |
| WebUI | Legacy/static console path | React 18 + TypeScript console built to `webui/static/console/` and served by `webui/hosted_server.py`. |
| Target testing | Demo-first and limited templates | Real authorised target adapters, runtime target APIs, validation, safety profiles. No default or mock targets. |
| Target config | `config/targets.yaml` only | Docker uses `config/targets.docker.yaml`; host-native uses `config/targets.yaml`. Both are empty by default. |
| Job store | JSON-style local jobs | SQLite job store with WAL, foreign keys, busy timeout, schema versioning. |
| Auth | Config/fallback style | Env-backed token auth or trusted reverse-proxy identity; production mode fails closed. |
| Security hardening | Limited | CSRF, rate limiting, request limits, security headers, trusted proxy checks, artifact path protection. |
| Reports/evidence | Basic output | Markdown, JSON, SARIF, dashboard, HTML reports, evidence paths, audit logs. |
| CI | Basic checks | Python matrix, lint, mypy, tests, dependency audit, metadata/readiness validators, hosted WebUI flow, demo scan, functional acceptance. |
| GenAI/OWASP/Agentic | Planning-heavy | Current-scope validators, scenarios, mappings, and readiness docs. |

## Recommended migration path

1. Create a clean checkout of the current repository.
2. Preserve old reports, job files, and local config files outside the repo.
3. Review new docs:
   - `README.md`
   - `docs/guides/lab-mode.md`
   - `docs/getting-started/installation.md`
   - `docs/guides/targets.md`
   - `docs/guides/web-console.md`
4. Start with Docker Compose:

```bash
docker compose build
docker compose up -d
```

5. Review the target configuration docs and configure your own targets.

6. Run a scan against your configured target:

```bash
docker compose exec vulnoraiq-web vulnoraiq scan --target <target_name> --profile ai_agent_foundation --authorised
```

7. Recreate any old custom targets using the current target schema and safety profile rules.

## Target config migration

Legacy host-native targets should be reviewed before use. For each custom target:

- confirm ownership/authorisation;
- set owner/contact metadata where possible;
- avoid committed secrets;
- use environment-variable token references;
- define response extraction paths;
- add timeout/rate limits;
- assign a safety profile;
- validate the target before scanning.

Docker lab targets should use Docker service names, not host `localhost`.

## Job store migration

Do not manually edit the SQLite job store. For legacy reports, keep them as archived report artifacts. New runs should write to the current SQLite path and report/evidence directories.

Default Docker paths:

- `/data/jobs.db`
- `/data/reports`
- `/data/evidence`
- `/data/audit`

## WebUI migration

The legacy static console is gone. Current WebUI assets are built from `webui/console/` into `webui/static/console/`.

To rebuild WebUI assets:

```bash
cd webui/console
npm install
npm run typecheck
npm run build
```

## Production-mode migration

For internal shared use:

```bash
export VULNORAIQ_ENV=production
export VULNORAIQ_AUTH_ENABLED=true
export VULNORAIQ_ADMIN_TOKEN="your-strong-token-min-20-chars"
python scripts/validate_runtime_production_config.py
vulnoraiq-web --host 127.0.0.1 --port 8787
```

Use reverse proxy/TLS and trusted proxy configuration for remote internal access.

## Migration validation

```bash
ruff check .
mypy .
pytest -q
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
```

## Breaking/important changes

- Python minimum is `>=3.10`.
- The supported WebUI is the React console, not the removed legacy static console.
- Real target tests should use Docker-first lab defaults unless you intentionally run host-native local targets.
- All targets require explicit authorisation. Scan `--target` is required (no default).
- Production mode requires safe auth/runtime configuration.
- Framework coverage claims remain scoped and require human review.
