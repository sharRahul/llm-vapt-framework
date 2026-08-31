# Plan: one Agent Lab user interface

**Status:** proposed
**Addresses:** [TO_BE_FIXED.md](TO_BE_FIXED.md) TBF-1
**Size:** medium — frontend only, no API change

## Problem

Agent Lab has two user interfaces over one API:

- `webui/static/agent-lab/` — a hand-written page served at `/agent-lab`
  (580 lines of vanilla JS).
- `webui/console/src/components/projects/ProjectImporter.tsx` — the console's
  **Projects** tab (674 lines of React).

They are not equivalent. Measured in a browser against the same server:

| Capability | Projects tab | `/agent-lab` |
| --- | --- | --- |
| Inputs / selects | 3 | 20 |
| Local folder import | yes | yes |
| ZIP upload | **no** | yes |
| Git URL import | disabled | yes |
| Mapped folder refresh | **no** | yes |
| Per-project delete | **no** | yes |
| Custom environment variables | **no** | yes |
| Container port control | **no** | yes |
| Explicit "Start authorised scan" | **no** | yes |

Whichever a user finds first decides what they can do. Every Agent Lab change
has to be made twice, and a bug fixed in one has already been missed in the
other.

## Decision

**Keep the React Projects tab. Remove `/agent-lab`.**

The React tab is inside the console, shares its auth, theme, toasts, and API
client, and is the surface the product documentation points at. The standalone
page exists because it predates the console.

## Work

### 1. Reach parity in the Projects tab

Port the capabilities listed above. In priority order, because each is a
capability the API already exposes and no client currently reaches:

1. Git URL import — the control exists but is disabled. Enable it and wire it to
   `POST /api/agent-lab/import/git`.
2. ZIP upload → `POST /api/agent-lab/import/archive`.
3. Mapped folder refresh — mapped projects already come back from
   `GET /api/agent-lab/projects`; show them, marked read-only.
4. Per-project delete → `POST /api/agent-lab/projects/{id}/delete`.
5. Custom environment variables and container port in the deploy form — these
   feed `env` and `ports` on the deploy request.
6. Explicit **Start authorised scan** on a deployment's registered target.

Reuse the deployment result card that already exists in the tab; it is the better
of the two presentations.

### 2. Redirect, then remove

- Serve `/agent-lab` as a redirect to `/#/projects` for one release, so any
  bookmark still lands somewhere useful.
- Then delete `webui/static/agent-lab/`, the `/agent-lab` route in
  `webui/server.py`, and the `static/agent-lab/*` package-data entry in
  `pyproject.toml`.

### 3. Documentation

`docs/guides/agents.md` and `docs/guides/web-console.md` both describe
`/agent-lab`. Point them at the Projects tab.

## Definition of done

- Every row in the table above reads "yes" for the Projects tab.
- A browser run imports by git and by ZIP, sets an environment variable, deploys,
  scans the auto-created target, and deletes the project — without leaving the
  console.
- `/agent-lab` no longer serves a second UI.
- No API change was required. If one turns out to be needed, that is a signal the
  API is missing something the standalone page was working around — record it in
  [STILL_MISSING.md](STILL_MISSING.md) rather than adding a special case.

## Risks

The standalone page is the one currently documented as the Agent Lab entry point,
so a user following the docs will notice the move. The redirect covers the gap,
and the docs change lands in the same release.
