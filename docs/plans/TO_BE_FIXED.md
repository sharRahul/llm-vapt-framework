# To be fixed

Defects found by driving the console end to end in a headless browser
(Playwright/Chromium) as a user: every view, every reachable button, a real scan,
finding triage, the intelligence panel, and the failure paths.

**Run conditions.** Server: `webui.server` on loopback, `local_admin` auth,
fixture targets enabled (`targets.test.yaml`). Docker Engine was **not running**,
so container deployment could only be tested for graceful failure, not success.

**Result:** 0 uncaught console errors, 0 unhandled page errors, 0 unexpected
failed requests. Seven defects found; six fixed in the same pass. What remains is
below.

---

## Fixed during this pass

Listed for the record — each has a regression test.

| # | Defect | Fix |
| --- | --- | --- |
| F1 | A misconfigured target failed with `internal scan error`. The scanner raised an actionable message ("Target 'x' is a placeholder…") and the blanket `except Exception` discarded it. | `run_scan_job` now handles `ValueError`/`PermissionError` separately and reports the real reason. |
| F2 | A **failed scan rendered as a clean zero-finding result** — `Info · RISK 0 · 0 vulns`, with nothing telling the user it never ran. | `Asset` carries `scanStatus`/`scanError`; the card shows a red **Scan failed** badge and the reason. |
| F3 | The progress stream emitted `target_validated` *before* validation, then immediately failed on that same validation. | Added `Scanner.validate_scan()` pre-flight. The event is emitted only after validation genuinely passes. |
| F4 | A scan failure toast said "check backend logs" instead of the reason the backend had already produced. | The toast now shows the backend's message. |
| F5 | The console could set only **one** of the seven finding statuses the API accepts (`triaged`, via "Mark for Review"). `accepted_risk`, `false_positive`, `in_progress`, `fixed`, `wont_fix` were unreachable. | New `TriageControl`: all seven statuses, and it collects the justification the backend requires for `accepted_risk`/`false_positive` **before** sending, rather than letting the request fail. |
| F6 | Deploying an agent with Docker stopped returned `500 internal server error`. | `DockerCommandError` is handled at the request boundary and returns `502` with Docker's own message. |
| F7 | Every mutation fetched a fresh CSRF token, doubling request volume per user action and tripping the rate limiter during ordinary use. | The console caches the token for 120s (server TTL is 300s) and retries once on a `403`. |
| F8 | The console had **no `<h1>`** — no top-level heading for screen readers or the document outline. | The brand mark is now the `h1`; the finding title is an `h2`. |

---

## Still to fix

### TBF-1 — Two different Agent Lab user interfaces · **High**

**What happens.** `/agent-lab` (hand-written page) and the console's **Projects**
tab (React) both drive the same Agent Lab API, and they are not equivalent.

Measured in the browser:

| | React Projects tab | Standalone `/agent-lab` |
| --- | --- | --- |
| Inputs / selects | 3 | 20 |
| Import: local folder | yes | yes |
| Import: ZIP upload | **no** | yes |
| Import: Git URL | disabled | yes |
| Import: mapped folder | **no** | yes |
| Per-project delete | **no** | yes |
| Custom env vars | **no** | yes |
| Container port control | **no** | yes |
| Explicit "Start authorised scan" | **no** | yes |

**Why it matters.** Whichever the user finds first determines what they can do.
Two implementations of one feature also means two places to fix every Agent Lab
bug — the standalone page already had a bug the React tab did not.

**Fix.** Bring the React Projects tab to parity, then delete
`webui/static/agent-lab/` and the `/agent-lab` route. Plan:
[`agent-lab-ui-consolidation.md`](agent-lab-ui-consolidation.md).

---

### TBF-2 — The first target offered is one that always fails · **Medium**

**What happens.** The header target selector defaults to the first target
alphabetically. With the shipped test config that is
`Placeholder Custom HTTP Agent`, whose endpoint is `https://example.invalid` —
so the first scan a new user runs always fails.

**Why it matters.** The very first action in the product fails, for a reason
that is about configuration rather than anything the user did.

**Fix.** Default to the first target that passes validation; mark unusable
targets in the selector and disable **Run Scan** while one is selected. Better:
have `GET /api/targets` return a `ready` flag per target so both the console and
the CLI agree on which targets can actually be assessed.

---

### TBF-3 — Live scan progress is unobservable at the end of a scan · **Low**

**What happens.** The "Live backend scan" panel renders only on the Overview,
but on `scan_completed` the app switches the user to the Workspace. By the time
you look, the panel is on a view you have left.

**Fix.** Either keep the progress panel in the shell (visible on every view while
a scan runs), or stop force-switching views and surface completion as a toast
with a link.

---

### TBF-4 — Asset auto-expansion depends on render timing · **Low**

**What happens.** `AssetNavigationPane` seeds its expanded state with a lazy
`useState` initialiser reading `assets[0]?.id`. Assets arrive asynchronously, so
if the pane mounts before the first asset lands, nothing is ever auto-expanded
and the user sees a collapsed card with no findings.

**Fix.** Derive the expanded state from the selected finding's asset, or sync it
in an effect when `assets` changes.

---

### TBF-5 — SVG chart internals are in the tab order · **Low**

**What happens.** Tabbing through the console lands on an SVG `<g>` element and
on `body`. Neither is interactive and neither is labelled.

**Fix.** Mark decorative chart SVGs `aria-hidden="true"` / `focusable="false"`,
and remove the stray tabindex.

---

### TBF-6 — Container deployment is unverified end to end · **Blocked**

Docker Engine was not running on the test machine, so Agent Lab deploy, the
health gate, auto-target registration, and container cleanup were exercised only
for their failure paths (which behave correctly, and now report actionable
errors — F6).

This is an environment limitation, not a known defect. CI now builds the image
and smoke-tests the container, but the **Agent Lab deploy → auto-target → scan**
flow has no automated coverage. Plan:
[`agent-lab-e2e-coverage.md`](agent-lab-e2e-coverage.md).

---

## What was verified working

- Every view loads and every navigation control works; hash deep-links and
  survive a reload.
- Target create, save, validate, delete; out-of-scope hosts and URL-embedded
  credentials are refused with clear messages.
- Scan queue → run → complete, with 6 findings from the fixture target.
- SSE progress: 12 events, unique monotonic ids, terminal `done`, clean close.
- Findings list, selection, evidence, remediation, OWASP mapping.
- Triage across all seven statuses, with the required justification and audit
  history.
- The assistant panel answers and its output is labelled advisory.
- CSRF is enforced (403 without a token); artifact path traversal is refused
  (400); artifact download works.
- Theme toggle, pane collapse, sort filters.
- No horizontal overflow at 390×844 or 820×1180.
- Focus indicators are present; `main`, `nav`, and `lang` are set; no unlabelled
  buttons; no images missing `alt`.
