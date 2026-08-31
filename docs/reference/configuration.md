# Configuration files

VulnoraIQ reads YAML configuration from one directory, `config/` by default
(override with `VULNORAIQ_CONFIG_DIR`). Everything here is non-secret and safe to
commit; credentials are supplied through
[environment variables](environment-variables.md) instead.

## Precedence

Values resolve in this order, later winning over earlier:

```text
built-in defaults
  → committed YAML under config/
    → environment variables
      → runtime changes made in the console (targets, agent templates)
```

Runtime changes are written to separate files so a committed configuration is
never rewritten by the running application:

- runtime targets → `VULNORAIQ_RUNTIME_TARGETS_PATH`
  (default `<output root>/runtime_targets.yaml`)
- Agent Lab deployments → `VULNORAIQ_AGENT_LAB_DEPLOYMENTS`

## Files

| File | Purpose |
| --- | --- |
| `default.yaml` | Framework metadata and cross-cutting defaults. |
| `targets.yaml` | Committed target definitions. Ships empty: you add the systems you are authorised to assess. |
| `targets.docker.yaml` | Target set used inside Docker Lab Mode (`VULNORAIQ_TARGET_CONFIG`). |
| `targets.test.yaml` | Synthetic fixture targets. Only loaded when fixture targets are explicitly enabled. |
| `targets/templates/*.yaml` | Copyable target templates for common providers and gateways. Every value is a placeholder. |
| `target_contracts.yaml` | Contract rules a target definition must satisfy. |
| `attack_profiles.yaml` | Named assessment profiles and the modules each one runs. |
| `policies.yaml` | Policy gates evaluated against a completed scan, including the authorisation requirement. |
| `policy_exceptions.yaml` | Recorded, justified exceptions to those policies. |
| `safety_profiles.yaml` | Per-target limits: host allowlists, timeouts, payload counts, response size caps. |
| `agent_templates.yaml` | Prebuilt agent images deployable from the Agents workspace. |
| `agent_runtime.yaml`, `agent_runtimes.yaml` | Agent runtime manifests used by policy validation. |
| `agent_execution_scenarios.yaml` | Scenarios for the agent execution harness. |
| `approval_evidence.yaml` | Approval records required by assurance policies. |
| `attack_profiles.yaml` | Assessment profile definitions. |
| `owasp_llm_2025_mapping.yaml` | OWASP LLM Top 10 (2025) mapping data. |
| `owasp_oracles.yaml` | Detection oracles per OWASP category. |
| `production_owasp_detection.yaml` | Production detection coverage definitions. |
| `mitre_atlas_mapping.yaml` | MITRE ATLAS mapping data. |
| `mitre_atlas_source_fixture.yaml` | Fixture source for ATLAS refresh validation. |
| `atlas_refresh.yaml` | ATLAS refresh job settings. |
| `rag_corpus_manifest.yaml`, `rag_retrieval_scenarios.yaml` | RAG assessment corpus and scenarios. |
| `report_branding.yaml` | Report header/branding text. |
| `release_package.yaml` | Files included in a release package. |
| `web_users.yaml`, `web_users.example.yaml` | File-based console users. Not permitted in production mode — use environment tokens. |
| `environment.template` | Copyable starting point for a local, untracked `.env`. |

## Safety profiles

A safety profile is the enforced boundary for one target. It is not advisory:
`safety_profiles.yaml` values are applied on every outbound request.

| Key | Effect |
| --- | --- |
| `allowed_hosts` | Only these hosts may be contacted. Declaring an allowlist is an explicit scope statement. |
| `allowed_schemes` | Restricts the URL scheme. |
| `allow_external_network` | Permits hosts outside loopback/private ranges. Off by default. |
| `request_timeout_seconds` | Per-request timeout. |
| `max_request_body_bytes`, `max_response_body_bytes` | Size caps in both directions. |
| `max_payloads_per_module`, `max_requests_per_scan` | Bounds how much traffic one assessment generates. |
| `max_concurrency` | Parallel request ceiling. |
| `require_authorisation` | Requires an explicit authorisation flag before the scan runs. |
| `destructive_tests` | Kept `false`: VulnoraIQ does not run destructive checks. |
| `redact_secrets`, `persist_raw_evidence` | Evidence handling. |

Without an allowlist and without `allow_external_network`, a target host must
resolve entirely to loopback, private, or link-local addresses. That is what
lets Docker Lab Mode reach an agent by its container name while still refusing a
public host that merely looks internal.

## Related

- [Environment variables](environment-variables.md)
- [Targets guide](../guides/targets.md)
- [Security model](../security/security-model.md)
