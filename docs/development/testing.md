# Testing

Three layers, run in this order when you change something:

| Layer | Command | Covers |
| --- | --- | --- |
| Python suite | `pytest -q` | Domain logic, HTTP handlers, persistence, adapters, Agent Lab, configuration, and repository invariants. |
| Console | `npm run typecheck` / `npm run build` in `webui/console` | TypeScript types and a production build. |
| Browser flow | `npm run test:webui:hosted` | The hosted console loading and starting a scan through the real API. |

## Python suite

```bash
pip install -e ".[dev]"
pytest -q
```

`tests/conftest.py` enables fixture targets (`VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS`)
and points the scanner at `config/targets.test.yaml`, so tests never touch a real
system. Nothing is excluded from the run: if a test is wrong, fix it rather than
ignoring the file.

Run a subset while iterating:

```bash
pytest tests/test_scan_pipeline_regressions.py -q
pytest -k "runtime_targets or agent_lab" -q
```

### What the suite covers

| Area | Files |
| --- | --- |
| Authorisation and target scope | `test_scanner_authorisation.py`, `test_owasp_top10_hardening.py`, `test_target_adapters.py`, `test_target_contract_validation.py` |
| Runtime target registry | `test_runtime_targets.py` |
| API behaviour and security controls | `test_webui_server.py`, `test_webui_auth_and_persistence.py`, `test_webui_auth_production.py`, `test_webui_request_errors.py`, `test_webui_artifact_security.py`, `test_webui_audit_logging.py`, `test_metrics.py` |
| Persistence and job lifecycle | `test_sqlite_job_store.py`, `test_backup_restore.py`, `test_scan_pipeline_regressions.py` |
| Agent Lab | `test_agent_lab_autotarget.py`, `test_agent_lab_smoke.py`, `test_agent_runtime_manifest.py` |
| Framework mappings | `test_owasp_*`, `test_mitre_atlas_*`, `test_ai_testing_guide_profiles.py` |
| Reporting | `test_policy_and_reporting.py`, `test_sarif_and_html_dashboard.py`, `test_report_diff.py`, `unit/test_report_generator.py` |
| Packaging, launchers, deployment baseline | `test_release_*`, `test_double_click_launchers.py`, `test_docker_only_launchers.py`, `test_production_hardening_status.py` |

`tests/test_scan_pipeline_regressions.py` is the regression file: each test names
the defect it guards against, so a reintroduced bug fails with an explanation.

## Quality gates

```bash
ruff check .
mypy .
```

`mypy` checks the whole tree with no blanket `ignore_errors`. Do not add a
file-level suppression to get past an error — narrow the type instead.

## Console

```bash
cd webui/console
npm ci
npm run typecheck     # tsc --noEmit
npm run build         # typechecks, then builds into webui/static/console/
```

`npm run build` is the gate: it fails on any type error before producing assets.
Commit the rebuilt `webui/static/console/` output with your change — see
[frontend build](frontend-build.md).

## Browser flow

```bash
npm install
npx playwright install chromium --with-deps
npm run test:webui:hosted
```

This starts a real server (`scripts/webui_test_server.py`) with fixture targets
and local-admin auth, loads the built console, fetches a CSRF token, starts a
scan through the API, and confirms the job is created. It deliberately stops
short of waiting for scan completion so the gate stays bounded and does not
depend on assessment duration.

The built console must exist before running it — run the console build first.

## Validators

These are separate CLIs that check configuration and framework data against the
implementation. CI runs all of them:

```bash
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_aitg_full_coverage.py
python scripts/validate_target_configs.py
python scripts/validate_assurance_bundle.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
python scripts/validate_runtime_production_config.py
```

Add `--run-functional` to the readiness validator to include a functional
acceptance run.

## Container

```bash
docker compose build
docker compose up -d
python scripts/container_smoke_test.py
docker compose down -v
```

CI builds the image, waits for the container health check, and calls `/healthz`
and `/readyz` — a successful build alone is not treated as proof it runs.

## CI

`.github/workflows/ci.yml` is the only workflow. Every job is gated on the event
that should reach it, so nothing runs twice and a push never builds a release.

| Job | Runs on | What it does |
| --- | --- | --- |
| `test` | push, PR, release, manual `run: ci`/`release` | tracked-`.env` check, `pip check`, `pip-audit`, `ruff`, `mypy`, `--check-config`, `pytest` across Python 3.10–3.12, the validators, the console build, the hosted browser flow, and a fixture-target scan producing every report format. |
| `docker` | push, PR, manual `run: ci` | Builds the image, waits for the container health check, and runs the Agent Lab integration tests. |
| `security` | push, PR, manual `run: ci`/`security` | Trivy filesystem and image scans, SBOMs, and — on `main` and tags — a signed GHCR image. |
| `atlas-refresh` | weekly schedule, manual `run: atlas` | Validates the MITRE ATLAS mapping and the refresh script. |
| `python-package`, `publish-*` | release, manual `run: release` | Builds the distribution; publishes only when `publish_to` names a target. |
| `release-package`, `sign-and-publish` | release, manual `run: release` | Builds, checksums, signs, and attests the platform packages. |

A manual run defaults to `run: ci`, so starting the workflow by hand cannot
accidentally publish anything.

## Writing tests

- Test behaviour, not internals. Assert what a caller observes.
- When you fix a bug, add a test that fails without the fix and say in the test
  what used to happen.
- Do not mock the boundary you are testing. Adapter tests stub the HTTP
  transport, not the adapter.
- Never point a test at a real system. Use fixture targets or a local stub.
