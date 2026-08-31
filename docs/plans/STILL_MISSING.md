# Still missing

Gaps between the architecture VulnoraIQ is aiming at and what the code currently
implements. These are not bugs — nothing here is broken. They are places where a
boundary the design assumes does not yet exist, or exists only partially.

Ordered by how much each one constrains what can safely be built next.

---

## SM-1 — There is no agent runtime state machine · **High**

**The design assumes.** An agent run moves through explicit, observable states:
`CREATED → PREPARING → READY → RUNNING → WAITING_FOR_TOOL / WAITING_FOR_APPROVAL
→ RUNNING → ANALYSING → COMPLETED`, with terminal `FAILED`, `CANCELLED`,
`TIMED_OUT`, `BLOCKED`.

**What exists.** A `PersistedScanJob` with four informal statuses — `queued`,
`running`, `completed`, `failed` — set by string assignment from several places.
There is no transition table, nothing rejects an invalid transition, and there is
no `cancelled` or `timed_out` state at all: a timed-out scan is recorded as
`failed` with a message.

**What this blocks.** Cancellation, approval gates, resumable runs, and any
honest "what is this run doing right now" view. It also makes the state
untestable as a unit — you can only assert on the end result.

**Shape of the work.** A `ScanRunState` enum plus a `transition(from, to)` that
raises on an illegal move; persist transitions as first-class rows rather than
free-text events; add `cancelled` and `timed_out`. Scope it to the scan runner
first — Agent Lab deployments can adopt the same machine afterwards.

---

## SM-2 — Scan runs cannot be cancelled · **High**

**What exists.** `POST /api/scans` starts a daemon thread. Nothing can stop it.
A scan against a slow or hanging target runs until its own timeouts expire, and
the operator can only wait or restart the process.

**Why it matters for a security tool.** "Stop sending traffic to that target,
now" is a safety control, not a convenience. An operator who realises they have
the wrong target has no way to act on that realisation.

**Shape of the work.** A cancellation token carried into `TestRunner` and checked
between modules and between payloads; `POST /api/scans/{id}/cancel`; a
`cancelled` terminal state (SM-1); the SSE stream emitting the cancellation.

---

## SM-3 — There is no tool/scanner contract · **High**

**The design assumes.** Each external tool declares a contract: identifier,
purpose, supported target types, argument schema, permissions, execution
environment, timeout, output limits, parser, structured result, error types,
platform support, availability check.

**What exists.** Assessment modules implement `run(context, payloads) -> Finding`
and nothing else. There is no declared argument schema, no availability check, no
per-tool timeout or output cap, and no way to ask "what can this module actually
assess?" before running it.

**What this blocks.** Integrating a real external scanner. Today VulnoraIQ's
assessment surface is HTTP requests it makes itself; the moment a third-party
binary is wrapped, every one of those properties has to exist or the execution
boundary is guesswork.

**Shape of the work.** A `ToolContract` dataclass and a registry; make the
existing modules declare theirs (they will mostly be trivial); route external
process execution through the same `docker_cli`-style boundary already used for
Docker.

---

## SM-4 — Findings have no first-class provenance · **Medium**

**The design assumes.** A finding distinguishes raw tool output, observation,
inferred finding, and confirmed vulnerability, and records source, tool,
timestamp, confidence, and analysis provenance as structured fields.

**What exists.** `Finding` has `evidence: dict[str, Any]`. Modules put confidence
and limitations in there by convention, with no schema. `docs/guides/findings.md`
documents the distinction accurately as a *practice*; the type system does not
enforce it.

**Why it matters.** The product's core claim is that findings are evidence, not
verdicts. That claim currently rests on convention. A module that omitted
confidence would produce a finding indistinguishable from a well-evidenced one.

**Shape of the work.** Promote `source`, `tool`, `confidence`, `observed_at`, and
`analysis_provenance` to typed fields on `Finding` with a required
`FindingSource` enum (`scanner_observed` / `inferred` / `ai_assisted`);
validate at construction; carry them through the report generators.

---

## SM-5 — No structured tool-request path from model output · **Medium**

**The design assumes.** `LLM output → structured tool request → schema
validation → target/scope validation → policy validation → execution adapter →
sandbox → structured result`.

**What exists.** The safe half of that: the assistant produces text for a human
and has no path to execution, which is the correct default and is enforced by
there being no such path at all.

**What is missing.** Nothing implements the pipeline, so any future feature that
lets a model *propose* an action (suggest a payload, pick the next module,
request a scanner run) has no validated route to take. It would have to invent
one, and the safe design is much harder to add later than now.

**Shape of the work.** Define the request envelope and the validation chain
before the first feature needs it, even with a single trivial tool behind it.
Depends on SM-3.

---

## SM-6 — Configuration is not validated at startup · **Medium**

**The design assumes.** Configuration is validated at startup and fails early
with useful errors.

**What exists.** Each YAML file is read lazily by whoever needs it and coerced
ad hoc. A malformed `attack_profiles.yaml` surfaces as a failed scan; a
malformed `safety_profiles.yaml` silently yields an empty profile — which
*weakens* enforcement rather than failing closed. The production checks
(`webui/production_checks.py`) cover deployment settings, not the YAML.

**Why it matters.** A safety profile that fails to parse should stop the server,
not quietly remove the limits it was supposed to impose.

**Shape of the work.** Typed config models loaded once at startup, validated
together, with a `--check-config` mode; fail closed on an unparseable safety
profile.

---

## SM-7 — Long scans still run in-process · **Medium**

**What exists.** Scans run on daemon threads inside the web server. Concurrency
is bounded and queued work now waits properly, but the work still shares the
server's process, memory, and lifetime. A server restart loses every in-flight
scan with no recovery — the job stays `running` in the database forever.

**Shape of the work.** Either reconcile orphaned `running` jobs at startup (small,
worth doing regardless), or move execution to a worker process. The reconciliation
step is a prerequisite either way.

---

## SM-8 — Evidence is written but never read back · **Low**

`VULNORAIQ_EVIDENCE_DIR` is consumed by `core/real_scan.py`, which writes raw
request/response evidence to disk. Nothing reads it: no API endpoint serves it,
the console cannot show it, and it is not included in the report artefacts. The
evidence a human reviewer would most want is the least reachable.

**Shape of the work.** An evidence index per scan, an artifact route that serves
it under the same authorisation rules as reports, and a link from the finding
detail pane.

---

## SM-9 — The role model has one unused level · **Low**

`analyst` carries exactly the same permissions as `viewer`. It is a configurable
identity, documented as such, and harmless — but the name promises capability the
role does not have. Either give analysts `start_configured_scan` (the obvious
meaning) or retire the role at the next breaking change.

---

## SM-10 — No frontend test suite · **Low**

The console has TypeScript checking and a production build, plus one Playwright
flow that starts a scan. There are no component tests. Rendering logic that
matters — severity mapping, risk scoring, the failed-scan state, triage
validation — is only covered indirectly through a browser.

**Shape of the work.** Vitest plus Testing Library for the pure functions and the
handful of components that encode product rules. Not a large job, and it is what
makes frontend changes safe to review.

---

## Explicitly not missing

Recorded so they are not re-raised:

- **OIDC / JWT identity** — deliberately deferred; see
  [`oidc-jwt-auth.md`](oidc-jwt-auth.md). Token and trusted-proxy modes cover the
  supported deployments.
- **Multi-tenancy / RBAC beyond three roles** — out of scope. VulnoraIQ is a
  single-operator tool; adding enterprise RBAC would imply isolation it does not
  provide.
- **Microservice decomposition** — no problem in the codebase calls for it.
- **A model that can execute commands** — this is a deliberate non-goal, not a
  gap.
