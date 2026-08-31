# MITRE ATLAS Mapping

MITRE ATLAS provides a useful threat-informed vocabulary for adversarial behaviour targeting AI-enabled systems. This project keeps a `mitre_atlas` field on findings so security teams can map AI VAPT results into threat-modelling, red-team, and governance workflows.

## Initial mapping approach

| Assessment area | OWASP coverage | ATLAS usage |
|---|---|---|
| Prompt injection | LLM01, LLM07 | Direct and indirect prompt manipulation techniques |
| RAG poisoning | LLM04, LLM08 | Data poisoning, retrieval manipulation, and knowledge-base compromise techniques |
| Agent/tool abuse | LLM06 | Tool misuse, privilege-boundary, and autonomous action techniques |
| Sensitive leakage | LLM02, LLM07 | Collection and exfiltration-style AI system behaviours |
| Resource exhaustion | LLM10 | Cost, token, and availability impact behaviours |

## Implementation note

Technique identifiers come from `config/mitre_atlas_mapping.yaml`, which is refreshed from the
official ATLAS data by `scripts/refresh_mitre_atlas.py`. A finding carries only technique IDs that
exist in that mapping; categories with no technique yet appear as `Unmapped / map later` in the
generated matrix rather than as a placeholder identifier inside a finding.
