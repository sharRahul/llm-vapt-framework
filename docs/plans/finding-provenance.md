# Plan: make finding provenance a type, not a convention

**Status:** proposed
**Addresses:** [STILL_MISSING.md](STILL_MISSING.md) SM-4, SM-8
**Size:** small–medium — domain type, report generators, one console panel

## Problem

VulnoraIQ's central claim is that a finding is **evidence for human review**, not
a verdict — and specifically that machine-observed fact is distinguishable from
AI-generated interpretation.

Today that claim rests on convention. `Finding` has:

```python
evidence: dict[str, Any]
```

Modules put `confidence`, `limitations`, and `status` in there by habit. Nothing
requires it. A module that omitted them would produce a finding that looks
exactly as well-evidenced as one that did. `docs/guides/findings.md` describes
the distinction correctly as a practice; the type system does not enforce it.

Separately, the raw request/response evidence written to
`VULNORAIQ_EVIDENCE_DIR` is never read back — no API serves it, the console
cannot show it, no report links it. The material a reviewer most wants is the
least reachable.

## Work

### 1. Promote provenance to typed fields

```python
class FindingSource(str, Enum):
    SCANNER_OBSERVED = "scanner_observed"   # a tool observed this directly
    INFERRED = "inferred"                   # derived from observations by a rule
    AI_ASSISTED = "ai_assisted"             # a model contributed to the analysis

class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass(slots=True)
class Finding:
    ...
    source: FindingSource
    confidence: Confidence
    tool: str
    observed_at: datetime
    limitations: str = ""
```

`source` and `tool` are required. Constructing a finding without saying where it
came from should be impossible, not merely discouraged.

Keep `evidence` for the tool-specific payload — request, response, oracle
decision. It stays a dict because its shape genuinely varies; what stops being
optional is the *provenance around it*.

### 2. Nothing AI-assisted enters evidence

The invariant to enforce and test: a finding with
`source == SCANNER_OBSERVED` must have no assistant-generated text in any field.
Assistant output already lives outside the finding, in the API response; this
makes it a property the tests assert rather than a property the code happens to
have.

### 3. Carry it into the reports

Markdown, JSON, and SARIF all gain source, confidence, tool, and limitations.
For SARIF this maps naturally onto `tool.driver` and result properties, so
downstream code-scanning consumers see the same distinction.

### 4. Make evidence reachable

- An evidence index per scan, written alongside the report artefacts.
- `GET /api/scans/{id}/evidence/{finding_id}` under the same authorisation rule
  as artifact download, serving redacted evidence only.
- A collapsed **Raw evidence** section in the finding detail pane.

### 5. Show provenance in the console

The finding detail pane already labels assistant output as advisory. Add a
source badge next to the severity badge — `Observed`, `Inferred`, `AI-assisted` —
so the distinction is visible without reading prose.

## Migration

`Finding` is constructed in the assessment modules and in `core/scanner.py`.
Give `source` and `confidence` no defaults so the compiler finds every call site;
most will be `SCANNER_OBSERVED` / `MEDIUM`. Reports read the new fields with a
fallback for scans persisted before the change.

## Definition of done

- `Finding` cannot be constructed without a source and a confidence.
- A test asserts no `SCANNER_OBSERVED` finding carries assistant-generated text.
- All three report formats carry provenance.
- Raw evidence is reachable from the console under the existing authorisation
  rules.
- `docs/guides/findings.md` describes enforced behaviour rather than practice.
