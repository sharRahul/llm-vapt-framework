# Plans

The only place in this repository that holds planning documents.

A plan belongs here when it describes work that is intended, agreed, and not yet
done. Once a plan is delivered or abandoned it is removed — completed and
historical plans are not kept in the repository. Implementation status lives in
the code, the tests, and `CHANGELOG.md`.

## Findings

| Document | What it is |
| --- | --- |
| [To be fixed](TO_BE_FIXED.md) | Defects found by driving the console end to end in a browser. Records what was fixed in that pass and what remains. |
| [Still missing](STILL_MISSING.md) | Gaps between the intended architecture and the implementation. Not bugs — absent boundaries. |

## Proposed work

| Plan | Addresses | Size |
| --- | --- | --- |
| [One Agent Lab user interface](agent-lab-ui-consolidation.md) | TBF-1 — two non-equivalent UIs over one API | Medium |
| [Agent Lab end-to-end coverage](agent-lab-e2e-coverage.md) | TBF-6 — the flagship flow has no success-path test | Small |
| [Scan run lifecycle](scan-run-lifecycle.md) | SM-1, SM-2, SM-7 — no state machine, no cancellation, no restart recovery | Medium |
| [Finding provenance](finding-provenance.md) | SM-4, SM-8 — provenance is convention, evidence is unreachable | Small–medium |
| [OIDC / JWT authentication](oidc-jwt-auth.md) | Future identity work; not required for supported deployments | Large |

## Suggested order

1. **Agent Lab end-to-end coverage** — smallest, and it protects the area with
   the worst regression history before anything else changes there.
2. **One Agent Lab user interface** — removes a duplicated surface; safer once
   the coverage above exists.
3. **Finding provenance** — the product's central claim, currently unenforced.
4. **Scan run lifecycle** — largest, and the prerequisite for cancellation,
   approval gates, and resumable runs.

`oidc-jwt-auth.md` stays deferred: token and trusted-proxy modes cover every
deployment VulnoraIQ currently supports.
