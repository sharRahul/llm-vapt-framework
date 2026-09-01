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
| [Fixed items](FIXED_ITEMS.md) | Delivered defects and work with regression coverage. |
| [Still missing](STILL_MISSING.md) | Gaps between the intended architecture and the implementation. Not bugs — absent boundaries. |

## Proposed work

| Plan | Addresses | Size |
| --- | --- | --- |
| [OIDC / JWT authentication](oidc-jwt-auth.md) | Future identity work; not required for supported deployments | Large |

The scan run lifecycle, finding provenance, tool contract, tool-request
pipeline, and frontend test suite plans are delivered and therefore removed;
what they built is recorded under **Delivered** in
[Still missing](STILL_MISSING.md).

## Suggested order

1. **T2 — assistant verbosity.** The only defect still open, and the one an
   operator meets on every finding. It needs retrieval grounding rather than
   further prompt cleanup.
2. **SM-7 — move scan execution to a worker process.** Deliberately waiting for
   a real concurrency need rather than an anticipated one.

`oidc-jwt-auth.md` stays deferred: token and trusted-proxy modes cover every
deployment VulnoraIQ currently supports.
