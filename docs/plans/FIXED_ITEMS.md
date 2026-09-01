# Fixed items

Completed defects and delivery work are recorded here. Each entry has regression
coverage in the test suite; proposed plans are removed once delivered.

| # | Item | Resolution |
| --- | --- | --- |
| F1 | Actionable scan errors were hidden. | The WebUI preserves validation and permission failures. |
| F2 | Failed scans looked like empty results. | Assets show the failure status and reason. |
| F3 | Validation progress was emitted too early. | Pre-flight validation completes before its event is sent. |
| F4 | Failure toasts hid backend reasons. | The reported backend message is shown to the operator. |
| F5 | Most triage states were unreachable. | The console supports every persisted status and required justifications. |
| F6 | Docker failures became HTTP 500s. | Docker errors return actionable 502 responses. |
| F7 | Mutations repeatedly fetched CSRF tokens. | The console caches and safely retries its CSRF token. |
| F8 | The console lacked a top-level heading. | The brand mark is the accessible `h1`. |
| F9 | Agent Lab had two divergent interfaces. | The React **Projects** view now has folder, ZIP, Git, mapped-folder refresh, delete, runtime variables, port, deploy/remove, and scan controls. `/agent-lab` redirects to `/#/projects`; the static page and package entry are gone. |
| F10 | Agent Lab deployment was not tested end to end. | Docker CI and a local fixture test cover build, health-gate, auto-target registration, authorised scan, cleanup, and crash cleanup. |
| F11 | The first header target could be unusable. | The target API provides readiness; the selector defaults to a ready target, labels unavailable entries, and disables scans when none is ready. |
| F12 | Scan completion interrupted the operator’s work. | Completion refreshes results without switching the current view. |
| F13 | Scan assets sometimes arrived collapsed. | The navigation pane expands the first asynchronously loaded asset while preserving an explicit collapse. |
| F14 | Decorative charts entered keyboard navigation. | Recharts accessibility layers are disabled and chart wrappers are hidden from assistive technology; the surrounding summary remains available as text. |
| F15 | Target readiness disagreed with itself. | The Targets view reads the server's readiness, so a placeholder endpoint is no longer labelled "ready" on the same screen where the scan selector disables it. |
| F16 | A failed target load looked like an empty configuration. | The console reports the load failure instead of telling the operator to add targets they already have. |
| F17 | The assistant echoed its prompt and repeated itself. | Explanations are stripped of echoed summary fields and duplicated fragments before they reach the console. |
| F18 | The raw-evidence panel could hang on "Loading evidence…". | The fetch is keyed on the finding rather than the loading flag, which had made the effect tear down its own request. |
| F19 | Live scan events showed raw event-type prefixes. | The progress list shows the message only. |
| F20 | Saving a new target jumped the editor to a different one. | The reload keeps the target that was just saved selected. |
| F21 | A target added in the Targets view was missing from the header scan selector until a page reload. | Save and delete notify the shell, which reloads its target list. |
| F22 | Editing a target stored with `endpoint` showed the new-target default base URL, and saving would have repointed it. | The draft resolves `endpoint` to `base_url` and inherits no endpoint-shaped scaffolding from a new target. |
| F23 | The workspace told an operator with no scans to adjust a filter they had never set. | The empty state distinguishes "no scans yet" from "the filter hides everything". |
| F24 | The scan-target selector was hidden below 640 px while **Run Scan** stayed enabled. | The selector shrinks instead of hiding, so a scan is never started against an invisible target. |
| F25 | API failures were rendered as the raw JSON envelope, escapes and all. | The client shows the server's `error` message; a Docker build failure is readable. |
| F26 | A template deploy always built VulnoraIQ's root image. | A template's `dockerfile` resolves against its build context, as in Compose. |
| F27 | Template deploys could not be given a provider or key, so the bundled agent always fell back to local Ollama. | The template card takes a provider, base URL, model, and API key, and the bundled agent speaks Anthropic as well as the OpenAI-compatible providers. |
| F28 | The burn-down chart had no data source and occupied half the dashboard saying nothing. | `GET /api/trends` aggregates findings across completed scans; before the first scan the chart cards are omitted rather than shown empty. |
| F29 | The console had no component tests. | Vitest and Testing Library cover the rules that decide what an operator sees; CI runs them. |
| F30 | Assessment modules declared no contract, so nothing knew a tool's limits, permissions, or supported targets. | `ToolContract`, enforced at registration and before every run, plus a bounded boundary for external processes. |
| F31 | Removing a hosted agent left its scan target behind, still reading "ready" against a container that no longer existed. | Removal deletes the targets the deploy registered, matching a template's declared ids through the image the container ran. |
