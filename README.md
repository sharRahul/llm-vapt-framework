# VulnoraIQ

Self-hosted AI security assessment for LLM applications, RAG systems, AI agents,
and the orchestration layers around them.

You point VulnoraIQ at a system you are authorised to assess — or import an agent
and let it build one for you — and it runs bounded, authorised assessments,
captures the evidence, and produces reports a human can review.

Findings are **evidence for human review**. VulnoraIQ does not claim certified
VAPT-grade assurance. See [assessment assurance](docs/security/assurance.md).

## What VulnoraIQ is

- A **browser console** for configuring targets, running assessments, and
  triaging findings.
- A **CLI** over the same engine, for scripted and CI use.
- **Agent Lab**: import an AI-agent project, build and run it in a sandboxed
  container, and get a working scan target without hand-writing a config.
- **OWASP LLM Top 10 (2025)** and **MITRE ATLAS** mapped assessment modules.
- Reports in Markdown, JSON, SARIF, and HTML dashboards, with redacted evidence
  and an audit trail.

It is **not** a general-purpose chatbot, a shell for a language model, or an
unattended scanner. Every assessment requires explicit authorisation, and every
target is scope-checked before a request is sent.

## Key capabilities

| Capability | Status |
| --- | --- |
| Desktop Mode (VulnoraIQ on your machine) | Supported |
| Lab Mode (VulnoraIQ in Docker Compose) | Supported |
| Target types: HTTP JSON, chat-completions, Ollama generate, RAG query, webhook JSON, agent tool-loop | Supported |
| Agent Lab import → build → run → auto-target → scan | Supported, **experimental** — it builds and runs code you supply |
| OWASP LLM Top 10 (2025) and MITRE ATLAS mapping | Supported |
| Markdown / JSON / SARIF / HTML reporting | Supported |
| Finding triage with history and audit trail | Supported |
| SQLite (WAL) persistence for jobs, findings, and triage history | Supported |
| In-app assistant ("Nora") for finding explanations | Optional; falls back to templated guidance when not installed |
| GPU for imported agents and the assistant | Optional; VulnoraIQ passes GPU runtime flags, it does not install drivers |
| Token auth, trusted-proxy identity, production hardening gate | Supported |
| Direct OIDC / JWT identity | [Planned](docs/plans/oidc-jwt-auth.md), not implemented |
| Signed native desktop installers | Not currently supported |

## Two run modes

| Mode | Best for | Where VulnoraIQ runs | Where agents run | Output |
| --- | --- | --- | --- | --- |
| **Desktop Mode** | Laptops and workstations | Host process | Docker containers | `./scan-reports/` |
| **Lab Mode** | Servers, VMs, CI, reproducible labs | Docker Compose container | Docker containers | `/data` volume or mapped folders |

Both default to a **local single-user admin session** bound to `127.0.0.1`.
Anything shared requires token auth and explicit hardening.

## How it works

```text
Import or configure a target
  → validate scope and connectivity
    → confirm authorisation
      → run the selected assessment profile
        → capture redacted evidence
          → map findings to OWASP LLM / MITRE ATLAS
            → report, triage, and review
```

Agent Lab adds a step in front: import a project, detect its HTTP contract, build
and run it in a container, health-gate it, and register the result as a target.

## Quick start

### Desktop Mode

| Platform | Launcher |
| --- | --- |
| Windows | `launch-vulnoraiq-webui.bat` |
| macOS | `launch-vulnoraiq-webui.command` |
| Linux | `launch-vulnoraiq-webui.sh` |

The launcher starts VulnoraIQ on the host, checks Docker is available for agent
sandboxes, creates the local output folders, and opens
<http://127.0.0.1:8787>. No `vulnoraiq-web` container is created — Docker is
used only for agents.

### Lab Mode

| Platform | Launcher |
| --- | --- |
| Windows | `launch-vulnoraiq-docker-lab.bat` |
| macOS | `launch-vulnoraiq-docker-lab.command` |
| Linux | `launch-vulnoraiq-docker-lab.sh` |

Or directly:

```bash
docker compose build
docker compose up -d
```

Then open <http://127.0.0.1:8787>.

Full walkthrough: [quick start](docs/getting-started/quick-start.md).

## Installation

| Path | Requirements |
| --- | --- |
| Desktop Mode | Python 3.10+, Docker Engine or Docker Desktop with Compose v2, a modern browser |
| Lab Mode | Docker Engine or Docker Desktop with Compose v2, a modern browser |
| Development | The above plus Node.js 20+ and npm |

From a source checkout:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Details: [installation](docs/getting-started/installation.md).

## AI and model providers

VulnoraIQ never calls a hosted model to perform an assessment. Models appear in
two independent places:

- **Imported agents** get a provider you choose at deploy time — Ollama, LM
  Studio, OpenRouter, any OpenAI-compatible endpoint, or plain environment
  variables. Keys are injected into that agent's container and redacted from
  stored records.
- **The optional assistant ("Nora")** runs a small local GGUF model in-process to
  explain findings. It is advisory, grounded in the finding's own evidence, and
  cannot reach a target or execute anything.

Details: [model providers](docs/guides/model-providers.md).

## Security and isolation

- Every scan requires explicit authorisation; without it nothing is sent.
- A target host must resolve to loopback, private, or link-local addresses unless
  it is explicitly allowlisted or opted into external access.
- Placeholder and synthetic fixture targets are refused in normal runtime.
- Agent containers run with `--cap-drop ALL`, `--security-opt no-new-privileges`,
  loopback-only port publishing, and optional CPU/memory limits.
- External commands run as argument arrays through a single audited boundary —
  never a shell string. A model has no path to command execution.
- Console access is loopback single-admin by default; token mode is required for
  anything shared, and production mode refuses to start without a real token.
- There is no built-in or default credential anywhere in VulnoraIQ.

Lab Mode mounts the Docker socket so Agent Lab can build and run containers. That
is equivalent to root on the host and is the central trust decision in the
design — read [sandboxing](docs/security/sandboxing.md) before exposing
VulnoraIQ beyond your own machine.

## Documentation

[`docs/README.md`](docs/README.md) is the documentation map. Common entry points:

| Need | Document |
| --- | --- |
| First assessment | [Quick start](docs/getting-started/quick-start.md) |
| Configure what you assess | [Targets](docs/guides/targets.md) |
| Import and run an agent | [Agents](docs/guides/agents.md) |
| Understand results | [Findings and evidence](docs/guides/findings.md) |
| Something is wrong | [Troubleshooting](docs/guides/troubleshooting.md) |
| Trust boundaries | [Security model](docs/security/security-model.md) |
| Every setting | [Configuration](docs/reference/configuration.md) · [Environment variables](docs/reference/environment-variables.md) |
| API and CLI | [HTTP API](docs/reference/api.md) · [CLI](docs/reference/cli.md) |

## Development

```bash
pip install -e ".[dev]"
ruff check .
mypy .
pytest -q
```

Console:

```bash
cd webui/console
npm ci
npm run build        # typechecks, then builds into webui/static/console/
```

See [development setup](docs/development/development-setup.md).

## Testing

```bash
pytest -q                                   # unit and integration suite
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_aitg_full_coverage.py
python scripts/validate_target_configs.py
npm run test:webui:hosted                   # browser flow (needs Playwright)
```

See [testing](docs/development/testing.md).

## Responsible use

VulnoraIQ sends adversarial input to AI systems and builds and runs code you
import. **Use it only against systems you own or are explicitly authorised in
writing to assess.** See [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) and
[responsible use](docs/security/responsible-use.md).

Report security issues through [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
