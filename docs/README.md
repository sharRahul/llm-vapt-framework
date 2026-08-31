# VulnoraIQ documentation

Maintained documentation for VulnoraIQ `0.3.0`, a self-hosted AI security
assessment application. The project overview and quick start live in the
[root README](../README.md); this page is the map of everything else.

## Getting started

| Document | What it covers |
| --- | --- |
| [Installation](getting-started/installation.md) | Requirements, install paths, and first launch. |
| [Quick start](getting-started/quick-start.md) | First assessment end to end: configure, target, scan, review. |
| [Configuration](getting-started/configuration.md) | What is configurable, where it lives, and precedence. |

## Guides

| Document | What it covers |
| --- | --- |
| [Desktop Mode](guides/desktop-mode.md) | Running VulnoraIQ on your own machine. |
| [Lab Mode](guides/lab-mode.md) | The full containerised lab under Docker Compose. |
| [Web console](guides/web-console.md) | The browser console and its workspaces. |
| [Agents (Agent Lab)](guides/agents.md) | Importing, building, and running an agent as a scan target. |
| [Model providers](guides/model-providers.md) | Providers for imported agents, and the optional in-app assistant. |
| [Targets](guides/targets.md) | Defining and validating what VulnoraIQ is allowed to assess. |
| [Assessments](guides/assessments.md) | Running authorised assessments against real targets. |
| [Findings and evidence](guides/findings.md) | How results are produced, ranked, and reviewed. |
| [Operations](guides/operations.md) | Day-to-day running, backup, and restore. |
| [Troubleshooting](guides/troubleshooting.md) | Symptoms, causes, and checks. |

## Security

| Document | What it covers |
| --- | --- |
| [Security model](security/security-model.md) | Trust boundaries, authorisation, and scope enforcement. |
| [Sandboxing](security/sandboxing.md) | How agent containers are isolated, and what that does not cover. |
| [Secrets](security/secrets.md) | Where credentials are allowed to live. |
| [Responsible use](security/responsible-use.md) | Authorisation expectations before assessing anything. |
| [Assessment assurance](security/assurance.md) | What VulnoraIQ findings do and do not claim. |
| [Incident response](security/incident-response.md) | Handling a problem in a VulnoraIQ deployment. |
| [Supply chain](security/supply-chain.md) | Dependency and image supply-chain controls. |

## Development

| Document | What it covers |
| --- | --- |
| [Development setup](development/development-setup.md) | Getting a working development environment. |
| [Testing](development/testing.md) | The test suites and how to run them. |
| [Docker](development/docker.md) | Building and validating the container image. |
| [Frontend build](development/frontend-build.md) | Building the React console into served assets. |
| [Module authoring](development/module-authoring.md) | Adding assessment modules and payloads. |
| [Release process](development/release-process.md) | Release checklist and gates. |
| [Release artifacts](development/release-artifacts.md) | What a release produces. |
| [Python package](development/python-package.md) | Publishing the distribution. |
| [Contributing](../CONTRIBUTING.md) | Contribution workflow. |

## Reference

| Document | What it covers |
| --- | --- |
| [Configuration files](reference/configuration.md) | Every YAML file VulnoraIQ reads. |
| [Environment variables](reference/environment-variables.md) | Every environment variable, with defaults and sensitivity. |
| [HTTP API](reference/api.md) | The endpoints the console and integrations use. |
| [CLI](reference/cli.md) | `vulnoraiq` commands. |
| [Migration](reference/migration.md) | Moving from earlier versions. |
| [OWASP LLM Top 10 mapping](reference/owasp-llm-mapping.md) | Category-to-implementation mapping. |
| [OWASP LLM category specs](owasp/) | Per-category assessment notes. |
| [OWASP → MITRE ATLAS crosswalk](owasp/OWASP_TO_MITRE_ATLAS_CROSSWALK.md) | Crosswalk between the two frameworks. |
| [MITRE ATLAS matrix](reference/mitre-atlas-matrix.md) | Generated ATLAS matrix. |
| [MITRE ATLAS mapping](reference/mitre-atlas-mapping.md) | How mappings are maintained. |
| [OWASP AI Testing Guide](reference/ai-testing-guide.md) | AITG coverage. |

## Plans

[`plans/`](plans/) is the only place in this repository that holds planning
documents. Completed and historical plans are not kept here.

| Document | What it is |
| --- | --- |
| [To be fixed](plans/TO_BE_FIXED.md) | Defects found by driving the console end to end. |
| [Still missing](plans/STILL_MISSING.md) | Gaps between the intended architecture and the implementation. |
| [Plan index](plans/README.md) | Proposed work, with a suggested order. |

## Keeping documentation honest

Every claim in these pages must be verifiable against the implementation.
When a change alters deployment posture, target support, console behaviour,
security boundaries, or release gates, update the affected page in the same
change. Do not turn framework coverage, synthetic fixture coverage, or a
successful local scan into a certified assurance claim — see
[assessment assurance](security/assurance.md).
