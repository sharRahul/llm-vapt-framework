# OWASP AI Testing Guide integration

VulnoraIQ includes a controlled, safe OWASP AI Testing Guide foundation path for authorised local or internal AI-system assessment.

The current implementation is not only a documentation mapping: it includes runnable profiles, safe payloads, target adapters, Docker mock-agent targets, WebUI profile selection, and report/evidence output.

## Current implemented scope

| Source area | VulnoraIQ implementation | Current purpose |
| --- | --- | --- |
| OWASP AI Testing Guide | `ai_testing_guide_foundation`, `owasp_ai_testing_methodology` | Methodology, evidence, runtime, and reporting checks. |
| OWASP GenAI Red Teaming Guide | `owasp_genai_red_teaming_methodology` | Risk-based GenAI red-team planning and behaviour review. |
| CSA Agentic AI Red Teaming Guide | `csa_agentic_ai_red_teaming` | Agent, tool, memory, and permission review. |
| OWASP AI Exchange | `owasp_ai_exchange_controls` | AI/data-centric control mapping and ownership. |
| OWASP AI Security and Privacy Guide | `owasp_ai_security_privacy_design` | Secure design, privacy, procurement, and testing prompts. |
| OWASP Top 10 for LLM | Existing `owasp_llm01` to `owasp_llm10` modules | LLM application risk checks. |
| OWASP AI VSS | `owasp_aivss_scoring_review` | Scoring, triage, and evidence quality review. |
| NIST AI 100-2 E2025 | `nist_ai_100_2_adversarial_ml` | Adversarial ML taxonomy alignment. |

## Runnable profiles

Current WebUI/CLI-selectable profiles include:

- `ai_testing_guide_foundation`
- `test_owasp_ai_testing_methodology`
- `test_owasp_genai_red_teaming_methodology`
- `test_csa_agentic_ai_red_teaming`
- `test_owasp_ai_exchange_controls`
- `test_owasp_ai_security_privacy_design`
- `test_owasp_aivss_scoring_review`
- `test_nist_ai_100_2_adversarial_ml`

These profiles use `payloads/ai_testing_guide.yaml`. The payloads ask for defensive methodology, evidence, control, and triage responses. They do not ask the target to perform unauthorised actions.

## Docker-first AI Testing Guide flow

```bash
docker compose build
docker compose up -d
docker compose exec vulnoraiq-web vulnoraiq targets validate --target local_mock_agent
docker compose exec vulnoraiq-web vulnoraiq scan --target local_mock_agent --profile ai_testing_guide_foundation --authorised
```

## Current local AI-agent target contracts

Docker-first targets live in `config/targets.docker.yaml` and use `http://local-mock-agent:9090` inside the private Docker network.

Host-native development targets live in `config/targets.yaml` and currently use loopback endpoints on port `9090`.

| Target | Contract | Default endpoint shape |
| --- | --- | --- |
| `local_mock_agent` | Chat-completions / HTTP JSON mock agent | `/v1/chat/completions` or `/agent` depending on config file. |
| `local_rag_app` | RAG query | `/rag/query` |
| `local_mock_ollama` | Ollama generate | `/api/generate` |
| `local_webhook_agent` / `owasp_lab_webhook_json` | Webhook JSON | `/webhook` |
| `local_agent_tool_loop` / `agent_tool_loop` | Dry-run tool-loop | `/agent/tool-loop` |

## Generic JSON contract

VulnoraIQ sends a prompt-bearing JSON body and accepts either plain text or JSON with a configured response extraction path such as `response`, `output`, `answer`, or `choices.0.message.content`.

Example request shape:

```json
{
  "prompt": "assessment prompt",
  "input": "assessment prompt"
}
```

## WebUI flow

1. Start the Docker lab or a host-native authorised local target.
2. Open the WebUI.
3. Select and validate the target.
4. Select `OWASP AI Testing Guide foundation` or an individual AI Testing Guide profile.
5. Confirm authorisation.
6. Start the assessment.
7. Review findings, evidence previews, recent jobs, and downloadable reports.

## Full AITG roadmap

The current foundation integration is complete for the controlled methodology-harness scope. The full 32-test OWASP AI Testing Guide implementation remains tracked in [OWASP LLM mapping](owasp-llm-mapping.md).

## Safety and assurance boundary

- Use these profiles only for systems you own or are explicitly authorised to assess.
- These checks provide methodology and evidence-harness support; they are not independent certification.
- Findings require human review before assurance, remediation, or external reporting use.
- If a target is not running or response extraction fails, VulnoraIQ reports the failure instead of silently falling back to the demo target.

## Full AITG profile

The `owasp-aitg-full` profile executes the canonical 32-entry manifest at `benchmarks/fixtures/aitg/aitg_32_manifest.yaml`. The default execution path uses safe synthetic fixtures and records coverage evidence, mappings, confidence, and limitations for every manifest entry. Real target execution remains bounded by explicit authorisation and target allow-list controls.
