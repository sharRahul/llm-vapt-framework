# VulnoraIQ run modes: desktop default and Docker lab advanced

This document defines the current VulnoraIQ launch and runtime modes.

## Product decision

VulnoraIQ supports two explicit launch modes:

| Mode | Intended users | Where VulnoraIQ runs | Where imported agents run | Report location |
| --- | --- | --- | --- | --- |
| Desktop Mode | Laptop and workstation users | Native host process | Docker containers | `./scan-reports/` |
| Docker Lab Mode | Servers, VMs, CI, dev labs | Docker Compose container | Docker containers | Docker volume or mapped folders |

Desktop Mode is the default product direction for normal users. Docker Lab Mode remains supported for reproducible lab, CI, server, and VM workflows.

## Desktop Mode target flow

```text
User clicks native launcher
  -> VulnoraIQ starts on the host machine
  -> Browser opens http://127.0.0.1:8787
  -> User opens Agent Lab
  -> User imports/selects a real AI-agent project
       - preferred: Local folder upload from the browser
       - alternatives: ZIP upload, Git import, or mapped ./projects/<agent-name>/ refresh
  -> VulnoraIQ stores WebUI imports under ./agent-lab/projects/
  -> User configures API key, local LLM, remote LLM, CPU/GPU runtime
  -> VulnoraIQ uses Docker only to build/run the imported agent
  -> VulnoraIQ auto-creates a target for the running agent
  -> User runs scans from the WebUI
  -> Jobs, reports, evidence, audit, and exports are stored under ./scan-reports/
  -> Dashboard loads results from the local job store and report/evidence folders
```

Desktop Mode uses Docker as a sandbox for imported targets, not as the runtime for VulnoraIQ itself.

## Docker Lab Mode target flow

```text
User starts Docker Lab launcher or manual Docker Compose
  -> Docker Compose builds/starts vulnoraiq-web
  -> Browser opens http://127.0.0.1:8787
  -> User opens Agent Lab
  -> User imports/selects a real AI-agent project
       - Local folder upload from the browser
       - ZIP upload
       - Git import
       - mapped ./projects/<agent-name>/ through /app/projects
  -> VulnoraIQ stores WebUI imports under /data/agent_lab/projects
  -> User configures API key, local LLM, remote LLM, CPU/GPU runtime
  -> vulnoraiq-web uses Docker to build/run the imported agent
  -> VulnoraIQ auto-creates a target for the running agent
  -> User runs scans from the WebUI
  -> Jobs, reports, evidence, and audit are stored under /data
```

Docker Lab Mode keeps the reproducible containerised lab model.

## Folder contract

Desktop Mode creates and uses these folders in the checkout/release root:

```text
scan-reports/
  jobs.db
  reports/
  evidence/
  audit/
  exports/

agent-lab/
  projects/          # managed WebUI imports: folder upload, ZIP upload, Git import
  deployments.yaml

projects/            # optional mapped AI-agent folders for refresh-only discovery
  <agent-name>/
```

Normal desktop users should prefer **Local folder upload** from the WebUI. That flow lets the browser select a local source folder and upload the selected files into `agent-lab/projects/`. The backend never receives permission to browse arbitrary local paths.

The `projects/` folder is still useful when an operator wants persistent host-visible projects that appear after Agent Lab refresh. Mapped projects are treated as read-only by Agent Lab.

Docker Lab Mode uses `/data` by default and maps operator-visible folders when configured:

```text
./agent-lab:/data/agent_lab
./projects:/app/projects:ro
```

## Runtime responsibilities

| Responsibility | Desktop Mode | Docker Lab Mode |
| --- | --- | --- |
| Start WebUI | Host process | Compose service |
| Managed Agent Lab imports | `./agent-lab/projects/` | `/data/agent_lab/projects/` |
| Optional mapped projects | `./projects/` | `/app/projects` from `./projects:/app/projects:ro` |
| Build imported agent | Host Docker CLI/API | Docker CLI/API from `vulnoraiq-web` |
| Run imported agent | Docker container | Docker container |
| Scan target | Host VulnoraIQ scanner | Containerised VulnoraIQ scanner |
| Agent target URL | Published localhost port | Container DNS on Compose network |
| Reports | Host folder | `/data` volume or mapped folder |
| Best default | End users | Advanced/dev/server/CI |

## Implementation status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: repo/source mode foundation | Implemented | Native desktop launchers, Desktop Mode folders, WebUI local folder upload, explicit Docker Lab launchers, desktop Agent Lab Docker network, mode-aware targets, tests, and docs are in place. |
| Phase 2: packaged desktop application | Future maturity | Build packages that bundle Python/frozen runtime so Docker Desktop is the only external prerequisite for normal users. |
| Phase 3: UX polish | In progress/future maturity | Run-mode indicators, reports-folder openers/exporters, backup/export before reset, and mode-selector help remain polish work. |

## Security notes

- Imported agents remain untrusted and must run in Docker containers by default.
- Local folder upload sends only files explicitly selected by the operator; it does not give the backend arbitrary filesystem access.
- API keys configured for imported agents should be injected into the agent runtime only and redacted from stored metadata.
- Desktop Mode should keep the WebUI on `127.0.0.1`.
- Docker Lab Mode must remain loopback-only unless deployed behind production auth, TLS, reverse proxy controls, audit retention, and backups.
