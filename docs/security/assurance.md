# Assessment assurance

This document separates VulnoraIQ application readiness from scanner/evaluator assurance.

VulnoraIQ `0.3.0` is a self-hosted AI security testing lab with Docker-first local target testing, a React WebUI, CLI, target adapters, reports, and readiness gates. Its findings are still **framework evidence requiring human review**, not certified VAPT-grade assurance.

## What findings mean today

- Findings show that a configured profile, payload, target adapter, evaluator, oracle, and policy path observed a condition worth review.
- Docker mock-agent scans prove wiring and deterministic scenario behaviour, not real-world assurance.
- GenAI scenario-harness results prove scenario/evidence/evaluator consistency for safe synthetic data, not independent real-environment detection assurance.
- OWASP/MITRE/Agentic mappings support coverage planning and reporting context, not a guarantee that every mapped technique is detectable.
- A human tester must review target scope, evidence, logs, environmental context, and remediation before treating a finding as confirmed.

## Current coverage summary

| Area | Current status | Assurance boundary |
| --- | --- | --- |
| OWASP LLM 2025 | Complete for current safe local/internal scope across all 10 categories. | Safe oracle/fixture coverage, not independent VAPT certification. |
| OWASP AI Testing Guide | Foundation profile and safe methodology harness implemented. Full 32-test implementation remains planned. | Methodology/evidence harness, not full AITG assurance. |
| Agentic Applications | Repo-level self-hosted readiness gates complete. | Operational readiness, not independent agentic security assurance. |
| GenAI Security | `DSGAI01–DSGAI21` scenario harness complete with 84 safe scenario cases. | Synthetic scenario validation, not real sensitive-data detection assurance. |
| MITRE ATLAS | Planning matrix and mapping governance complete for current scope. | Mapping support, not technique-level detection certification. |
| Docker lab | Deterministic mock-agent/RAG/tool-loop targets complete. | Lab target proof, not production target assurance. |

## Evidence collected

VulnoraIQ may collect:

- target/profile/module metadata;
- request/response observations needed for scanner evidence;
- oracle/evaluator outputs;
- policy decisions and finding scores;
- GenAI scenario evidence fields;
- job metadata;
- Markdown, JSON, SARIF, dashboard, and HTML reports;
- audit logs and metrics for application operations.

Evidence must be reviewed before sharing. Reports can contain sensitive target responses if a real authorised system returns them.

## Evidence not guaranteed

VulnoraIQ does not automatically guarantee collection of:

- full provider logs;
- enterprise SIEM/SOAR telemetry;
- host/network telemetry;
- cloud account configuration;
- source code, prompts, policy bundles, or model-management settings unless provided through approved integrations;
- organisation-specific legal/privacy risk decisions.

## False positives and false negatives

False positives are expected where heuristic checks or synthetic scenario assumptions do not match the environment.

False negatives are expected where:

- a profile lacks a relevant payload or oracle;
- target behaviour is non-deterministic;
- evidence is unavailable;
- a real system needs grey-box/white-box context;
- a framework mapping is broader than current implemented checks;
- the risk depends on organisation-specific data-governance or provider configuration.

## Requirements before stronger claims

Before external VAPT-grade or independent assurance claims can be made, VulnoraIQ needs:

1. independently reviewed scanner/evaluator logic;
2. calibrated thresholds against known-good and known-vulnerable approved targets;
3. approved-environment validation for AI agents, RAG systems, vector stores, providers, telemetry, and data-governance workflows;
4. report-language review to prevent overclaiming;
5. SIEM/operational evidence integration where relevant;
6. independent security assessment of the WebUI, API, target adapters, Docker lab, and release artifacts.

## Allowed report language

Use wording such as:

> Finding requires human review. Evidence was produced by a VulnoraIQ controlled assessment profile and should be validated against target scope, logs, architecture, and business context.

Do not use wording that states or implies certified assurance, guaranteed exploitability, or permission to test third-party systems.
