# Development setup

## Requirements

| Need | Version |
| --- | --- |
| Python | 3.10 or newer |
| Node.js | 20 or newer (console only) |
| Docker | Docker Engine or Docker Desktop with Compose v2 |

## Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

The `dev` extra brings pytest, ruff, mypy, and pip-audit. Runtime dependencies
are declared in `pyproject.toml` — there is no separate requirements file.

Run the server directly:

```bash
VULNORAIQ_AUTH_MODE=local_admin vulnoraiq-web --host 127.0.0.1 --port 8787
```

Or through a launcher:

```bash
python scripts/desktop_launch.py     # Desktop Mode
python scripts/bootstrap_launch.py   # Lab Mode via Docker Compose
```

## Frontend

```bash
cd webui/console
npm ci
npm run dev        # Vite dev server
npm run typecheck  # tsc --noEmit
npm run build      # typecheck, then build into webui/static/console/
```

The server serves the built output from `webui/static/console/`, which is
committed so a checkout runs without a Node toolchain. Rebuild and commit it
whenever you change the console — see [frontend build](frontend-build.md).

## Layout

```text
core/            assessment domain: scanner, policy, evaluators, findings, runtime targets
integrations/    outbound adapters: target HTTP clients, CVE lookup, contract validation
modules/         assessment modules and the module registry
payloads/        payload libraries
webui/           HTTP API, security controls, Agent Lab, assistant
  console/       React console source
  static/        built console and Agent Lab assets
reports/         report generators (Markdown, JSON, SARIF)
dashboards/      dashboard generators
scripts/         launchers, validators, packaging, maintenance
config/          YAML configuration
tests/           test suite
docs/            this documentation
```

Dependency direction runs one way: `webui` may use `core` and `integrations`;
`core` may use `integrations`; neither `core` nor `integrations` imports `webui`.

## Checks

Run these before opening a change:

```bash
ruff check .
mypy .
pytest -q
```

`mypy` is a real gate — the configuration has no blanket `ignore_errors`, so a
type error fails the build. Do not silence one with a file-level suppression;
fix the type or narrow it explicitly.

Full validation is listed in [testing](testing.md).

## Conventions

- Match the style of the file you are editing.
- Comments explain *why*, not *what*. Most code does not need one.
- Every external command is an argument array through the shared boundary in
  `webui/docker_cli.py`. Never build a shell string.
- New configuration goes in `config/` as non-secret YAML, or as an environment
  variable documented in
  [environment variables](../reference/environment-variables.md).
- No file starting with `.env` may ever be committed.

## Related

- [Testing](testing.md)
- [Docker](docker.md)
- [Module authoring](module-authoring.md)
- [Contributing](../../CONTRIBUTING.md)
