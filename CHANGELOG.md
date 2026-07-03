# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added

- Agent Lab "deploy any agent → working scannable target": deploying an imported agent now auto-produces a **working** VulnoraIQ scan target matching the agent's real HTTP contract with no manual `docker` commands and no manual target edits. Endpoint detection was enriched (`param_style`, `param_key`, `response_shape`, `response_path`) and given a ranking helper that selects the inference endpoint and skips infrastructure routes (`/`, `/health`, `/refresh`, `/docs`, static). The auto-registered `http_json` target derives its method, endpoint, request-body key, and response-extraction path from that contract, so a chatbot exposed as `GET /get?msg=` returning plain text (e.g. the AIRA Vulnerable-AI-Chatbot) registers correctly instead of POSTing the wrong shape. Deployments now select a **free host port** (a busy host port no longer blocks the run), publish `127.0.0.1:<host>:<container>`, and set a **run-mode-aware `base_url`** (`127.0.0.1:<host-port>` in Desktop Mode, container DNS in Docker Lab Mode). A post-run **health check** gates target registration and cleans up containers that never become reachable. New **External endpoint** (register a running endpoint with no Docker build) and **Hybrid** (local app + external model provider) deployment modes require an authorization acknowledgement. The deploy response and a new WebUI deployment-summary card surface the detected contract, reachable URL, selected endpoint, target ID, ports, deployment mode, and health status, with one-click **Run baseline scan** and **Stop / remove** actions. See `docs/AGENT_LAB.md`.
- `docs/ready-to-remove/` review queue for completed, superseded, or stale planning documentation that should be reviewed before final deletion.
- CVE correlation for findings: a new online lookup (`integrations/cve_lookup.py`, `POST /api/findings/cve`) queries NVD by keyword/CWE (and OSV when a package is named) and surfaces matching CVE/advisory records in the WebUI intelligence panel. When a lookup succeeds with no match it flags the finding as a *candidate novel/zero-day* for human verification — never asserting a zero-day automatically. Best-effort and offline-safe (reports `online: false` instead of failing).
- Optional in-app assistant model (`pip install -e .[assistant]`): "Ask VulnoraIQ" and AI finding explanations now run a small GGUF model locally via `llama-cpp-python` (CPU or GPU), downloaded once on first use and cached — no Ollama or external API. Answers are grounded in the bundled OWASP notes and the selected finding, with safe `web_fetch` (SSRF-guarded) and allowlisted `read_docs` tools. Degrades gracefully to templated guidance when the model is not installed. New `POST /api/assistant/explain` endpoint; see `docs/ASSISTANT_MODEL.md` (incl. a path to fine-tune your own model on a 16 GB GPU).
- Agent Lab: a per-project **Delete** button (managed projects only; mapped projects shown read-only).
- Direct target authoring in the WebUI **Targets** workspace: the target editor now accepts a target type, HTTP method, base URL, endpoint path, model, response extraction path, and request body template for any direct LLM, RAG, or agent HTTP endpoint — no Agent Lab/Docker deploy required. Target IDs are editable when creating a new target and fixed once saved. Added a **Model set** readiness guardrail for chat/Ollama types. The HTTP method selector supports `GET` (request body fields are sent as query parameters) for chatbots and agents that expose a `GET` endpoint, as well as `POST`/`PUT`. Targets backed by a deployed Agent Lab container still take their base URL/endpoint from the container and remain locked. This restores end-to-end LLM/agent testing for systems the operator already runs.

### Changed

- Active documentation index now points to current guides, implementation status, scorecard, assurance, and future-plan docs instead of completed or stale planning documents.
- README, docs index, implementation status, run-mode docs, and manual LLM testing prompt now describe the consolidated normal CI posture through `.github/workflows/ci.yml`.
- WebUI is mitigation-only: removed the "Apply Fix" action and its `status:"fixed"` persistence; relabeled the panel to "Recommended Mitigation" / "Mitigation View" with an explicit "guidance only — a human owner must implement and verify" note. VulnoraIQ advises; it does not change the target.
- Corrected the console branding from "VulnorAIQ" to "VulnoraIQ" everywhere on the UI.
- Agent Lab import: "Local folder upload" is now the default first tab with a clearer "Browse & select your AI agent folder" picker.
- `pytest` no longer pins `basetemp`/`cache_dir` inside the working tree (`.pytest_tmp`). It uses the OS temp dir and the default `.pytest_cache`, avoiding locked/ACL-corrupted leftover directories that made later runs fail with `PermissionError` on Windows.
- The example release package now bundles `docker-compose.yml`, `Dockerfile`, and `.env.docker.example` so the included Docker Lab launchers can start the lab from the package alone.

### Fixed

- Agent Lab port detection now recognises a Flask/uvicorn `app.run(..., port=<n>)` kwarg and Dockerfile `EXPOSE` directives. Agents like the AIRA Vulnerable-AI-Chatbot (`app.run('0.0.0.0', port=5000)`, `EXPOSE 5000`) were previously detected as the default port `8000`, so the deploy published a dead container port and the health check hit nothing; they now publish and health-check the real port (`5000`).
- Agent Lab free-port selection (`_free_host_port`) no longer reports an occupied host port as free on Windows. The availability probe set `SO_REUSEADDR`, which on Windows lets a second socket bind a port that already has a listening socket, so a busy host port could still be chosen for publishing. The probe now binds strictly and falls back to an OS-assigned ephemeral port.
- Agent Lab static `/agent-lab` page now pre-fills the endpoint/method/port form from the analyzer's ranked `selected_endpoint` instead of the first detected endpoint. For AIRA the first endpoint is the non-inference index route `/`, so the form seeded `/` and — because those fields are sent as target overrides on deploy — overrode the correctly auto-detected `GET /get` contract with `/`, registering a broken target. (The React **Projects** tab already used `selected_endpoint`.)
- Agent Lab project analysis no longer returns HTTP 500 for Flask projects that use a bare `@app.route("/")` without `methods=` (an optional regex group returned `None`, causing `AttributeError` in endpoint detection).
- Agent Lab deployment removal (`POST /api/agent-lab/deployments/<id>/remove`) now resolves the identifier against the deployment registry (accepting `deployment_id`, `project_id`, or `container_name`) and reports `removed: true` only when a matching container actually existed. Previously a stale/wrong identifier could report success while leaving a container running, because `docker rm -f` exits `0` for a missing container.
- WebUI console no longer loads fonts from the Google Fonts CDN. The stylesheet `@import` and `preconnect` hints were removed so the console renders with bundled/system fonts, works offline, and no longer triggers a Content-Security-Policy console error.
- Content-Security-Policy now includes `font-src 'self' data:`, so bundled console fonts (including inlined `data:` woff2 subsets) load without a CSP violation in the browser console.
- The WebUI now ships an inline SVG favicon, removing the two `GET /favicon.ico` 404s that appeared on every page load.
- Assistant model now loads on GPU by default with automatic CPU fallback. The CUDA `llama-cpp-python` wheel links `cudart`/`cublas`/`nvrtc`, which the `nvidia-*-cu12` pip packages provide; `webui/assistant_llm.py` now registers `site-packages/nvidia/*/bin` on the Windows DLL search path so `ggml-cuda.dll` finds its runtime with no system CUDA toolkit or manual `PATH` setup. Previously the only installed wheel was a CPU build that crashed with `0xc000001d`, so the assistant always dropped to templated guidance. New `assistant-cuda` extra pins the CUDA runtime packages; see `docs/ASSISTANT_MODEL.md`.

### Removed

- Redundant `.github/workflows/python-ci.yml` normal CI workflow. The remaining `.github/workflows/ci.yml` keeps the Python matrix, dependency checks, lint, type checking, tests, validators, hosted WebUI flow, functional acceptance, and artifacts.
- Completed/superseded planning docs from the active documentation tree; copies were staged in `docs/ready-to-remove/` for maintainer review before final deletion.

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
- Agent Lab documentation in `docs/AGENT_LAB.md` and implementation plan in `docs/AGENT_LAB_PLAN.md`.
- Package-data inclusion for `webui/static/agent-lab/*`.
- Agent Lab smoke tests for project ID policy and provider environment mapping.
- OWASP AI Testing Guide foundation suite and single-test Web UI profiles covering GenAI red teaming methodology, CSA agentic AI red teaming, OWASP AI Exchange controls, AI Security and Privacy design, AI VSS scoring review, and NIST AI 100-2 adversarial ML taxonomy alignment.
- Safe `payloads/ai_testing_guide.yaml` methodology payload library for authorised local/internal AI assessment runs.
- Local OWASP lab AI agent target templates for HTTP JSON, chat-completions-compatible, Ollama generate, and webhook JSON contracts.
- Documentation for testing actual local AI agents through `docs/AI_TESTING_GUIDE_INTEGRATION.md`.
- Release-only Windows, Linux, and macOS artifact build workflow triggered by published GitHub Releases or manual dispatch only.
- Platform release package builder for native release formats: `vulnoraiq-<version>-windows.zip`, `vulnoraiq-<version>-linux.tar.gz`, and `vulnoraiq-<version>-macos.dmg`.
- On-demand release signing bundle with SHA256 checksums, GitHub artifact attestations, and optional GPG detached signatures.
- Self-bootstrapping double-click release launchers that create `.venv`, install VulnoraIQ locally, and start the WebUI.
- Linux `VulnoraIQ.desktop` launcher descriptor for extracted release packages.
- Release artifact documentation in `docs/RELEASE_ARTIFACTS.md`.
- Python package build workflow for wheel/source distributions, with manual TestPyPI/PyPI publishing using trusted publishing.
- PyPI package publishing documentation in `docs/PYPI_PACKAGE.md`.
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
- `docs/USER_GUIDE.md` with an end-to-end operating guide for startup, clean-state behaviour, target setup, scan execution, finding review, evidence, and safe operation.
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
