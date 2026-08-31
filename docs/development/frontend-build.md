# Frontend build

The browser console is a React 18 + TypeScript app under `webui/console/`, built
by Vite into `webui/static/console/`. The server serves that built output; it
never runs Vite.

## Why the build output is committed

`webui/static/console/` is tracked. That is deliberate: a source checkout, a
release package, and the Docker image all serve the console without needing
Node. Node is a development requirement only.

The consequence is that **a console change is not complete until you rebuild and
commit the output.** Source and built assets must land in the same change.

## Building

```bash
cd webui/console
npm ci
npm run build
```

`npm run build` is `tsc --noEmit && vite build`, so it typechecks first and fails
before producing assets if the types are wrong. Use `npm run typecheck` alone for
a faster check, and `npm run dev` for a hot-reloading dev server.

Vite fingerprints its output (`index-<hash>.js`), so a rebuild replaces the
previous bundle with a differently named file. Stage the deletion of the old
asset along with the new one:

```bash
git add -A webui/static/console/
```

## What gets produced

| Path | Contents |
| --- | --- |
| `webui/static/console/index.html` | Console entry point, served at `/`. |
| `webui/static/console/assets/index-<hash>.js` | Application bundle. |
| `webui/static/console/assets/charts-<hash>.js` | Charting library chunk. |
| `webui/static/console/assets/index-<hash>.css` | Compiled styles. |
| `webui/static/console/assets/*.woff2` | Self-hosted font subsets. |

Fonts are bundled rather than fetched from a CDN, so the console works offline
and stays within its Content-Security-Policy.

Agent Lab is part of the React console’s **Projects** view and is included in the Vite build. The former `/agent-lab` page redirects to `/#/projects`.

## Packaging

`pyproject.toml` lists `webui/static/console/*` and `webui/static/console/assets/*` as package data, so the built console ships in the Python distribution and the release package.

## CI

The console build runs on the Python 3.12 matrix leg only, to avoid repeating
Node and browser setup across every Python version. It runs before the hosted
browser flow, which needs the built assets to exist.

## Related

- [Development setup](development-setup.md)
- [Testing](testing.md)
- [Web console guide](../guides/web-console.md)
