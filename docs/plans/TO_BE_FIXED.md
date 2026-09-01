# To be fixed

Defects found by driving the console end to end in a headless browser
(Playwright/Chromium) as a user: every view, every reachable button, a real scan,
finding triage, the intelligence panel, and the failure paths.

**Run conditions.** Console checks use `webui.server` on loopback against a local
HTTP agent fixture, so the real-target scan path — the one that writes raw
evidence artefacts — is exercised rather than only the deterministic fixture
client. Docker-backed Agent Lab coverage runs with a local Docker Engine, and
the bundled `http_llm_agent` is deployed against a live hosted model provider so
the provider path is exercised with a real key rather than a stub.

Delivered work is recorded in [Fixed items](FIXED_ITEMS.md).

---

## Still to fix

| # | Item | Why it is not fixed here |
| --- | --- | --- |
| T2 | Assistant explanations are still wordier than they should be. | Echoed prompt fields and duplicated fragments are stripped, and a long explanation is now clamped to three lines behind **Show more**, so it no longer pushes the evidence below the fold. What remains is the bundled small model's own verbosity — sentences that restate the prompt and stop mid-clause. That is a model problem, not a console one, and it needs retrieval grounding rather than more prompt cleanup. |
| T4 | LM Studio is the one offered provider not exercised live. | Ollama, OpenAI, OpenRouter, and Anthropic were each deployed from the console with a real key and answered a real prompt. LM Studio uses the same OpenAI-compatible branch as OpenAI and OpenRouter, both of which were verified, so the untested part is the default base URL rather than the call path — but it was not run. |

---

## What was verified working

- Every view loads and every navigation control works; hash deep-links survive a
  reload.
- Target create, save, validate, delete; out-of-scope hosts and URL-embedded
  credentials are refused with clear messages.
- Saving a new target keeps the editor on it, and the header scan selector
  reflects a create or delete without a page reload.
- An existing target's stored endpoint is what the editor shows, so saving
  cannot silently repoint it.
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
- The burn-down chart draws a real series from `GET /api/trends` after a scan,
  and the chart cards are absent rather than empty before the first one.
- API failures reach the operator as the server's message, not as a JSON
  envelope full of escapes.
- CSRF is enforced (403 without a token); artifact path traversal is refused
  (400); artifact download works; evidence outside the evidence root is not
  indexed or served.
- Theme toggle, pane collapse, sort filters.
- No horizontal overflow at any width from 390 px to 1920 px, in all five views,
  and the scan-target selector is reachable at every one of them.
- Agent Lab: import → build → health-gate → auto-target → safe scan → cleanup,
  including the crash-cleanup failure path.
- A template deploy builds the agent's own Dockerfile and takes a provider, base
  URL, model, and API key from the console. Ollama, OpenAI, OpenRouter, and
  Anthropic were each deployed this way and answered a live prompt; a full scan
  was run end to end against the Anthropic-backed agent.
- Focus indicators are present; `main`, `nav`, and `lang` are set; no unlabelled
  buttons; no images missing `alt`.
