# Module and Payload Authoring

This guide explains how to add new assessment modules and safe payload libraries.

## Module model

A module implements the `AssessmentModule` protocol from `modules/base.py`.

Each module exposes:

- `metadata.name`: stable module identifier used by profiles.
- `metadata.owasp_id`: OWASP LLM category or combined mapping.
- `metadata.title`: report-facing title.
- `metadata.component`: affected application layer.
- `metadata.default_severity`: default severity outside demo mode.
- `metadata.recommendation`: remediation guidance.
- `metadata.atlas_mapping`: MITRE ATLAS mapping or pending status.
- `run(context, payloads)`: returns a `Finding`.

## Registry model

`modules/registry.py` owns module registration and lookup.

Current built-in modules are created by `modules/starter.py`. Future enterprise modules should be registered through `ModuleRegistry.register()` and referenced by name in `config/attack_profiles.yaml`.

## Payload libraries

Payload libraries live under `payloads/` and follow the shape documented in `payloads/schema.yaml`.

A payload should include:

```yaml
id: stable-payload-id
category: assessment_category
input: "Safe assessment input text."
expected_behavior: "Expected safe behaviour."
severity_hint: medium
metadata:
  applies_to:
    - module_name
  review_status: reviewed
  tags: [example]
```

## Safety rules

- Do not include real credentials, tokens, private data, tenant IDs, or client information.
- Use safe local fixtures first.
- Keep payload IDs stable because reports reference them as evidence.
- Document expected behaviour clearly.
- Prefer high-level control checks over harmful instructions.
- Keep `README.md` and the affected guide under `docs/` aligned when adding a capability.

## Review checklist

Before merging a new module or payload library:

1. Add or update the relevant profile in `config/attack_profiles.yaml`.
2. Add safe payloads that apply to the module.
3. Add tests for registry resolution and payload selection.
4. Confirm Markdown, JSON, and dashboard reports still render.
5. Confirm configured non-demo targets still require explicit authorisation.
