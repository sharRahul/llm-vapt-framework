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
