# To be fixed

Defects found by driving the console end to end in a headless browser
(Playwright/Chromium) as a user: every view, every reachable button, a real scan,
finding triage, the intelligence panel, and the failure paths.

**Run conditions.** Console checks use `webui.server` on loopback with local
fixture targets. Docker-backed Agent Lab coverage runs with a local Docker Engine.

Delivered work is recorded in [Fixed items](FIXED_ITEMS.md).

---

## Still to fix

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
- Agent Lab: import → build → health-gate → auto-target → safe scan → cleanup,
  including the crash-cleanup failure path.
- Focus indicators are present; `main`, `nav`, and `lang` are set; no unlabelled
  buttons; no images missing `alt`.
