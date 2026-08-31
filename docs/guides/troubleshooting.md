# Troubleshooting

Symptoms and the checks that resolve them. Everything here reflects behaviour the
current code actually has.

## Startup

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Docker was not found` | The Docker CLI is not on `PATH`. | Install Docker Desktop / Docker Engine, or set `VULNORAIQ_DOCKER_BINARY`. |
| `Docker Desktop / Docker Engine is not ready` | The CLI exists but the engine is not running. | Start Docker and wait until it reports ready. |
| `auth_mode_validation_failed` at startup | `VULNORAIQ_AUTH_MODE=local_admin` with a non-loopback `--host`. | Bind `127.0.0.1`, or switch to `token` mode with an admin token. |
| `production_mode_validation_failed` | `VULNORAIQ_ENV=production` without a valid admin token. | Set `VULNORAIQ_ADMIN_TOKEN` to at least 20 characters, and `VULNORAIQ_AUTH_MODE=token`. |
| `production_check_failed: <name>` | A production hardening check failed. | The log line names the check and the detail. Fix it, or start with `--skip-production-checks` only in a non-production context. |
| Port already in use | Another VulnoraIQ (or something else) holds 8787. | Stop it, or pass `--port`. |

Check Docker independently:

```bash
python scripts/check_docker_runtime.py --json
```

## Authentication

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every request returns `401` | Token mode is on and no token was sent. | Send the header named by `GET /api/session`, or use `local_admin` for local use. |
| `403 forbidden` on a target/agent action | The role lacks `manage_runtime`. | Use an admin token. Only admin manages runtime. |
| `403 invalid or missing CSRF token` | The `X-CSRF-Token` header is absent or stale. | Fetch a fresh token from `/api/csrf-token`; tokens expire after `VULNORAIQ_CSRF_TOKEN_TTL`. |
| `429 rate limit exceeded` | Client exceeded `VULNORAIQ_RATE_LIMIT_MAX` in the window. | Slow down, or raise the limit for a trusted local deployment. |

## Targets

| Symptom | Cause | Fix |
| --- | --- | --- |
| `target host ... resolves outside loopback/private networks` | The target is on the public internet and nothing opted it in. | Only if you are authorised: set `allow_external: true` on the target, or add it to a safety-profile allowlist. |
| `target host ... could not be resolved` | DNS returned nothing for the host. | Check the name. In Lab Mode, a container name only resolves once the container is running on the same Docker network. |
| `host ... is blocked by the configured target allowlist` | An allowlist is in force and excludes this host. | Add it to `VULNORAIQ_ALLOWED_TARGET_HOSTS`, the safety profile's `allowed_hosts`, or the target's `allowed_host_pattern`. |
| `target URL must not embed credentials` | The base URL contains `user:pass@`. | Move the credential to `auth_token_env`. |
| `Target '<name>' is a placeholder` | The target still has a template endpoint. | Replace it with the real authorised endpoint. |
| `contains 'demo'/'mock'/'fake'/'fixture' and is not allowed` | A synthetic target in normal runtime. | Rename it, or set `VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS=true` for a deliberate fixture run. |
| `Targets require explicit authorisation` | The scan was started without the authorisation flag. | Pass `--authorised`, or confirm the checklist in the console. |

Validate a target's connectivity before scanning — the console's **Test
connectivity** button, or:

```bash
vulnoraiq targets validate --target <name>
```

## Agent Lab

| Symptom | Cause | Fix |
| --- | --- | --- |
| `did not serve HTTP at ... within 30s` | The container started but the app never listened. The container is removed and the last logs are included in the error. | Read the returned logs. Usually a wrong start command, a missing dependency, or the app binding `127.0.0.1` inside the container instead of `0.0.0.0`. |
| `git host '<host>' is not allowed` | The host is outside the allowlist. | Add it to `VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS`. |
| `imported repository exceeds Agent Lab size limits` | Import is over the byte or file cap. | Raise `VULNORAIQ_AGENT_LAB_MAX_IMPORT_BYTES` / `..._MAX_IMPORT_FILES`, or import a smaller subset. |
| `unsafe archive path` | The ZIP contains an absolute path or `..`. | Repack the archive from the project root. |
| `mounted project has no Dockerfile` | Mapped projects are read-only, so no Dockerfile can be generated into them. | Add a Dockerfile to the project, or import it into managed Agent Lab storage instead. |
| `project '<id>' already exists` | The id is taken. | Delete the existing project, or import under a different id. |
| Scan hits the wrong endpoint | Endpoint detection picked a different route. | The analyse response shows `selected_endpoint`. Override `endpoint_path`, `method`, `param_key`, and `response_extraction_path` in the deploy request's `target` block. |
| Agent deployed but no target appears | Registration is health-gated. | Check the deploy response: a failed health gate returns an error rather than a target. |

## Scans

| Symptom | Cause | Fix |
| --- | --- | --- |
| `429 scan queue at capacity` | Running plus queued scans reached `VULNORAIQ_SCAN_QUEUE_LIMIT`. | Wait, or raise the limit. |
| Scan fails with `scan did not start: the runner stayed at capacity` | A queued scan waited longer than `VULNORAIQ_SCAN_SLOT_WAIT_SECONDS`. | Raise `VULNORAIQ_MAX_CONCURRENT_SCANS`, or the wait. |
| Scan fails with `internal scan error` | An exception during the run; details are in the application log, not the response. | Check the server log for `scan_job_failed`. |
| Findings show `TARGET_ERROR: ...` | The target itself returned an error or was unreachable. | Validate connectivity; check the target's own logs. |
| Live progress stops updating | The event stream hit `VULNORAIQ_SSE_MAX_STREAM_SECONDS`. | Reload the scan view; the job itself is unaffected. |

## Reports and persistence

| Symptom | Cause | Fix |
| --- | --- | --- |
| No reports appear | Output root is elsewhere. | Check `VULNORAIQ_WEB_OUTPUT_ROOT`; in Lab Mode look under `/data/reports`. |
| Jobs disappeared | The job database moved, or the Docker volume was reset. | Check `VULNORAIQ_JOB_STORE_PATH`. `docker compose down -v` deletes the volume. |
| Artefact download returns 404 | The artefact is not one the job produced. | Only names in the job's own output map are served. |

Back up and restore the job store:

```bash
python scripts/backup_sqlite_store.py
python scripts/restore_sqlite_store.py
```

## Assistant

| Symptom | Cause | Fix |
| --- | --- | --- |
| Explanations look templated | The local model is not installed or failed to load. | `GET /api/assistant/config` reports the model status. See [model providers](model-providers.md). |
| Model load crashes on Windows CPU | A newer `llama-cpp-python` wheel using unsupported instructions. | Pin `0.3.19` from the CPU wheel index. |

## Lab Mode

| Symptom | Check |
| --- | --- |
| Console does not open | `docker compose ps`, then `docker compose logs vulnoraiq-web` |
| Not reachable from another machine | Expected. The console publishes on `127.0.0.1` only. |
| Target unreachable from the container | The target must be reachable *from inside* the container, not from your host. |

## Getting more detail

```bash
export VULNORAIQ_LOG_LEVEL=DEBUG
```

Audit records are emitted separately from application logs and carry the request
id, actor, action, and outcome. Pass `X-Request-ID` on a request to correlate it.

## Related

- [Operations](operations.md)
- [Lab Mode](lab-mode.md)
- [Environment variables](../reference/environment-variables.md)
