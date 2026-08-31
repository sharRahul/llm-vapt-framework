# OWASP to MITRE ATLAS Crosswalk

This document maps VulnoraIQ's OWASP AI security coverage areas to MITRE ATLAS tactics for implementation planning.

> **Status:** source-confirmed planning crosswalk.  
> **Scope:** OWASP LLM 2025, OWASP GenAI Data Security Risks and Mitigations 2026, and OWASP Top 10 for Agentic Applications 2026.  
> **Implementation boundary:** mappings are now source-confirmed at category level, but they remain implementation-planning mappings until VulnoraIQ has active fixtures, evaluators, report evidence, and CI gates for each row.

## Source inputs

| Source | Version/date | Usage in this crosswalk |
| --- | --- | --- |
| `docs/owasp/` | VulnoraIQ OWASP LLM 2025 docs | Existing LLM category implementation specs. |
| `docs/reference/mitre-atlas-matrix.md` | MITRE ATLAS `2026.05` snapshot | ATLAS tactic baseline used by VulnoraIQ. |
| `docs/owasp-documents/OWASP-GenAI-COMPASS-RunBook-1.0.pdf` | Version 1.0, July 2025 | COMPASS/OODA operating model and threat-informed resilience workflow. |
| `docs/owasp-documents/OWASP-GenAI-Data-Security-Risks-and-Mitigations-2026-v1.0.pdf` | Version 1.0, March 2026 | Confirmed `DSGAI01` through `DSGAI21` category names. |
| `docs/owasp-documents/OWASP-Top-10-for-Agentic-Applications-2026-12.6.pdf` | Version 2026, December 2025 | Confirmed `ASI01` through `ASI10` category names. |
| `docs/owasp-documents/OWASP-Top10-for-Agentic-Applications_AIUC-1-Crosswalk-May26.pdf` | Version 1.0, May 2026 | AIUC crosswalk method, Primary/Secondary relevance, and strategic gaps. |
| `docs/owasp-documents/State-of-Agentic-AI-Security-and-Governance-v2.01.pdf` | Version 2.01, June 2026 | Governance maturity, adoption-tier prioritisation, NHI, AI SBOM, and runtime governance context. |

## Mapping labels

| Label | Meaning |
| --- | --- |
| `Primary` | Directly relevant tactic for the risk category. |
| `Secondary` | Common downstream tactic or supporting control relationship. |
| `Contextual` | Relevant only for specific architectures or scenarios. |
| `Unmapped / map later` | Do not force a weak mapping; keep the item visible for later review. |

No OWASP, GenAI, Agentic, or ATLAS item should disappear because the mapping is uncertain.

---

## MITRE ATLAS tactic baseline used by VulnoraIQ

| Tactic ID | Tactic | Planning interpretation in VulnoraIQ |
| --- | --- | --- |
| AML.TA0000 | AI Model Access | Access to model endpoints, model assets, or model-serving surfaces. |
| AML.TA0001 | AI Attack Staging | Preparing prompts, data, tools, accounts, infrastructure, or payloads for AI attacks. |
| AML.TA0002 | Reconnaissance | Discovering AI surfaces, prompts, tools, data stores, policies, or model behaviour. |
| AML.TA0003 | Resource Development | Creating or acquiring datasets, tools, prompts, models, connectors, or infrastructure. |
| AML.TA0004 | Initial Access | Gaining entry into model, RAG, agent, tool, or orchestration surfaces. |
| AML.TA0005 | Execution | Causing model, tool, code, workflow, or agent execution. |
| AML.TA0006 | Persistence | Maintaining influence through memory, corpus poisoning, model/data changes, or agent state. |
| AML.TA0007 | Defense Evasion | Bypassing guardrails, policies, monitoring, or detection. |
| AML.TA0008 | Discovery | Enumerating system instructions, tools, data sources, permissions, identities, or environment. |
| AML.TA0009 | Collection | Gathering sensitive data, context, embeddings, memory, logs, artifacts, or outputs. |
| AML.TA0010 | Exfiltration | Moving restricted data or artifacts out of the controlled boundary. |
| AML.TA0011 | Impact | Integrity, availability, safety, cost, trust, or business-process impact. |
| AML.TA0012 | Privilege Escalation | Gaining broader model/tool/agent permissions or policy bypass. |
| AML.TA0013 | Credential Access | Obtaining secrets, tokens, keys, credentials, or authentication material. |
| AML.TA0014 | Command and Control | Establishing external control channels through tools, agents, callbacks, or generated workflows. |
| AML.TA0015 | Lateral Movement | Moving across tools, agents, data sources, identities, or connected systems. |

---

## OWASP LLM 2025 to MITRE ATLAS mapping

| OWASP ID | Vulnerability | Primary MITRE ATLAS tactics | Secondary/contextual tactics | VulnoraIQ implementation focus |
| --- | --- | --- | --- | --- |
| LLM01:2025 | Prompt Injection | AML.TA0004 Initial Access; AML.TA0005 Execution; AML.TA0007 Defense Evasion | AML.TA0012 Privilege Escalation; AML.TA0010 Exfiltration; AML.TA0011 Impact | Direct, indirect, retrieval-borne, tool-borne, and agent-chain instruction boundary tests. |
| LLM02:2025 | Sensitive Information Disclosure | AML.TA0008 Discovery; AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0013 Credential Access; AML.TA0011 Impact | Restricted marker, secret, PII, credential, report artifact, log, and trace leakage tests. |
| LLM03:2025 | Supply Chain | AML.TA0003 Resource Development; AML.TA0004 Initial Access; AML.TA0006 Persistence | AML.TA0007 Defense Evasion; AML.TA0005 Execution; AML.TA0011 Impact | Model, dependency, dataset, connector, tool, prompt-template, and provider provenance checks. |
| LLM04:2025 | Data and Model Poisoning | AML.TA0006 Persistence; AML.TA0007 Defense Evasion; AML.TA0011 Impact | AML.TA0003 Resource Development; AML.TA0005 Execution | Corpus integrity, source trust, model/version drift, unreviewed data, and poisoning metadata tests. |
| LLM05:2025 | Improper Output Handling | AML.TA0005 Execution; AML.TA0011 Impact | AML.TA0007 Defense Evasion; AML.TA0004 Initial Access | Unsafe output-to-action, schema bypass, downstream consumer, code/HTML/SQL handoff, and report rendering tests. |
| LLM06:2025 | Excessive Agency | AML.TA0005 Execution; AML.TA0012 Privilege Escalation; AML.TA0015 Lateral Movement | AML.TA0013 Credential Access; AML.TA0014 Command and Control; AML.TA0010 Exfiltration; AML.TA0011 Impact | Tool scope, approval, memory write, rollback, audit, budget, and multi-step action governance tests. |
| LLM07:2025 | System Prompt Leakage | AML.TA0008 Discovery; AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0007 Defense Evasion; AML.TA0013 Credential Access | Protected instruction marker, system/developer prompt, policy, chain context, and report artifact leakage tests. |
| LLM08:2025 | Vector and Embedding Weaknesses | AML.TA0008 Discovery; AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0006 Persistence; AML.TA0007 Defense Evasion; AML.TA0011 Impact | RAG source trust, metadata filtering, user/group boundary, poisoned retrieval, embedding collision, and citation-grounding tests. |
| LLM09:2025 | Misinformation | AML.TA0011 Impact; AML.TA0007 Defense Evasion | AML.TA0005 Execution; AML.TA0008 Discovery | Unsupported claim, fabricated citation, uncertainty, high-impact decision, and operator escalation tests. |
| LLM10:2025 | Unbounded Consumption | AML.TA0011 Impact; AML.TA0005 Execution | AML.TA0014 Command and Control; AML.TA0007 Defense Evasion | Token, timeout, retry, loop, fan-out, cost, tool-call, recursion, and agent-loop budget tests. |

---

## OWASP GenAI Data Security Risks 2026 to MITRE ATLAS mapping

The GenAI source document defines GenAI data security across source data, derived data, model artifacts, runtime data, operational exhaust, and agent state/delegation artifacts. The table of contents confirms `DSGAI01` through `DSGAI21`; the narrative text also refers to a `DSGAI01–DSGAI25` taxonomy, so VulnoraIQ tracks that as a source discrepancy until a complete extracted source list is available.

| OWASP ID | GenAI data-security risk | Primary MITRE ATLAS tactics | Secondary/contextual tactics | VulnoraIQ implementation focus |
| --- | --- | --- | --- | --- |
| DSGAI01 | Sensitive Data Leakage | AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0013 Credential Access; AML.TA0011 Impact | Prompt/response/report/log DLP, restricted markers, redaction, and evidence minimisation. |
| DSGAI02 | Agent Identity & Credential Exposure | AML.TA0013 Credential Access; AML.TA0012 Privilege Escalation | AML.TA0005 Execution; AML.TA0015 Lateral Movement | Agent identity, scoped credentials, JIT tokens, credential-bearing trace detection. |
| DSGAI03 | Shadow AI & Unsanctioned Data Flows | AML.TA0002 Reconnaissance; AML.TA0004 Initial Access; AML.TA0009 Collection | AML.TA0010 Exfiltration; AML.TA0011 Impact | AI asset discovery, unknown provider detection, policy gaps, and unsanctioned data-flow evidence. |
| DSGAI04 | Data, Model & Artifact Poisoning | AML.TA0006 Persistence; AML.TA0007 Defense Evasion; AML.TA0011 Impact | AML.TA0003 Resource Development | Corpus/model/artifact integrity, source trust, hash drift, and unreviewed ingestion checks. |
| DSGAI05 | Data Integrity & Validation Failures | AML.TA0011 Impact; AML.TA0007 Defense Evasion | AML.TA0006 Persistence | Schema validation, provenance checks, freshness, source approval, and tamper-evidence. |
| DSGAI06 | Tool, Plugin & Agent Data Exchange Risks | AML.TA0005 Execution; AML.TA0012 Privilege Escalation; AML.TA0015 Lateral Movement | AML.TA0010 Exfiltration; AML.TA0013 Credential Access | Connector scope, tool-call data flow, MCP/plugin manifests, and action trace evidence. |
| DSGAI07 | Data Governance, Lifecycle & Classification for AI Systems | AML.TA0009 Collection; AML.TA0011 Impact | AML.TA0010 Exfiltration; AML.TA0006 Persistence | Classification propagation, retention, deletion, ownership, lineage, and approval evidence. |
| DSGAI08 | Non-Compliance & Regulatory Violations | AML.TA0011 Impact | AML.TA0009 Collection; AML.TA0010 Exfiltration | Regulatory mapping, data residency, retention/legal basis, DSR support, and audit-readiness checks. |
| DSGAI09 | Multimodal Capture & Cross-Channel Data Leakage | AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0011 Impact; AML.TA0013 Credential Access | Image/audio/text data classification, multimodal DLP, biometric/privacy review, and cross-channel leakage checks. |
| DSGAI10 | Synthetic Data, Anonymization & Transformation Pitfalls | AML.TA0010 Exfiltration; AML.TA0011 Impact | AML.TA0009 Collection | Re-identification, membership inference, transformation-risk notes, and synthetic-data lineage tests. |
| DSGAI11 | Cross-Context & Multi-User Conversation Bleed | AML.TA0008 Discovery; AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0006 Persistence; AML.TA0011 Impact | Session isolation, tenant/user boundary fixtures, memory/cache bleed checks. |
| DSGAI12 | Unsafe Natural-Language Data Gateways (LLM-to-SQL/Graph) | AML.TA0005 Execution; AML.TA0012 Privilege Escalation | AML.TA0010 Exfiltration; AML.TA0013 Credential Access; AML.TA0011 Impact | Query intent gating, schema allowlists, least-privilege DB access, and unsafe generated-query simulation. |
| DSGAI13 | Vector Store Platform Data Security | AML.TA0008 Discovery; AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0006 Persistence; AML.TA0007 Defense Evasion | Vector DB authz, tenant index isolation, metadata filtering, snapshot import validation, and embedding leakage checks. |
| DSGAI14 | Excessive Telemetry & Monitoring Leakage | AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0011 Impact | Prompt/tool/output trace minimisation, audit/report redaction, telemetry retention checks. |
| DSGAI15 | Over-Broad Context Windows & Prompt Over-Sharing | AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0007 Defense Evasion; AML.TA0011 Impact | Context minimisation, trust-domain segmentation, prompt assembly review, and over-sharing detection. |
| DSGAI16 | Endpoint & Browser Assistant Overreach | AML.TA0004 Initial Access; AML.TA0005 Execution; AML.TA0012 Privilege Escalation | AML.TA0010 Exfiltration; AML.TA0015 Lateral Movement | Browser/endpoint permission inventory, local context controls, tool-call gating, and user-session boundary checks. |
| DSGAI17 | Data Availability & Resilience Failures in AI Pipelines | AML.TA0011 Impact | AML.TA0007 Defense Evasion; AML.TA0005 Execution | Vector/index availability, stale failover, backup/restore semantic validation, and circuit-breaker evidence. |
| DSGAI18 | Inference & Data Reconstruction | AML.TA0010 Exfiltration; AML.TA0009 Collection | AML.TA0011 Impact | Membership inference, embedding inversion, reconstruction probes, and privacy-preserving evidence. |
| DSGAI19 | Human-in-the-Loop & Labeler Overexposure | AML.TA0009 Collection; AML.TA0010 Exfiltration | AML.TA0011 Impact | Labeler data minimisation, reviewer access boundaries, masking, and high-sensitivity review routing. |
| DSGAI20 | Model Exfiltration & IP Replication | AML.TA0010 Exfiltration; AML.TA0011 Impact | AML.TA0009 Collection; AML.TA0003 Resource Development | Model artifact access controls, extraction probes, watermark/provenance checks, and IP exposure reporting. |
| DSGAI21 | Disinformation & Integrity Attacks via Data Poisoning | AML.TA0006 Persistence; AML.TA0007 Defense Evasion; AML.TA0011 Impact | AML.TA0003 Resource Development | Poisoned data/corpus scenarios, source-trust scoring, misinformation integrity checks, and manual-review routing. |

---

## OWASP Top 10 for Agentic Applications 2026 to MITRE ATLAS mapping

| OWASP ID | Agentic risk | Primary MITRE ATLAS tactics | Secondary/contextual tactics | VulnoraIQ implementation focus |
| --- | --- | --- | --- | --- |
| ASI01 | Agent Goal Hijack | AML.TA0004 Initial Access; AML.TA0005 Execution; AML.TA0007 Defense Evasion | AML.TA0012 Privilege Escalation; AML.TA0011 Impact | Goal/instruction hierarchy, direct/indirect injection, intent gates, and high-impact action approval checks. |
| ASI02 | Tool Misuse and Exploitation | AML.TA0005 Execution; AML.TA0012 Privilege Escalation | AML.TA0010 Exfiltration; AML.TA0011 Impact | Tool scope, argument validation, policy enforcement middleware, semantic tool validation, and usage budgets. |
| ASI03 | Identity and Privilege Abuse | AML.TA0013 Credential Access; AML.TA0012 Privilege Escalation; AML.TA0015 Lateral Movement | AML.TA0005 Execution; AML.TA0010 Exfiltration | Agent identity, non-human identity, delegated credentials, least privilege, JIT access, and attribution. |
| ASI04 | Agentic Supply Chain Vulnerabilities | AML.TA0003 Resource Development; AML.TA0004 Initial Access; AML.TA0006 Persistence | AML.TA0005 Execution; AML.TA0007 Defense Evasion; AML.TA0011 Impact | Tool/provider/framework manifests, AIBOM/SBOM/ML-BOM linkage, version drift, connector provenance, and prompt/template supply chain. |
| ASI05 | Unexpected Code Execution (RCE) | AML.TA0005 Execution; AML.TA0011 Impact | AML.TA0004 Initial Access; AML.TA0012 Privilege Escalation | Code/tool sandboxing, generated-code execution gates, interpreter isolation, file-write guards, and RCE simulation fixtures. |
| ASI06 | Memory & Context Poisoning | AML.TA0006 Persistence; AML.TA0007 Defense Evasion; AML.TA0011 Impact | AML.TA0009 Collection; AML.TA0010 Exfiltration | Memory integrity, context isolation, poisoned state, long-term memory review, and traceable memory writes. |
| ASI07 | Insecure Inter-Agent Communication | AML.TA0014 Command and Control; AML.TA0015 Lateral Movement; AML.TA0012 Privilege Escalation | AML.TA0008 Discovery; AML.TA0010 Exfiltration | Agent identity, mutual authentication, signed agent cards/manifests, protocol validation, A2A/MCP trust boundaries. |
| ASI08 | Cascading Failures | AML.TA0011 Impact; AML.TA0005 Execution | AML.TA0014 Command and Control; AML.TA0015 Lateral Movement | Circuit breakers, blast-radius limits, planner/executor isolation, cascade simulations, and propagation controls. |
| ASI09 | Human-Agent Trust Exploitation | AML.TA0007 Defense Evasion; AML.TA0011 Impact | AML.TA0005 Execution; AML.TA0009 Collection | Human approval UX, deceptive output, overtrust prompts, high-risk output flagging, and operator review evidence. |
| ASI10 | Rogue Agents | AML.TA0014 Command and Control; AML.TA0015 Lateral Movement; AML.TA0011 Impact | AML.TA0006 Persistence; AML.TA0012 Privilege Escalation | Agent registration, discovery, kill switch, containment, runtime monitoring, behavioural drift, and rogue-agent quarantine. |

---

## AIUC-1 crosswalk implications

The AIUC-1 crosswalk states that mappings are relevance mappings rather than sufficiency proofs. VulnoraIQ should follow the same rule: a Primary mapping indicates direct relevance to the core risk, not complete mitigation.

Important implementation implications:

| Crosswalk theme | VulnoraIQ implementation implication |
| --- | --- |
| Agent identity and inter-agent communication | Add per-agent identity fields, signed manifests, mutual auth, and trusted discovery checks for ASI03/ASI07/ASI10. |
| Architectural containment and runtime monitoring | Add circuit breakers, blast-radius limits, runtime malicious-activity monitoring, and entitlement controls for ASI01/ASI05/ASI08/ASI10. |
| Supply-chain attestation and schema controls | Add tool manifests, prompt/version control, AIBOM/SBOM/ML-BOM references, code signing, and agent-model boundary schemas for ASI01/ASI02/ASI04/ASI06/ASI08. |
| Human gates and feedback | Add pause/stop/redirect controls, high-risk output flags, approval evidence, and human review routing for ASI01/ASI08/ASI09. |

---

## Required crosswalk fields for implementation

When this mapping moves from planning to code, each implemented check should carry:

- `owasp_family`: `LLM`, `GenAI Data`, or `Agentic`
- `owasp_id`: e.g. `LLM01`, `DSGAI01`, or `ASI01`
- `owasp_name`
- `mitre_atlas_tactics`: list of `AML.TAxxxx`
- `mitre_atlas_techniques`: list of confirmed technique IDs, once regenerated from ATLAS data
- `mapping_confidence`: `high`, `medium`, `low`
- `mapping_status`: `candidate`, `validated`, `rejected`, `map_later`
- `evidence_surface`: prompt, response, retrieval trace, tool trace, memory trace, model metadata, provider metadata, report artifact, audit log
- `manual_review_required`: boolean

## Immediate implementation backlog

1. Add `config/owasp_mitre_atlas_crosswalk.yaml` as the machine-readable source for this file.
2. Add validator checks that every active OWASP oracle has at least one candidate ATLAS tactic.
3. Add report fields for ATLAS tactic and technique mappings.
4. Add dashboard coverage by OWASP family, OWASP category, and ATLAS tactic.
5. Add GenAI scenario manifests for all confirmed `DSGAI01–DSGAI21` categories.
6. Add Agentic scenario manifests for all confirmed `ASI01–ASI10` categories.
7. Add source-discrepancy tracking for the GenAI document's `DSGAI01–DSGAI25` narrative vs `DSGAI01–DSGAI21` table-of-contents extraction.
8. Add CI guard to fail if OWASP docs, crosswalk YAML, and report schema drift.

## Claim rule

Do not claim full MITRE ATLAS coverage until:

1. all ATLAS techniques and sub-techniques are regenerated from the official source,
2. each technique is mapped, deliberately unmapped, or marked for later review,
3. active VulnoraIQ checks produce structured evidence for each validated mapping,
4. false-positive / false-negative limitations are documented, and
5. generated reports distinguish candidate mappings from validated detections.