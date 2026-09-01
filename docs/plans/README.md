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

The scan run lifecycle and finding provenance plans are delivered and therefore
removed; what they built is recorded under **Delivered** in
[Still missing](STILL_MISSING.md).

## Suggested order

1. **SM-3 — a tool/scanner contract.** The remaining High item, and the
   prerequisite for SM-5.
2. **SM-10 — a frontend test suite.** Small, and what makes console changes safe
   to review.

`oidc-jwt-auth.md` stays deferred: token and trusted-proxy modes cover every
deployment VulnoraIQ currently supports.
