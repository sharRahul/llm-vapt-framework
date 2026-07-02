# Implementation status

This document separates implemented capability from future assurance and maturity work.

> **Current maturity:** VulnoraIQ `0.3.0` is a self-hosted AI security testing application with two supported run modes: Desktop Mode for normal laptop/workstation use and Docker Lab Mode for advanced server, VM, CI, and dev-lab use. It is complete for **self-hosted laptop/server use** within the current authorised local/internal scope. It supports authorised local/internal testing of LLM, RAG, tool-using, agentic, and GenAI data-security scenarios through a Python scanner, target adapters, hosted React WebUI, assistant backend/model controls, target templates, CLI, SQLite job persistence, reports, evidence, on-demand release packages, supply-chain workflow evidence, loopback-only local publishing, and CI validation.

> **Assurance limitation:** OWASP, GenAI, Agentic, AITG, and MITRE mappings are framework evidence and planning/validation controls. They are not independently validated VAPT-grade assurance. See [`ASSESSMENT_ASSURANCE.md`](ASSESSMENT_ASSURANCE.md) for the full assurance boundary.

## Mainline status as of 2026-06-28

| Area | Status | Evidence |
| --- | --- | --- |
| Version/package | Complete for `0.3.0` beta | `pyproject.toml`, package entry points, metadata validation. |
| Desktop Mode | Complete for current source/release-package use | Native launchers and `scripts/desktop_launch.py` start VulnoraIQ on the host, create `scan-reports/`, `agent-lab/`, and optional `projects/`, and keep Docker for sandboxed Agent Lab runtimes. |
| Docker Lab Mode | Complete for current advanced local/CI/server-lab scope | `docker-compose.yml`, loopback-only `127.0.0.1:8787:8787` WebUI publishing, Dockerfile, Docker smoke tests. |
| Real authorised target testing | Complete for current local/internal scope | Target adapters, target validation, scanner wiring, runtime target APIs, and test-profile fixture targets. |
| React WebUI | Complete as supported WebUI | `webui/console/` source and `webui/static/console/` built assets. Legacy static console has been removed. |
| WebUI target workspace | Complete for current backend APIs | Search/filtering, readiness metrics, health/status pills, safety checklist, in-place authoring of direct LLM/RAG/agent HTTP endpoints (type, base URL, endpoint path, model, response path, request body), target save/delete, validation, scan launch, recent jobs, SSE progress, finding actions/history. Agent Lab container-backed targets keep their base URL/endpoint locked to the deployed container. |
| WebUI assistant | Complete for current self-hosted path | Assistant backend API, CSRF-protected chat requests, model controls, and React controls. |
| Experimental Agent Lab | Implemented for local lab use | Real project import via folder/ZIP/Git/mapped folders, provider settings, CPU/GPU Docker runtime selection, build/run/remove flow, and auto-created runtime targets. |
| CLI | Complete for current scope | `targets list`, `targets validate`, `scan`, `reports list`, `jobs list`, and `jobs show`. |
| Auth/security hardening | Complete for self-hosted internal scope | Token auth, trusted proxy mode, local single-user/admin mode, CSRF, rate limiting, request limits, security headers, audit logs, metrics, artifact path protection. |
| Persistence | Complete for current scope | SQLite job store with WAL, schema versioning, foreign keys, busy timeout. |
| OWASP LLM | Complete for current safe local/internal scope | OWASP docs, oracles, fixtures, profile/module coverage, mapping validation. |
| OWASP AI Testing Guide | Complete for safe synthetic coverage | AITG manifest, validator, `owasp-aitg-full` profile, and integration docs. |
| GenAI Security | Complete for current controlled scenario-harness scope | `DSGAI01–DSGAI21`, scenario cases, deterministic evaluators, validator, tests, docs. |
| Agentic Applications | Complete for repo-level self-hosted readiness gates | Mapping validation, CI gates, current status docs, and assurance boundary. |
| MITRE ATLAS | Complete for planning/mapping governance scope | Matrix docs, crosswalk, mapping validator, third-party notices. |
| Release packaging | Complete for self-hosted package scope | Manual release workflow, double-click launchers, bootstrap `.venv`, checksums, GitHub artifact attestations, optional GPG signatures. |
| Supply-chain workflow | Complete for current container release scope | Trivy filesystem/image scans, SARIF artifacts, SPDX/CycloneDX SBOMs, optional strict gates, GHCR publish, Cosign keyless signing, and verification evidence. |
| CI | Consolidated normal gate set | `.github/workflows/ci.yml` runs the Python matrix, Ruff, mypy, pytest, dependency checks, validators, hosted WebUI flow, functional acceptance, and artifacts. The old duplicate `python-ci.yml` workflow was removed. |
| Documentation | Cleaned active docs tree | Completed/superseded planning docs are staged in `docs/ready-to-remove/` for maintainer review while lightweight active stubs keep validator-owned paths stable. |

## Current complete capability

| Capability | Current implementation |
| --- | --- |
| Desktop launch | Host-native launchers start the WebUI on loopback and create `scan-reports/`, `agent-lab/`, and optional `projects/`. |
| Docker Lab launch | Compose starts a full `vulnoraiq-web` service for advanced lab, CI, VM, and server-style testing. |
| Real target testing | Users configure their own authorised targets. No default or mock targets are provided in normal runtime. |
| Docker test-lab profile | Deterministic test-agent is available behind the `test` Docker Compose profile for CI and integration testing. |
| Loopback WebUI publishing | Local modes publish the WebUI on loopback unless a production deployment is explicitly configured behind the required controls. |
| Configured target adapters | HTTP JSON, chat-completions, Ollama-generate, webhook JSON, RAG query, and agent tool-loop shapes. |
| Authorisation gate | CLI `--authorised` and WebUI checklist for all scans. |
| Scanner/reporting | Markdown, JSON, SARIF, Markdown dashboard, HTML dashboard, branded export and evidence output. |
| Policy and scoring | Findings, scores, policy status, exceptions, and approval evidence validation. |
| WebUI server | Hardened Python hosted server with security headers, CSRF, rate limiting, structured errors, metrics, audit logs, SSE events, persisted finding APIs, and assistant chat API wrapper. |
| WebUI console | React TypeScript SecOps console with target management, dashboards, findings/intelligence panels, live assistant chat, and typed UI data models. |
| Target template library | Common LLM APIs, RAG endpoints, local model servers, agent frameworks, and provider gateway templates with dry-run defaults and validator coverage. |
| Persistence | SQLite default with operational backup/restore tooling. |
| Release packages | Windows `.zip`, Linux `.tar.gz`, and macOS `.dmg` packages with double-click bootstrap launchers, checksums, artifact attestations, and optional GPG signatures. |
| Supply-chain evidence | Workflow artifacts include Trivy tables/SARIF files, filesystem SPDX SBOM, image CycloneDX SBOM, and Cosign verification when image publishing is enabled. |
| Release validation | Package metadata, OWASP/ATLAS mapping, GenAI readiness, production readiness, runtime config, and functional acceptance scripts. |

## Known incomplete or future maturity items

| Area | Status |
| --- | --- |
| Bundled desktop runtime | Source/release-package Desktop Mode still expects Python 3.10+; a bundled/frozen runtime remains future work. |
| Enterprise identity | Trusted proxy identity exists; direct OIDC/JWT remains future work and is planned in `docs/future-plans/OIDC_JWT_AUTH_PLAN.md`. |
| Native installer certificates | On-demand release packages are signed/attested; Authenticode Windows installers, notarised macOS app/pkg installers, and distro-native Linux packages remain future work. |
| SIEM integration | Audit logs exist; packaged SIEM schemas/rules remain future work. |
| Multi-instance operation | CSRF/rate-limit stores and SQLite remain single-instance/local-server oriented. |
| Agent Lab hardening | Agent Lab is implemented but remains experimental because it builds/runs operator-provided code through Docker. |
| Independent assurance | Independent assurance workflow, checklist, and evidence bundle generation are implemented; external independent review remains required before stronger assurance claims. |
| Real-world GenAI assurance | Current harness uses safe synthetic scenarios and controlled validation; broader approved-environment validation remains future maturity work. |

## Safe usage summary

Desktop Mode:

```bash
python scripts/desktop_launch.py
vulnoraiq scan --target <target_name> --profile baseline --authorised
```

Docker Lab Mode:

```bash
docker compose build
docker compose up -d
docker compose exec vulnoraiq-web vulnoraiq targets list
docker compose exec vulnoraiq-web vulnoraiq scan --target <target_name> --profile ai_agent_foundation --authorised
```

## Documentation rule

Keep `README.md`, `docs/README.md`, this file, WebUI/CLI/Docker docs, safety/target docs, scorecard, backlog, assurance doc, `SECURITY.md`, and `CHANGELOG.md` aligned whenever code changes affect deployment posture, target support, WebUI behaviour, CI gates, or release claims.
