# Still missing

Gaps between the architecture VulnoraIQ is aiming at and what the code currently
implements. These are not bugs — nothing here is broken. They are places where a
boundary the design assumes does not yet exist, or exists only partially.

Ordered by how much each one constrains what can safely be built next. Only one
remains, and it is deliberately deferred.

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

## Delivered

Removed from this list once the boundary exists. Kept here as a pointer so the
numbering stays stable and a reader does not wonder where an item went.

| Item | Where it lives now |
| --- | --- |
| SM-1 — no agent runtime state machine | `core/scan_state.py`; transitions persisted in `scan_transitions` and returned by `GET /api/scans/{id}`. |
| SM-2 — scan runs cannot be cancelled | `core/cancellation.py`, `POST /api/scans/{id}/cancel`, and the console's **Stop** control. |
| SM-3 — no tool/scanner contract | `modules/contract.py`; declared by every module, enforced by `ModuleRegistry.register` and `TestRunner`, with external processes bounded by `core/process_boundary.py`. |
| SM-4 — findings have no first-class provenance | `source`, `confidence`, `tool`, and `observed_at` are required fields on `Finding`, carried through all three report formats and shown as a badge. |
| SM-5 — no structured tool-request path | `core/tool_request.py`: envelope → schema → scope → policy → adapter, with a refusing adapter as the default. |
| SM-6 — configuration is not validated at startup | `core/config_validation.py`, run on every start and available as `--check-config`; safety profiles fail closed. |
| SM-8 — evidence is written but never read back | `core/evidence_index.py`, the `/evidence` routes, and the console's **Raw evidence** panel. |
| SM-9 — the role model has one unused level | `analyst` carries `start_configured_scan` in `webui/auth.py`; it can run a configured scan but not change the configuration. |
| SM-10 — no frontend test suite | Vitest and Testing Library under `webui/console/src/**/*.test.{ts,tsx}`, run by `npm test` and by CI. |

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
