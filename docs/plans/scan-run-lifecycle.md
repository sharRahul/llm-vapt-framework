# Plan: an explicit scan run lifecycle

**Status:** proposed
**Addresses:** [STILL_MISSING.md](STILL_MISSING.md) SM-1, SM-2, SM-7
**Size:** medium — backend, one persistence migration

## Problem

A scan run has no modelled lifecycle. `PersistedScanJob.status` is a plain string
assigned from several call sites, with four informal values: `queued`, `running`,
`completed`, `failed`.

Three consequences:

1. **Nothing can be cancelled.** `POST /api/scans` starts a daemon thread and
   there is no way to stop it. For a tool that sends traffic to a target, "stop
   now" is a safety control, not a convenience.
2. **A timed-out run is indistinguishable from a failed one.** Both are `failed`
   with a message, so an operator cannot tell "the target never answered" from
   "the target rejected us".
3. **A restart strands work.** In-flight scans die with the process and their
   rows stay `running` forever. Nothing reconciles them.

## Target states

```text
QUEUED ──► RUNNING ──► ANALYSING ──► COMPLETED
   │           │
   │           ├──► CANCELLED      (operator asked it to stop)
   │           ├──► TIMED_OUT      (exceeded its own budget)
   │           └──► FAILED         (target rejected, config invalid, internal fault)
   └──────────────► CANCELLED      (cancelled before it started)
```

Only states that correspond to something the runner actually does. No
`WAITING_FOR_APPROVAL` until an approval gate exists — inventing states ahead of
behaviour is how the current informal set became untrustworthy.

## Work

### 1. Model the states

`core/scan_state.py`:

```python
class ScanRunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    ANALYSING = "analysing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"

TERMINAL = {COMPLETED, CANCELLED, TIMED_OUT, FAILED}
ALLOWED: dict[ScanRunState, set[ScanRunState]] = {...}

def transition(current, target) -> ScanRunState:
    """Raise InvalidScanTransition if the move is not allowed."""
```

Every status change goes through `transition`. Illegal moves raise rather than
silently corrupting the record.

### 2. Cancellation

- A `CancellationToken` created per run and held in the runner's registry.
- `TestRunner` checks it between modules and between payloads — the natural
  boundaries, so a cancel takes effect within one request rather than mid-request.
- `POST /api/scans/{id}/cancel`, requiring `start_configured_scan`, audited.
- The token is also what enforces a whole-run budget, which produces `TIMED_OUT`
  rather than a generic failure.

### 3. Startup reconciliation

On boot, any job left in a non-terminal state belongs to a process that no longer
exists. Move it to `FAILED` with `"interrupted by a server restart"`. Small, and
it removes a class of permanently-stuck rows.

### 4. Persistence

The four existing values keep their names, so stored rows stay valid. Add a
`scan_transitions` table recording `(scan_id, from, to, at, actor, reason)` — the
audit trail that free-text events cannot provide. Bump `SCHEMA_VERSION`.

### 5. Surface it

- The SSE stream emits a `state_changed` event on every transition.
- `GET /api/scans/{id}` returns the transition history.
- The console shows a **Cancel** button while a run is non-terminal, and renders
  `cancelled` and `timed_out` distinctly from `failed` — the same lesson as the
  failed-scan badge already added.

## Definition of done

- A scan cancelled from the console stops sending requests within one payload and
  ends `cancelled`.
- A scan exceeding its budget ends `timed_out`, not `failed`.
- Every transition is recorded and retrievable.
- An illegal transition raises in tests.
- A restart leaves no job stuck in `running`.

## Explicitly out of scope

Moving execution to a worker process (SM-7's larger half). Startup reconciliation
removes the sharpest edge; the queue/worker decision should be driven by a real
concurrency need, not anticipated.
