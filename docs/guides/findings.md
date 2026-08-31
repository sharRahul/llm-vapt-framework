# Findings and evidence

A VulnoraIQ finding is **evidence for a human reviewer**, not a verdict. This
page explains what a finding contains, where each part comes from, and how to
tell machine-observed fact from AI-generated interpretation.

## The chain

```text
assessment payload
  → target response captured verbatim
    → oracle/evaluator decision           ← deterministic, this is the evidence
      → finding (severity, mapping, recommendation)
        → policy evaluation
          → report artefacts
```

Everything up to the finding is produced by deterministic code. Nothing in that
chain is written by a language model.

## What a finding carries

| Field | Meaning |
| --- | --- |
| `title` | Short description of the weakness. |
| `description` | What was checked and what was observed. |
| `severity` | `critical`, `high`, `medium`, `low`, or `info`. |
| `owasp_id` | OWASP LLM Top 10 (2025) category, or `AITG` for AI Testing Guide coverage. |
| `mitre_atlas` | Mapped MITRE ATLAS technique identifiers. |
| `affected_component` | The part of the target the finding concerns. |
| `source` | `scanner_observed`, `inferred`, or `ai_assisted`; the console labels it next to severity. |
| `tool` | The scanner or evaluator that produced the finding. |
| `observed_at` | UTC timestamp for the underlying observation. |
| `confidence` | Structured `low`, `medium`, or `high` confidence. |
| `limitations` | What the evidence does not establish. |
| `evidence` | Structured request, response, and oracle-decision material specific to the tool. |
| `recommendation` | Advisory remediation guidance. |
| `score` | Numeric risk score where the module produces one. |

Request and response evidence is redacted before storage: header names matching
`token`, `secret`, `key`, `password`, or `authorization`, and bearer-token or
`sk-...` values, are replaced.

## Confidence and limitations

Confidence and limitations are required finding fields rather than conventions
inside the flexible evidence payload. Synthetic fixture coverage is labelled as such: it proves the
check runs, not that a real system is safe. A run against a fixture target and a
run against a real authorised system are different claims, and the evidence says
which one you have.

## Where AI fits — and where it does not

The optional in-app assistant ("Nora") can explain a finding in plain language
and suggest mitigations. It is strictly downstream of the evidence:

- Assistant output is grounded in the finding's own evidence plus bundled
  reference material, and never replaces it.
- Every assistant response carries a `safety_note` marking it advisory and
  requiring human review.
- The assistant is explicitly instructed not to invent CVE identifiers, CVSS
  scores, or versions, and to defer to lookups and supplied references.
- The assistant never claims to have applied a fix, and cannot: it has no path to
  the target or to command execution.
- Assistant output is never written into a finding's `evidence`.

If the assistant is not installed, explanations fall back to deterministic
templated guidance and nothing else changes.

**Never present an assistant explanation as scanner-confirmed evidence.**

## CVE lookups

The CVE panel queries public vulnerability sources for records matching a
finding. Matches are candidate context for a reviewer, not a confirmation that
the target is affected by that CVE. Confirm applicability against the target's
actual component versions.

## Triage

Each finding carries a remediation state you can update from the console:

| Status | Meaning |
| --- | --- |
| `open` | Not yet reviewed. |
| `triaged` | Reviewed, awaiting action. |
| `in_progress` | Remediation under way. |
| `accepted_risk` | Accepted; a reason is required. |
| `false_positive` | Not a real issue; a reason is required. |
| `fixed` | Remediated. |
| `wont_fix` | Deliberately not remediating. |

Every change is recorded with the actor, timestamp, and previous state, and is
retrievable from the finding's history. Only the remediation fields are
writable — a client cannot inject arbitrary keys into a finding.

## Report artefacts

Each completed scan produces:

| Artefact | Use |
| --- | --- |
| `scan-report.md` | Human-readable report. |
| `scan-report.json` | Structured data for downstream tooling. |
| `scan-report.sarif` | SARIF for code-scanning integrations. |
| `dashboard.md` / `dashboard.html` | Summary dashboards. |

They are written under the configured output root and downloaded through the
API, which serves only the artefacts a job actually produced.

## Related

- [Assessment assurance](../security/assurance.md) — what these findings do and do not claim.
- [Assessments guide](assessments.md)
- [OWASP LLM mapping](../reference/owasp-llm-mapping.md)
