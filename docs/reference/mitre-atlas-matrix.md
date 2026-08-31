# MITRE ATLAS Matrix for AI Systems

This file is the VulnoraIQ implementation planning register for MITRE ATLAS tactics, techniques, and sub-techniques.

> **Generated snapshot:** this checked-in snapshot is generated from the official MITRE ATLAS v6 source path used by VulnoraIQ: `https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.05.yaml`.

> **Third-party notice:** MITRE ATLAS data is copyright 2021-2026 MITRE and licensed under the Apache License, Version 2.0. VulnoraIQ's use of MITRE ATLAS data does not imply endorsement by MITRE. See `THIRD_PARTY_NOTICES.md`.

> **Mapping rule:** if a tactic or technique cannot be confidently mapped to OWASP or a VulnoraIQ coverage area, it is still listed and marked `Unmapped / map later`. No ATLAS item should disappear just because it is not mapped yet.

> **Drift-control rule:** regenerate this file with `scripts/generate_mitre_atlas_matrix.py` and keep unmapped rows visible until they are deliberately mapped, excluded, or documented for later review.

## Official source alignment

- Site: `https://atlas.mitre.org`
- Data repository: `https://github.com/mitre-atlas/atlas-data`
- Source file: `dist/v6/ATLAS-2026.05.yaml`
- Collection version: `2026.05`
- Modified date: `2026-05-27`
- Tactic count in this snapshot: `16`
- Technique and sub-technique count in this snapshot: `170`
- Generator script: `scripts/generate_mitre_atlas_matrix.py`

## Regeneration command

```bash
vulnoraiq-generate-atlas-matrix \
  --source https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.05.yaml \
  --output docs/reference/mitre-atlas-matrix.md
```

Check for drift:

```bash
vulnoraiq-generate-atlas-matrix \
  --source https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.05.yaml \
  --output docs/reference/mitre-atlas-matrix.md \
  --check
```

## Tactics

| Tactic ID | Tactic | OWASP mapping | VulnoraIQ coverage area | Implementation status |
| --- | --- | --- | --- | --- |
| AML.TA0000 | AI Model Access | Unmapped / map later | Unmapped / map later | Unmapped / map later |
| AML.TA0001 | AI Attack Staging | Unmapped / map later | Unmapped / map later | Unmapped / map later |
| AML.TA0002 | Reconnaissance | Unmapped / map later | Reconnaissance / environment discovery | Candidate mapping / needs validation |
| AML.TA0003 | Resource Development | Unmapped / map later | Supply-chain and capability provenance planning | Candidate mapping / needs validation |
| AML.TA0004 | Initial Access | Unmapped / map later | Configured target exposure / initial access planning | Candidate mapping / needs validation |
| AML.TA0005 | Execution | LLM05 / LLM06 | Output-to-action and agent tool execution governance | Candidate mapping / needs validation |
| AML.TA0006 | Persistence | LLM04 / LLM06 | Model, corpus, memory, and agent persistence review | Candidate mapping / needs validation |
| AML.TA0007 | Defense Evasion | LLM01 / LLM07 | Guardrail bypass and protected-instruction review | Candidate mapping / needs validation |
| AML.TA0008 | Discovery | LLM02 / LLM08 | System, RAG, agent, and model discovery review | Candidate mapping / needs validation |
| AML.TA0009 | Collection | LLM02 / LLM08 | Artifact, data-source, and service collection review | Candidate mapping / needs validation |
| AML.TA0010 | Exfiltration | LLM02 / LLM06 | Restricted information and agent-tool exfiltration review | Candidate mapping / needs validation |
| AML.TA0011 | Impact | LLM05 / LLM10 | Output, integrity, availability, and cost impact review | Candidate mapping / needs validation |
| AML.TA0012 | Privilege Escalation | LLM06 | Agent authority, permissions, and tool escalation review | Candidate mapping / needs validation |
| AML.TA0013 | Credential Access | LLM02 / LLM06 | Credential exposure and agent configuration review | Candidate mapping / needs validation |
| AML.TA0014 | Command and Control | LLM06 | Agent/tool command channel review | Candidate mapping / needs validation |
| AML.TA0015 | Lateral Movement | LLM06 | Agent/tool/data-source movement planning | Candidate mapping / needs validation |

## Techniques and sub-techniques

> The complete generated technique table should be regenerated from `scripts/generate_mitre_atlas_matrix.py` before deeper ATLAS implementation work. Keep regenerated IDs visible, including `Unmapped / map later` rows, so later implementation planning does not silently drop ATLAS coverage.
