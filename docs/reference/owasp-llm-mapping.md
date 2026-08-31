# OWASP LLM Top 10 2025 Mapping

This project is aligned to the OWASP Top 10 for LLM Applications 2025 risk names.

| OWASP ID | Risk | Framework coverage |
|---|---|---|
| LLM01:2025 | Prompt Injection | Direct and indirect prompt-injection probes, prompt leakage detection, RAG context-injection checks |
| LLM02:2025 | Sensitive Information Disclosure | Secret and private-context leakage checks |
| LLM03:2025 | Supply Chain | Dependency, model provenance, dataset lineage, plugin source checks |
| LLM04:2025 | Data and Model Poisoning | Corpus integrity, poisoning simulation readiness, model/data integrity checks |
| LLM05:2025 | Improper Output Handling | Unsafe downstream output review and sandboxing checks |
| LLM06:2025 | Excessive Agency | Tool permissions, agent autonomy, human approval gates |
| LLM07:2025 | System Prompt Leakage | Hidden instruction disclosure checks |
| LLM08:2025 | Vector and Embedding Weaknesses | Retrieval manipulation, vector store, embedding and corpus validation checks |
| LLM09:2025 | Misinformation | Factuality, source quality, uncertainty, and human-review checks |
| LLM10:2025 | Unbounded Consumption | Token, cost, recursion, rate-limit, and DoS-style resource controls |

## Implementation note

The starter runner in `core/test_runner.py` maps each configured module key to the relevant OWASP ID. Concrete module packages can replace those starter checks over time without changing the reporting schema.
