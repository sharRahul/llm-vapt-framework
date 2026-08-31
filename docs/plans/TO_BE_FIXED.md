# To be fixed

Defects found by driving the console end to end in a headless browser
(Playwright/Chromium) as a user: every view, every reachable button, a real scan,
finding triage, the intelligence panel, and the failure paths.

**Run conditions.** Console checks use `webui.server` on loopback with local
fixture targets. Docker-backed Agent Lab coverage runs with a local Docker Engine.

Delivered work is recorded in [Fixed items](FIXED_ITEMS.md).

---

## Still to fix

No currently known console defects from this browser-review pass.

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
