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
- `contract`: a `ToolContract` declaring what the module may do (see below).

## Tool contract

Every module declares a `ToolContract` from `modules/contract.py`. Metadata says
what a module *is*; the contract says what running it *involves*, which is what
the execution boundary needs before it starts anything:

| Field | What it declares |
| --- | --- |
| `tool_id` | Must equal the name the module is registered under. |
| `purpose` | One line an operator can read. |
| `target_types` | Target types the module supports; `*` means any. |
| `arguments` | An `ArgumentSpec` per argument: type, required, default, choices. |
| `permissions` | Capabilities from `KNOWN_PERMISSIONS`; an unknown name is refused. |
| `execution` | `in_process`, `subprocess`, or `container`. |
| `timeout_seconds`, `max_output_bytes` | The bounds a run must stay inside. |
| `platforms`, `requires_executable` | What must be true for the tool to be available here. |

The built-in review modules all do the same thing — send bounded payloads to the
configured target in process — so `contract_for_metadata()` derives their
contract from the metadata they already declare. Write a contract by hand only
when a module does something different.

Three rules are enforced rather than documented:

- `ModuleRegistry.register()` refuses a module with no contract, or one whose
  `tool_id` does not match the name it is registered under;
- `ToolContract` refuses `subprocess` without `process.spawn` and `container`
  without `docker`;
- `TestRunner` checks availability and target support before a module runs, so a
  tool never sends its first request outside what it declared.

Ask the registry what a module can do without importing or running it:
`ModuleRegistry().contract(name)` and `.contracts()`.

### External tools

A module declared as `execution: "subprocess"` must run through
`core.process_boundary.run_contracted_tool()`. That is the only place VulnoraIQ
spawns a scanner process: it passes an argument array (never a shell string),
bounds the run with the contract's `timeout_seconds`, truncates output at
`max_output_bytes`, and refuses to start when the contract's executable is
absent. It is the same boundary shape `webui/docker_cli.py` gives Docker.

### Proposed actions

`core/tool_request.py` is the validated route from a *proposed* action to
execution: envelope → schema → target/scope → policy → adapter. The default
adapter refuses to execute anything, which is deliberate — VulnoraIQ has no
feature that should act on a model's proposal, and a model that can run commands
is a stated non-goal. The pipeline exists so that a future feature has one
validated route to take rather than inventing its own. A model-originated
request additionally must carry a rationale, may not use `subprocess` or
`container` execution, and may not carry `process.spawn`, `docker`,
`filesystem.write`, or `network.egress`.

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
4. Confirm the module's contract declares the permissions and execution
   environment it actually uses — `tests/test_tool_contracts.py` asserts the
   built-in set stays in process.
4. Confirm Markdown, JSON, and dashboard reports still render.
5. Confirm configured non-demo targets still require explicit authorisation.
