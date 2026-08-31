# VulnoraIQ operations runbook

This runbook covers VulnoraIQ `0.3.0` as a self-hosted Docker-first AI security testing lab and internal-server application.

## 1. Normal startup

### Docker lab

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open <http://localhost:8787>.

### Host-native local launcher

```bash
python launch-vulnoraiq-webui.py
```

Launcher mode is loopback/local only.

### Production-mode hosted server

```bash
export VULNORAIQ_ENV=production
export VULNORAIQ_AUTH_ENABLED=true
export VULNORAIQ_ADMIN_TOKEN="your-strong-token-min-20-chars"
python scripts/validate_runtime_production_config.py
vulnoraiq-web --host 127.0.0.1 --port 8787
```

## 2. Health checks

| Check | Command or URL |
| --- | --- |
| Docker services | `docker compose ps` |
| Web logs | `docker compose logs vulnoraiq-web` |
| Mock-agent logs | `docker compose logs local-mock-agent` |
| Health | `/healthz` |
| Readiness | `/readyz` |
| Metrics | `/metrics` with auth where enabled |
| Target validation | `vulnoraiq targets validate --target local_mock_agent` |

## 3. Common operations

### Validate targets

```bash
docker compose exec vulnoraiq-web vulnoraiq targets validate --target local_mock_agent
```

### Run a scan

```bash
docker compose exec vulnoraiq-web vulnoraiq scan \
  --target local_mock_agent \
  --profile ai_agent_foundation \
  --authorised
```

### List reports and jobs

```bash
docker compose exec vulnoraiq-web vulnoraiq reports list
docker compose exec vulnoraiq-web vulnoraiq jobs list
docker compose exec vulnoraiq-web vulnoraiq jobs show --job-id <job-id>
```

## 4. Data locations

| Location | Contents |
| --- | --- |
| `/data/jobs.db` | SQLite job store. |
| `/data/reports` | Markdown, JSON, SARIF, dashboard, and HTML outputs. |
| `/data/evidence` | Evidence files. |
| `/data/audit` | Audit logs. |

## 5. Backup and restore

Use the SQLite backup script for the job store and preserve reports/evidence as normal files.

```bash
python scripts/backup_sqlite_store.py --database /data/jobs.db --output-dir /data/backups
python scripts/restore_sqlite_store.py --backup <backup-file> --database /data/jobs.db
```

Before restore, stop the service or ensure no scans are running.

## 6. Shutdown

```bash
docker compose down
```

Remove volumes only when intentionally deleting all local jobs/reports/evidence/audit data:

```bash
docker compose down -v
```

## 7. Troubleshooting

| Symptom | Action |
| --- | --- |
| WebUI unreachable | Check `docker compose ps`, port `8787`, and `docker compose logs vulnoraiq-web`. |
| Target validation fails | Check `local-mock-agent` logs and ensure the active target config is `targets.docker.yaml` inside Docker. |
| Scans fail authorisation | Confirm `--authorised` in CLI or the WebUI checklist for non-demo targets. |
| Reports missing | Confirm `VULNORAIQ_WEB_OUTPUT_ROOT` and `/data/reports`. |
| Jobs missing | Confirm `VULNORAIQ_JOB_STORE_PATH` and whether the Docker volume was reset. |
| Browser tests fail locally | Install Playwright Chromium and ensure the environment can download browser binaries. |
| Production mode refuses startup | Run `python scripts/validate_runtime_production_config.py` and fix every fail-closed item. |

## 8. Incident handling trigger points

Escalate to the incident response plan for:

- suspected auth bypass or token compromise;
- report/evidence exposure;
- unsafe target configuration;
- repeated CSRF/rate-limit abuse;
- dependency vulnerability impacting the deployed version;
- GenAI/OWASP readiness validation drift before release.

## 9. Current operational limitations

VulnoraIQ is designed for a single self-hosted instance. Multi-instance shared state, enterprise OIDC, SIEM rule packs, signed installers, image signing/scanning, and independent assurance validation remain future maturity items.
