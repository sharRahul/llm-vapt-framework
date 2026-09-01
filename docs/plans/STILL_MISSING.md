# Still missing

Gaps between the architecture VulnoraIQ is aiming at and what the code currently
implements. These are not bugs — nothing here is broken. They are places where a
boundary the design assumes does not yet exist, or exists only partially.

Ordered by how much each one constrains what can safely be built next.

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

## SM-7 — Long scans still run in-process · **Low**

**What exists.** Scans run on daemon threads inside the web server. Concurrency
is bounded, queued work waits properly, a run can be cancelled, and a restart no
longer strands rows — startup reconciliation moves any non-terminal job to
`failed`. What remains is that the work still shares the server's process,
memory, and lifetime.

**Shape of the work.** Move execution to a worker process. Deliberately not done
yet: the reconciliation step removed the sharp edge, and the queue/worker
decision should be driven by a real concurrency need rather than anticipated.

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

## Delivered

Removed from this list once the boundary exists. Kept here as a pointer so the
numbering stays stable and a reader does not wonder where an item went.

| Item | Where it lives now |
| --- | --- |
| SM-1 — no agent runtime state machine | `core/scan_state.py`; transitions persisted in `scan_transitions` and returned by `GET /api/scans/{id}`. |
| SM-2 — scan runs cannot be cancelled | `core/cancellation.py`, `POST /api/scans/{id}/cancel`, and the console's **Stop** control. |
| SM-4 — findings have no first-class provenance | `source`, `confidence`, `tool`, and `observed_at` are required fields on `Finding`, carried through all three report formats and shown as a badge. |
| SM-6 — configuration is not validated at startup | `core/config_validation.py`, run on every start and available as `--check-config`; safety profiles fail closed. |
| SM-8 — evidence is written but never read back | `core/evidence_index.py`, the `/evidence` routes, and the console's **Raw evidence** panel. |

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
