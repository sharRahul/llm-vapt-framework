# CLI guide

The `vulnoraiq` CLI is the same scanner/reporting path used by the WebUI backend. All scan commands require `--target <name>`; no default target is provided. Run it inside Docker Compose or from a local package install.

## Docker-first usage

```bash
docker compose exec vulnoraiq-web vulnoraiq targets list
docker compose exec vulnoraiq-web vulnoraiq targets validate --target <target_name>
docker compose exec vulnoraiq-web vulnoraiq scan --target <target_name> --profile ai_agent_foundation --authorised
docker compose exec vulnoraiq-web vulnoraiq reports list
docker compose exec vulnoraiq-web vulnoraiq jobs list
docker compose exec vulnoraiq-web vulnoraiq jobs show --job-id <job-id>
```

Docker reports are written under `/data/reports`; evidence under `/data/evidence`; audit logs under `/data/audit`; the SQLite job store is `/data/jobs.db`.

## Host-native development usage

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
vulnoraiq scan --target <target_name> --profile baseline --authorised
```

The `--target` argument is required; there is no default target. You must configure a target in your `config/targets.yaml` before running a scan.

## Command groups

| Command | Purpose |
| --- | --- |
| `vulnoraiq targets list` | Show configured targets from the active target config file. |
| `vulnoraiq targets validate --target <name>` | Run adapter connectivity and response-extraction checks. |
| `vulnoraiq scan ...` | Run an authorised scan and write Markdown, JSON, SARIF, dashboard, and HTML outputs. |
| `vulnoraiq reports list` | List generated report artifacts in the active output root. |
| `vulnoraiq jobs list` | List persisted WebUI/CLI jobs from the active job store. |
| `vulnoraiq jobs show --job-id <id>` | Print one persisted job record as JSON. |

## Explicit scan outputs

```bash
vulnoraiq scan \
  --target <target_name> \
  --profile ai_agent_foundation \
  --authorised \
  --output reports/output/scan-report.md \
  --json-output reports/output/scan-report.json \
  --sarif-output reports/output/scan-report.sarif \
  --dashboard-output reports/output/dashboard.md \
  --html-dashboard-output reports/output/dashboard.html
```

## Configuration environment variables

| Variable | Purpose |
| --- | --- |
| `VULNORAIQ_CONFIG_DIR` | Directory containing config files. Defaults to `config`. |
| `VULNORAIQ_TARGET_CONFIG` | Target config filename. Docker uses `targets.docker.yaml`; host-native defaults to `targets.yaml`. |
| `VULNORAIQ_WEB_OUTPUT_ROOT` | Report/output root. |
| `VULNORAIQ_JOB_STORE_PATH` | SQLite job-store path. |
| `VULNORAIQ_EVIDENCE_DIR` | Evidence output path. |
| `VULNORAIQ_AUDIT_DIR` | Audit log path. |

## Safety boundary

Use `--authorised` only when you own the target or have explicit permission to assess it. CLI output is still framework evidence that requires human review.
