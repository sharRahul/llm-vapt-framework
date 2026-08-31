# Configuration

VulnoraIQ works out of the box for local use. This page covers the few things you
will actually configure, and where each one lives.

## The split

| Kind | Where | Committed? |
| --- | --- | --- |
| Non-secret defaults and framework data | YAML under `config/` | Yes |
| Runtime settings and limits | Environment variables | No |
| Secrets (tokens, API keys) | Environment or a secret store | **Never** |
| Targets you create in the console | The runtime target registry | No |

Precedence runs: built-in defaults → committed YAML → environment → runtime
changes made in the console.

## First-run choices

### Run mode

Nothing to configure — the launcher you use decides. Desktop Mode runs VulnoraIQ
on your machine; Lab Mode runs it in a container. See
[Desktop Mode](../guides/desktop-mode.md) and [Lab Mode](../guides/lab-mode.md).

### Authentication

Local use defaults to `local_admin`: no token, loopback binding, and you are the
single administrator. That is the right setting for a laptop.

Anything shared needs real authentication:

```bash
export VULNORAIQ_AUTH_MODE=token
export VULNORAIQ_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

`local_admin` refuses to start on a non-loopback bind, and is rejected outright
when `VULNORAIQ_ENV=production`.

### Where output goes

| Variable | Default | Holds |
| --- | --- | --- |
| `VULNORAIQ_WEB_OUTPUT_ROOT` | `reports/output/webui` (Desktop Mode: `scan-reports/reports`) | Reports and dashboards |
| `VULNORAIQ_JOB_STORE_PATH` | `<output root>/jobs.db` | Scan job history and finding states |
| `VULNORAIQ_EVIDENCE_DIR` | unset | Captured request/response evidence |

### Targets

`config/targets.yaml` ships **empty on purpose**: there is no default target, so
VulnoraIQ cannot assess anything until you say what you are authorised to assess.

Add targets in the console's Targets workspace, deploy an agent in Agent Lab
(which registers one for you), or edit the YAML directly. Copyable starting
points for common providers live in `config/targets/templates/`.

See the [targets guide](../guides/targets.md).

### Scope limits

Two controls decide what VulnoraIQ may contact:

- **Safety profiles** (`config/safety_profiles.yaml`) — per-target host
  allowlists, timeouts, size caps, and request budgets.
- **`VULNORAIQ_ALLOWED_TARGET_HOSTS`** — a deployment-wide allowlist that
  overrides everything. Nothing outside it is ever contacted.

With neither set, a target host must resolve entirely to loopback, private, or
link-local addresses.

### Local environment file

For convenience during development, copy the template and edit the copy:

```bash
cp config/environment.template .env
```

`.env` is git-ignored and must stay that way. The template is deliberately not
named `.env.*` so it cannot be confused for a real environment file.

## Full references

- [Configuration files](../reference/configuration.md) — every YAML file.
- [Environment variables](../reference/environment-variables.md) — every variable,
  with defaults and sensitivity.
- [Secrets](../security/secrets.md) — where credentials may live.
