# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Security

- **Removed a hardcoded administrator token.** `vulnoraiq-internal-admin-token` was accepted by `WebAuthManager.authenticate_token` in any non-production deployment — which is the default — granting full `manage_runtime` access (including Docker control) to anyone who could reach the server. There is now no built-in or default credential anywhere in VulnoraIQ; a token exists only because an operator configured one. A regression test asserts that no shipped value authenticates.
- **Target scope is enforced by address resolution, not hostname text.** `validate_url` previously allowed any host ending in `.internal` or `.local`, so an attacker-controlled public name such as `x.example.internal` passed the scope gate. Every address a host resolves to must now be loopback, private, or link-local unless the target is explicitly allowlisted or opts into `allow_external`. This also fixes Docker Lab Mode, where Agent Lab registers targets by container DNS name: those names were rejected by every shipped safety profile, so the deploy → auto-target → scan flow could not complete in Lab Mode at all.
- **Agent containers are no longer published on every interface.** `webui/agent_host.py` deployed with `-p <port>:<port>`, binding `0.0.0.0` and exposing a deliberately weak assessment target to the whole network. Port mappings without an explicit bind address are now pinned to `127.0.0.1`, and prebuilt-image agents get `--cap-drop ALL` and `--security-opt no-new-privileges:true`, which Agent Lab deployments already had.
- Target URLs that embed credentials (`https://user:pass@host/`) are rejected on save, and the `VULNORAIQ_ALLOWED_TARGET_HOSTS` deployment-wide allowlist plus each target's own `allowed_host_pattern` are now actually enforced — `allowed_host_pattern` was declared in the shipped target templates but never read.
- Removed the `VULNORAIQ_WEBUI_TEST_ADMIN` escalation path, which could return an admin principal outside production and granted nothing real.
- Removed the unreachable `POST /api/projects/deploy` route, which built and ran an arbitrary project image with a host bind-mount and no container restrictions, and was called by no client.

### Fixed

- **A failed scan rendered as a clean zero-finding result.** The asset card showed `Info · RISK 0 · 0 vulns` with nothing indicating the scan had never run. Assets now carry the job status and render a **Scan failed** badge with the reason.
- **A misconfigured target failed with `internal scan error`.** The scanner raises an actionable message ("Target 'x' is a placeholder…"), and the blanket exception handler discarded it. Configuration and authorisation failures now report their own reason; only genuine faults stay opaque.
- **The progress stream announced `target_validated` before validating.** A run against a placeholder target emitted "target validated" and then immediately failed on that same validation. `Scanner.validate_scan()` is now a pre-flight, and the event is emitted only once validation passes.
- **The console could set only one of the seven finding statuses the API accepts.** `accepted_risk`, `false_positive`, `in_progress`, `fixed`, and `wont_fix` were unreachable from the UI. A new review-status control offers all of them and collects the justification the backend requires for `accepted_risk`/`false_positive` before sending, rather than letting the request fail.
- **A stopped Docker engine returned `500 internal server error`.** `DockerCommandError` is handled at the request boundary and returns `502` with Docker's own message, matching how Agent Lab already reported upstream failures.
- **The console had no `<h1>`**, leaving the page with no top-level heading for screen readers or the document outline.
- The console cached no CSRF token, so every mutation cost two requests and ordinary use could trip the rate limiter. The token is now cached inside the server's validity window, with a single retry on expiry.
- **`PATCH` requests were answered with 501.** `_do_PATCH_routes` existed and the console used `PATCH` for finding triage, but no `do_PATCH` method was defined, so every triage update from the console silently failed.
- **Queued scans could vanish.** The API admitted up to `VULNORAIQ_SCAN_QUEUE_LIMIT` scans while only `VULNORAIQ_MAX_CONCURRENT_SCANS` could run; the surplus returned immediately from `run_scan_job` and stayed marked `queued` forever with no worker and no error. Queued scans now wait for a slot (`VULNORAIQ_SCAN_SLOT_WAIT_SECONDS`, default 900s) and fail explicitly if one never frees. Admission control counts waiting scans, and `/metrics` exposes `vulnoraiq_queued_scans`.
- **Scan event ids are stable.** `SqliteJobStore` deleted and re-inserted the entire event list on every job update, renumbering `AUTOINCREMENT` ids underneath an in-flight SSE stream, so a client resuming from `Last-Event-ID` replayed or skipped events. Only new events are appended now.
- **The JSON job-store backend works.** It left every `event_id` at `0`, so `list_events_after` returned nothing and the progress stream stayed empty, and `update_finding` always returned `None`, so finding triage answered 404. Both backends now share one triage rule and behave identically.
- **Scan event streams now terminate.** The response declared `Connection: keep-alive` and carried no `Content-Length`, so after the terminal `done` event a client had no end-of-stream signal and hung until it timed out. Streams are also bounded by `VULNORAIQ_SSE_MAX_STREAM_SECONDS`, so a disappeared client or a wedged job cannot hold a worker thread for the process lifetime.
- Removing an Agent Lab deployment now also removes the scan targets it registered, instead of leaving targets pointing at a container that no longer exists.
- Git and archive imports report a missing tool or a timeout as a normal failure instead of raising an unhandled exception.

### Changed

- **One server entry point.** `webui/assistant_server.py` is now `webui/server.py`, the single composed server used by both run modes (`vulnoraiq-web`). `webui/hosted_server.py` provides the core handler and one shared `serve()` startup gate — logging, auth-mode validation, production checks, background maintenance — so a server cannot come up with a weaker configuration merely because it was started differently. `WebAuthManager.validate_production` is public; callers no longer reach into private members.
- **Request-level security controls have their own module.** CSRF tokens, rate limiting, proxy trust, audit logging, metrics, and response security headers moved from module globals in `hosted_server` into `webui/web_security.py` with explicit classes. Composed servers use that public API instead of importing another module's private helpers.
- **One runtime target registry.** `core/runtime_targets.py` is the single source of truth for targets created at run time, replacing three separate implementations in the scanner, the API layer, and the launcher.
- **One Docker boundary.** All container work goes through `webui/docker_cli.py`: argument arrays only, never a shell string, always bounded by a timeout, with failures typed as `DockerCommandError`.
- Agent Lab source analysis moved to `webui/agent_analysis.py`, separating "understand the agent's HTTP contract" from "build and run containers".
- The console has one HTTP client (`webui/console/src/lib/api.ts`) instead of seven copies of `fetch` plus CSRF plumbing; `apiPost` and `apiPatch` obtain the CSRF token themselves.
- `mypy` is a real gate again: the project-wide `ignore_errors = true` and the per-file `# mypy: ignore-errors` suppressions are gone, and the tree type-checks clean.
- `tests/test_scanner_authorisation.py` is no longer excluded from `pytest`; its stale expectations were rewritten to match intended behaviour.
- The runtime image is slimmer: it installs runtime dependencies only, not the dev toolchain, and the Docker *client* only, not the `docker.io` engine package.
- CI gained a Docker image build-and-smoke-test job and a check that no `.env` file is ever tracked. The placeholder `python-ci.yml` workflow and the validator coupling that kept it alive are gone.

### Removed

- **All tracked `.env*` files.** `.env.example`, `.env.docker.example`, and `.env.production.example` are removed, and `.gitignore` now blocks `.env`, `.env.*`, and both patterns in any subdirectory with no exceptions. Every supported variable is documented in `docs/reference/environment-variables.md`, and `config/environment.template` is the copyable starting point — deliberately not named `.env.*`. `docker-compose.yml` no longer uses `env_file`.
- Dead code: `scripts/launch_webui.py` (a second HTTP server with a conflicting `/api/agents` contract, invoked by no launcher), `webui/agent_runtime.py`, `webui/project_analyzer.py`, `core/orchestrator.py`, `integrations/base.py`, `integrations/adapters.py`, `integrations/endpoint_security.py`, and four empty target-adapter subclasses. Their test coverage was rewritten against the live code paths rather than deleted.
- `requirements.txt`, which duplicated `pyproject.toml` and put `pytest` in the runtime dependency set, and the unused `rich` dependency.
- `docker-compose.override.yml` is now untracked: overrides are per-developer.
- The `ATLAS-MAP-TODO` placeholder identifier, which leaked an internal marker into user-facing findings.

### Documentation

- The README is rewritten as the front door: what VulnoraIQ is and is not, a capability table marking what is supported, experimental, planned, and not supported, and the security boundary stated plainly.
- `docs/` is restructured into `getting-started/`, `guides/`, `development/`, `security/`, `reference/`, `owasp/`, and `plans/`, with `docs/README.md` as the map. `docs/plans/` is the only location for planning documents; completed plans, status documents, internal architecture notes, and QA working material are no longer kept in the repository.
- New pages: environment-variable reference, configuration-file reference, HTTP API reference, findings and evidence, troubleshooting, sandboxing, secrets, responsible use, development setup, and Docker.
- The findings documentation states explicitly where AI-generated analysis sits relative to machine-observed evidence, and that assistant output is never presented as scanner-confirmed.

### Earlier unreleased changes

#### Added

- Agent Lab "deploy any agent → working scannable target": deploying an imported agent now auto-produces a **working** VulnoraIQ scan target matching the agent's real HTTP contract with no manual `docker` commands and no manual target edits. Endpoint detection was enriched (`param_style`, `param_key`, `response_shape`, `response_path`) and given a ranking helper that selects the inference endpoint and skips infrastructure routes (`/`, `/health`, `/refresh`, `/docs`, static). The auto-registered `http_json` target derives its method, endpoint, request-body key, and response-extraction path from that contract, so a chatbot exposed as `GET /get?msg=` returning plain text (e.g. the AIRA Vulnerable-AI-Chatbot) registers correctly instead of POSTing the wrong shape. Deployments now select a **free host port** (a busy host port no longer blocks the run), publish `127.0.0.1:<host>:<container>`, and set a **run-mode-aware `base_url`** (`127.0.0.1:<host-port>` in Desktop Mode, container DNS in Docker Lab Mode). A post-run **health check** gates target registration and cleans up containers that never become reachable. New **External endpoint** (register a running endpoint with no Docker build) and **Hybrid** (local app + external model provider) deployment modes require an authorization acknowledgement. The deploy response and a new WebUI deployment-summary card surface the detected contract, reachable URL, selected endpoint, target ID, ports, deployment mode, and health status, with one-click **Run baseline scan** and **Stop / remove** actions. See `docs/guides/agents.md`.
- CVE correlation for findings: a new online lookup (`integrations/cve_lookup.py`, `POST /api/findings/cve`) queries NVD by keyword/CWE (and OSV when a package is named) and surfaces matching CVE/advisory records in the WebUI intelligence panel. When a lookup succeeds with no match it flags the finding as a *candidate novel/zero-day* for human verification — never asserting a zero-day automatically. Best-effort and offline-safe (reports `online: false` instead of failing).
- Optional in-app assistant model (`pip install -e .[assistant]`): "Ask VulnoraIQ" and AI finding explanations now run a small GGUF model locally via `llama-cpp-python` (CPU or GPU), downloaded once on first use and cached — no Ollama or external API. Answers are grounded in the bundled OWASP notes and the selected finding, with safe `web_fetch` (SSRF-guarded) and allowlisted `read_docs` tools. Degrades gracefully to templated guidance when the model is not installed. New `POST /api/assistant/explain` endpoint; see `docs/guides/model-providers.md`.
- Agent Lab: a per-project **Delete** button (managed projects only; mapped projects shown read-only).
- Direct target authoring in the WebUI **Targets** workspace: the target editor now accepts a target type, HTTP method, base URL, endpoint path, model, response extraction path, and request body template for any direct LLM, RAG, or agent HTTP endpoint — no Agent Lab/Docker deploy required. Target IDs are editable when creating a new target and fixed once saved. Added a **Model set** readiness guardrail for chat/Ollama types. The HTTP method selector supports `GET` (request body fields are sent as query parameters) for chatbots and agents that expose a `GET` endpoint, as well as `POST`/`PUT`. Targets backed by a deployed Agent Lab container still take their base URL/endpoint from the container and remain locked. This restores end-to-end LLM/agent testing for systems the operator already runs.

#### Changed

- Agent Lab `/agent-lab` page no longer shows raw JSON. Project analysis now renders a readable **contract chip** — the actual request VulnoraIQ will send, e.g. `GET /get ?msg= → text` with a colour-coded HTTP method — over a fact grid (framework, ports, Dockerfile, source), and a live "Target VulnoraIQ will create" preview mirrors the deploy form before you build. When no inference endpoint is auto-detected the panel gives direction ("set the method/path yourself, or use External endpoint mode") instead of a silent `null`. Deploy and scan results render as success/failure cards; failed deployments collapse repeated container-log lines (`ERROR … (×9)`) into a scannable block. Added visible keyboard focus outlines and reduced-motion support.
- README, docs index, implementation status, run-mode docs, and manual LLM testing prompt now describe the consolidated normal CI posture through `.github/workflows/ci.yml`.
- WebUI is mitigation-only: removed the "Apply Fix" action and its `status:"fixed"` persistence; relabeled the panel to "Recommended Mitigation" / "Mitigation View" with an explicit "guidance only — a human owner must implement and verify" note. VulnoraIQ advises; it does not change the target.
- Corrected the console branding from "VulnorAIQ" to "VulnoraIQ" everywhere on the UI.
- Agent Lab import: "Local folder upload" is now the default first tab with a clearer "Browse & select your AI agent folder" picker.
- `pytest` no longer pins `basetemp`/`cache_dir` inside the working tree (`.pytest_tmp`). It uses the OS temp dir and the default `.pytest_cache`, avoiding locked/ACL-corrupted leftover directories that made later runs fail with `PermissionError` on Windows.
- The example release package now bundles `docker-compose.yml`, `Dockerfile`, and `config/environment.template` so the included Docker Lab launchers can start the lab from the package alone.

#### Fixed

- Agent Lab deployment health check no longer registers a broken target for a container that never serves its app. The gate was a bare TCP connect, which Docker Desktop's host-side port proxy satisfies even when nothing inside the container is listening (e.g. an app that crash-loops on a bad entrypoint), so a dead deployment could be reported `healthy`/`running` and turned into a scan target. It now requires an actual HTTP response **and** a `running`/not-restarting container state (`docker inspect`) before registering, and aborts + removes the container (surfacing its logs) otherwise. Surfaced by deploying the Raiker agent, whose generated `uvicorn app:app` entrypoint fails to import.
- Agent Lab port detection now recognises a Flask/uvicorn `app.run(..., port=<n>)` kwarg and Dockerfile `EXPOSE` directives. Agents like the AIRA Vulnerable-AI-Chatbot (`app.run('0.0.0.0', port=5000)`, `EXPOSE 5000`) were previously detected as the default port `8000`, so the deploy published a dead container port and the health check hit nothing; they now publish and health-check the real port (`5000`).
- Agent Lab free-port selection (`_free_host_port`) no longer reports an occupied host port as free on Windows. The availability probe set `SO_REUSEADDR`, which on Windows lets a second socket bind a port that already has a listening socket, so a busy host port could still be chosen for publishing. The probe now binds strictly and falls back to an OS-assigned ephemeral port.
- Agent Lab static `/agent-lab` page now pre-fills the endpoint/method/port form from the analyzer's ranked `selected_endpoint` instead of the first detected endpoint. For AIRA the first endpoint is the non-inference index route `/`, so the form seeded `/` and — because those fields are sent as target overrides on deploy — overrode the correctly auto-detected `GET /get` contract with `/`, registering a broken target. (The React **Projects** tab already used `selected_endpoint`.)
- Agent Lab project analysis no longer returns HTTP 500 for Flask projects that use a bare `@app.route("/")` without `methods=` (an optional regex group returned `None`, causing `AttributeError` in endpoint detection).
- Agent Lab deployment removal (`POST /api/agent-lab/deployments/<id>/remove`) now resolves the identifier against the deployment registry (accepting `deployment_id`, `project_id`, or `container_name`) and reports `removed: true` only when a matching container actually existed. Previously a stale/wrong identifier could report success while leaving a container running, because `docker rm -f` exits `0` for a missing container.
- WebUI console no longer loads fonts from the Google Fonts CDN. The stylesheet `@import` and `preconnect` hints were removed so the console renders with bundled/system fonts, works offline, and no longer triggers a Content-Security-Policy console error.
- Content-Security-Policy now includes `font-src 'self' data:`, so bundled console fonts (including inlined `data:` woff2 subsets) load without a CSP violation in the browser console.
- The WebUI now ships an inline SVG favicon, removing the two `GET /favicon.ico` 404s that appeared on every page load.
- Assistant model now loads on GPU by default with automatic CPU fallback. The CUDA `llama-cpp-python` wheel links `cudart`/`cublas`/`nvrtc`, which the `nvidia-*-cu12` pip packages provide; `webui/assistant_llm.py` now registers `site-packages/nvidia/*/bin` on the Windows DLL search path so `ggml-cuda.dll` finds its runtime with no system CUDA toolkit or manual `PATH` setup. Previously the only installed wheel was a CPU build that crashed with `0xc000001d`, so the assistant always dropped to templated guidance. New `assistant-cuda` extra pins the CUDA runtime packages; see `docs/guides/model-providers.md`.

#### Removed

- Redundant `.github/workflows/python-ci.yml` normal CI workflow. The remaining `.github/workflows/ci.yml` keeps the Python matrix, dependency checks, lint, type checking, tests, validators, hosted WebUI flow, functional acceptance, and artifacts.

## [0.3.0] - 2026-06-26

### Removed

- All demo, mock, and fixture targets from default runtime. No default scan target; `--target` is now required. Backend rejects target IDs containing `demo`, `mock`, `fake`, or `fixture` unless `VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS=true` is set.
- `local-mock-agent` service removed from default Docker Compose; moved behind `profiles: ["test"]`.
- `start_demo_scan` permission removed; all scans use `start_configured_scan`.
- Demo special-casing in scan authorisation gate and module severity logic.
- `config/targets.yaml` and `config/targets.docker.yaml` cleaned of all fake targets; replaced with commented templates.
- WebUI "Run Scan" no longer defaults to `target: demo`; requires a configured target; disabled when none exist.

### Added

- Experimental Agent Lab WebUI flow for importing real AI-agent projects, configuring LLM provider settings, choosing CPU/GPU Docker runtime options, building/running agents, auto-creating runtime targets, and launching authorised scans.
- Agent Lab backend APIs under `/api/agent-lab/*` for project import, analysis, Dockerfile generation, deployment, deployment inventory, and cleanup.
- Agent Lab static page served at `/agent-lab` and embedded in the React Project Importer workspace.
- Agent Lab documentation in `docs/guides/agents.md` and the Agent Lab guide.
- Package-data inclusion for `webui/static/agent-lab/*`.
- Agent Lab smoke tests for project ID policy and provider environment mapping.
- OWASP AI Testing Guide foundation suite and single-test Web UI profiles covering GenAI red teaming methodology, CSA agentic AI red teaming, OWASP AI Exchange controls, AI Security and Privacy design, AI VSS scoring review, and NIST AI 100-2 adversarial ML taxonomy alignment.
- Safe `payloads/ai_testing_guide.yaml` methodology payload library for authorised local/internal AI assessment runs.
- Local OWASP lab AI agent target templates for HTTP JSON, chat-completions-compatible, Ollama generate, and webhook JSON contracts.
- Documentation for testing actual local AI agents through `docs/reference/ai-testing-guide.md`.
- Release-only Windows, Linux, and macOS artifact build workflow triggered by published GitHub Releases or manual dispatch only.
- Platform release package builder for native release formats: `vulnoraiq-<version>-windows.zip`, `vulnoraiq-<version>-linux.tar.gz`, and `vulnoraiq-<version>-macos.dmg`.
- On-demand release signing bundle with SHA256 checksums, GitHub artifact attestations, and optional GPG detached signatures.
- Self-bootstrapping double-click release launchers that create `.venv`, install VulnoraIQ locally, and start the WebUI.
- Linux `VulnoraIQ.desktop` launcher descriptor for extracted release packages.
- Release artifact documentation in `docs/development/release-artifacts.md`.
- Python package build workflow for wheel/source distributions, with manual TestPyPI/PyPI publishing using trusted publishing.
- PyPI package publishing documentation in `docs/development/python-package.md`.
- Cross-platform local Web UI launchers for standalone laptop/workstation use.
- Local launcher startup checks for Python runtime, required dependencies, core modules, target/profile config, Web UI assets, output directory, and SQLite job-store readiness.
- Web UI startup and local-server-controls panel with dependency checks, quick-start actions, runtime options, refresh checks, and loopback launcher-mode **Stop local server** control.
- Docker-first AI-agent lab with deterministic mock agent, Docker target config, safety profile, and smoke tooling.
- React target-management workspace with target search/filtering, readiness metrics, validation, authorisation checklist, scan creation controls, and recent job refresh.
- WebUI assistant backend API with CSRF-protected chat requests, server-side model controls, and React model/temperature/instruction controls.
- Expanded real-environment target templates for Anthropic Claude, Google Gemini, Cohere, Ollama, vLLM, LocalAI, Pinecone/LangChain RAG, LangGraph, CrewAI, LiteLLM, Portkey, and AWS Bedrock gateway patterns.
- Future OIDC/JWT authentication implementation plan under `docs/future-plans/`.
- Regression tests that ensure Docker WebUI publishing stays loopback-only and removed archival docs are not re-linked.
- README prerequisites for Docker, launcher, source/package, wheel-build, and WebUI development run paths.
- WebUI visual alignment utilities and regression coverage for icon/text wrapping in the header, cards, and target workspace.
- `docs/getting-started/quick-start.md` with an end-to-end operating guide for startup, clean-state behaviour, target setup, scan execution, finding review, evidence, and safe operation.
- Regression tests that prevent reintroducing WebUI dummy data and verify the user guide remains linked.

### Changed

- Security policy and safety model now explicitly describe Agent Lab as an experimental local-lab capability that requires local Docker build/run access.
- Dockerfile and Compose configuration now prepare Agent Lab import roots and host gateway connectivity for local LLM providers.
- WebUI Project Importer now opens the Agent Lab workflow.
- Web UI styling now honours the user's system light/dark appearance preference through `prefers-color-scheme`.
- Project license changed from MIT to Apache License 2.0.
- Package metadata now declares `Apache-2.0`, includes license files, PyPI classifiers, project URLs, keywords, and a release extra for package builds.
- Package metadata validation now checks PyPI publishing metadata and release extras.
- Documentation now consistently describes VulnoraIQ as a Docker-first, self-hosted laptop/workstation/internal-server application for authorised AI assessment work.
- Current-scope readiness items are now consistently marked **Complete** for the self-hosted/internal assessment scope.
- README, docs index, deployment guide, security policy, implementation status, readiness scorecard, backlog, release checklist, assurance, runbook, incident response, GenAI readiness plan, and Agentic Applications readiness plan were aligned to the same product positioning and completion vocabulary.
- Local standalone launcher mode is documented as a loopback-only convenience path, separate from the hardened hosted/production `vulnoraiq-web` path.
- Docker Compose now publishes the WebUI only on host loopback through `127.0.0.1:8787:8787` for the default local lab.
- WebUI docs now identify the React console as the supported UI and mark the legacy static console direction as superseded.
- `vulnoraiq-web` now starts the assistant-enabled hosted WebUI wrapper.
- Release packaging now rebuilds React assets before packaging and publishes final release bundles from a signing/attestation job.
- README and SECURITY were rewritten to reflect the current loopback-local, self-hosted internal scope.
- WebUI header, target manager, KPI cards, action buttons, and asset cards now use responsive alignment/wrapping rules so icons and labels stay together across narrow layouts.
- WebUI overview/workspace state now comes from backend scans only; clean installs show zero/empty state and previously run scans are loaded from `/api/scans`.

### Fixed

- Browser ZIP upload is wired to the Agent Lab archive import endpoint.
- Web UI catalog toolbar overflow where the `Showing ... options` badge could clip into the neighbouring panel in narrow columns.
- `scripts/run_scan.py` jobs-show typing issue that could fail `mypy` by reusing a loop variable for an optional job lookup.
- Stale documentation index entries that pointed readers toward superseded planning notes.
- WebUI icon/text placement issues caused by fixed-width target panes, non-wrapping button labels, and long target/job labels.

### Removed

- Superseded archival WebUI and Docker planning notes whose useful content is now covered by the current README, Docker, deployment, WebUI, and future-plan docs.
- WebUI mock/demo data module and fallback dashboard/assets/findings so clean startup no longer displays dummy information.

### Notes

- VulnoraIQ findings remain framework evidence requiring human review.
- Experimental Agent Lab imports and runs real operator-provided code. Review imported source and generated evidence before treating results as confirmed.
- This release does not claim certified VAPT-grade assurance or independently validated real-environment GenAI detection coverage.
- Launcher and default Docker Compose modes are intended for local laptop/workstation use only; exposed or shared deployments must use production mode with auth enabled and production configuration validation.
- Platform release artifacts use native formats where practical: Windows `.zip`, Linux `.tar.gz`, and macOS `.dmg`.
- Release packages include checksums and GitHub artifact attestations by default; detached GPG signatures are produced when signing secrets are configured.
- Native OS certificate-signed installers remain future maturity items.
- Direct OIDC/JWT remains future work and is not required for current local single-user use.
- PyPI publication is opt-in and should be tested on TestPyPI before publishing to PyPI.

## [0.2.0] - 2026-06-22

### Added

- Production startup validation.
- Trusted reverse-proxy identity auth mode.
- Structured audit logging with request correlation IDs.
- Prometheus-format metrics endpoint protected by default.
- SQLite backup and restore scripts.
- Docker Compose production-like environment.
- Scan concurrency limits.
- Container smoke test script.
- Production readiness scorecard, runbook, incident response, release checklist, migration guide, and assessment assurance docs.
- Dependency checks in CI.
- OWASP-to-MITRE ATLAS planning crosswalk and mapping metadata validator.
- GenAI security implementation planning docs.
- Agentic Applications security implementation planning docs.
- OWASP source document review index.
- Source-confirmed GenAI Data Security category extraction for `DSGAI01–DSGAI21`.
- Source-confirmed OWASP Top 10 for Agentic Applications category extraction for `ASI01–ASI10`.

### Changed

- Version bumped to 0.2.0.
- Auth, CSRF, rate limiting, security headers, proxy IP resolution, SQLite persistence, HTTP errors, configuration output, metrics, and deployment docs were hardened for the self-hosted application model.
- Production readiness docs were updated for self-hosted internal scope.
- README, SECURITY.md, and docs index were rewritten for the `0.2.0` self-hosted production posture.
- `docs/genai/` and `docs/agentic/` were updated from placeholder planning IDs to source-confirmed ranges.
- Active LLM oracle/check configs now include OWASP-to-ATLAS mapping metadata.

### Fixed

- CSRF expiry test stability.
