# To be fixed

Defects found by driving the console end to end in a headless browser
(Playwright/Chromium) as a user: every view, every reachable button, a real scan,
finding triage, the intelligence panel, and the failure paths.

**Run conditions.** Console checks use `webui.server` on loopback against a local
HTTP agent fixture, so the real-target scan path — the one that writes raw
evidence artefacts — is exercised rather than only the deterministic fixture
client. Docker-backed Agent Lab coverage runs with a local Docker Engine.

Delivered work is recorded in [Fixed items](FIXED_ITEMS.md).

---

## Still to fix

| # | Item | Why it is not fixed here |
| --- | --- | --- |
| T1 | The console's product rules have no component tests. | This pass changed target readiness, terminal-state rendering, phase labels, and the evidence panel; each was verified by driving a browser, not by a test that fails on a regression. Tracked as [SM-10](STILL_MISSING.md); it needs Vitest and Testing Library, which the console does not have yet. |
| T2 | Assistant explanations are still wordier than they should be. | Echoed prompt fields and duplicated fragments are now stripped, which fixes the wall of repeated prose. What remains is the bundled small model's own verbosity, which is a model problem rather than a console one. |
| T3 | The burn-down chart is permanently empty. | It has no data source: nothing aggregates findings across scans over time. The empty state is honest, but the card occupies half the dashboard to say nothing. Either give it a real series or drop it. |

---

## What was verified working

- Every view loads and every navigation control works; hash deep-links survive a
  reload.
- Target create, save, validate, delete; out-of-scope hosts and URL-embedded
  credentials are refused with clear messages.
- Target readiness agrees across the sidebar badge, the guardrails panel, and the
  header scan selector.
- Scan queue → run → analyse → complete against a real HTTP agent, with the
  transition history recorded and returned.
- Cancelling a running scan from the console ends it `cancelled`, not `failed`,
  and names the operator who stopped it.
- A run that exceeds its budget ends `timed_out`.
- SSE progress: unique monotonic ids, human phase labels, heartbeats excluded
  from the timeline, terminal event carrying the precise state, clean close.
- Findings list, selection, evidence, remediation, OWASP mapping, provenance
  badge.
- Raw evidence: the index lists real artefacts and one opens to show the captured
  request and response.
- Triage across all seven statuses, with the required justification and audit
  history.
- The assistant panel answers and its output is labelled advisory.
- CSRF is enforced (403 without a token); artifact path traversal is refused
  (400); artifact download works; evidence outside the evidence root is not
  indexed or served.
- Theme toggle, pane collapse, sort filters.
- No horizontal overflow at any width from 390 px to 1920 px, in all five views.
- Agent Lab: import → build → health-gate → auto-target → safe scan → cleanup,
  including the crash-cleanup failure path.
- Focus indicators are present; `main`, `nav`, and `lang` are set; no unlabelled
  buttons; no images missing `alt`.
