# VulnoraIQ incident response plan

This plan covers VulnoraIQ `0.3.0` self-hosted Docker lab and internal-server deployments.

> **Scope:** local or internal-server deployment using Docker Compose or production-mode hosted server, token auth or trusted reverse-proxy identity, SQLite persistence, reports/evidence paths, structured audit logs, and documented target authorisation controls.

## Severity definitions

| Severity | Description | Initial response target | Escalation |
| --- | --- | --- | --- |
| Critical | Auth bypass, confirmed token misuse, artifact/report exposure, arbitrary file access, runtime compromise, corrupted production DB with no clean backup. | Immediate | Security lead + engineering lead + legal/comms if data exposure is possible. |
| High | Suspected auth abuse, trusted-proxy spoofing attempt, repeated CSRF/rate-limit abuse, exploitable dependency issue, unsafe target config in shared deployment, release-claim validation failure. | < 1 hour | Security + engineering. |
| Medium | Misconfiguration, failed backup, limited DoS, missing audit/metric signal, GenAI/OWASP/docs drift, target validation regression. | < 4 hours | Engineering owner. |
| Low | Documentation issue, demo-only issue, local browser-test environment issue, non-sensitive monitoring gap. | Next sprint | Repo maintainer. |

## Evidence sources

Use these first:

- Docker logs: `docker compose logs vulnoraiq-web`, `docker compose logs local-mock-agent`;
- audit logs under `/data/audit`;
- SQLite job store at `/data/jobs.db`;
- report outputs under `/data/reports`;
- evidence outputs under `/data/evidence`;
- `/healthz`, `/readyz`, and `/metrics`;
- CI logs and validation artifacts;
- reverse-proxy logs where deployed.

## Immediate containment

1. Stop scans from the WebUI or CLI.
2. If needed, stop the service:

```bash
docker compose down
```

3. Preserve `/data/jobs.db`, `/data/reports`, `/data/evidence`, and `/data/audit` before deleting or rotating anything.
4. Revoke or rotate `VULNORAIQ_ADMIN_TOKEN` and target tokens.
5. Disable unsafe runtime targets or remove affected runtime target files.
6. Run production validation before restart.

## Investigation checklist

- Was the target owned/authorised?
- Was `--authorised` or WebUI authorisation used correctly?
- Which profile and modules ran?
- Which target config file was active?
- Did target validation pass before scanning?
- Were any report/evidence artifacts exposed?
- Were secrets or sensitive responses persisted?
- Did rate limits, request limits, CSRF, and auth behave as expected?
- Did CI/readiness validation fail before release or deployment?

## Recovery

1. Apply code/config fix.
2. Restore from a known-good SQLite backup if needed.
3. Rebuild/restart Docker services.
4. Run:

```bash
ruff check .
mypy .
pytest -q
python scripts/validate_runtime_production_config.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
python scripts/validate_genai_readiness.py
python scripts/validate_owasp_atlas_mappings.py
```

5. Run a controlled Docker smoke scan before resuming normal use.

## Post-incident review

Document:

- timeline;
- affected deployment and target scope;
- root cause;
- evidence/artifacts involved;
- whether data exposure occurred;
- corrective actions;
- docs/tests/CI updates required;
- whether release claims need to be changed.

## Assurance boundary

An incident in VulnoraIQ or its lab does not automatically imply target compromise. Conversely, a clean VulnoraIQ run does not prove a target is secure. Findings and incident evidence require human review.
