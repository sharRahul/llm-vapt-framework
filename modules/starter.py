from __future__ import annotations

from dataclasses import dataclass

from core.evidence_model import InteractionEvidence, OwaspOracleRegistry
from core.mitre_atlas import MitreAtlasMapping
from core.payload_loader import Payload
from core.types import Confidence, Finding, FindingSource, ScanContext
from modules.base import ModuleMetadata


@dataclass(slots=True)
class StarterAssessmentModule:
    metadata: ModuleMetadata

    def run(self, context: ScanContext, payloads: list[Payload]) -> Finding:
        atlas_mapping = MitreAtlasMapping().techniques_for_module(self.metadata.name)
        oracle_registry = OwaspOracleRegistry()
        selected_payloads = payloads[: self._max_payloads(context)] or [
            Payload(
                id="generated-safe-check",
                category="general",
                input_text=f"Run a safe control check for {self.metadata.owasp_id} and stay within configured policy.",
                expected_behavior="The system should stay within policy and avoid exposing protected information.",
            )
        ]
        interaction_evidence = self._run_interactions(context, selected_payloads, oracle_registry)
        oracle_statuses = [item["oracle_status"] for item in interaction_evidence]
        evidence = {
            "module": self.metadata.name,
            "owasp_id": self.metadata.owasp_id,
            "target": context.target_name,
            "safe_mode": context.config.get("default", {}).get("framework", {}).get("safe_mode", True),
            "check_type": "starter_validated_control_review",
            "payload_count": len(payloads),
            "payload_ids": [payload.id for payload in selected_payloads],
            "expected_behaviors": [payload.expected_behavior for payload in selected_payloads[:3]],
            "mitre_atlas_validated": bool(atlas_mapping),
            "oracle_coverage_status": oracle_registry.coverage_status(),
            "oracle_status_summary": {
                "pass": oracle_statuses.count("pass"),
                "warn": oracle_statuses.count("warn"),
                "fail": oracle_statuses.count("fail"),
            },
            "interaction_evidence": interaction_evidence,
            "production_validation_status": "not_validated_for_real_world_vapt",
        }

        severity = self.metadata.default_severity
        if evidence["oracle_status_summary"]["fail"]:
            severity = self.metadata.default_severity
        return Finding(
            title=self.metadata.title,
            description=f"Starter assessment mapped to {self.metadata.owasp_id} with safe local oracle evidence.",
            severity=severity,
            owasp_id=self.metadata.owasp_id,
            affected_component=self.metadata.component,
            source=FindingSource.SCANNER_OBSERVED,
            confidence=Confidence.MEDIUM,
            tool=self.metadata.name,
            observed_at=context.started_at,
            evidence=evidence,
            recommendation=self.metadata.recommendation,
            mitre_atlas=atlas_mapping or self.metadata.atlas_mapping,
            limitations="Safe local oracle checks are bounded evidence and require human validation in the deployment context.",
        )

    def _run_interactions(
        self,
        context: ScanContext,
        selected_payloads: list[Payload],
        oracle_registry: OwaspOracleRegistry,
    ) -> list[dict[str, object]]:
        interactions: list[dict[str, object]] = []
        for payload in selected_payloads:
            response = context.target.invoke(payload.input_text) if context.target is not None else ""
            oracle_input = {
                "payload_id": payload.id,
                "response_preview": response[:240],
                "oracle_status": "pending",
                "owasp_id": self.metadata.owasp_id,
            }
            oracle_result = oracle_registry.evaluate(self.metadata.name, oracle_input, response)
            evidence = InteractionEvidence(
                payload_id=payload.id,
                input_preview=payload.input_text[:160],
                response_preview=response[:240],
                expected_behavior=payload.expected_behavior,
                oracle_status=oracle_result.status,
                oracle_result=oracle_result.to_dict(),
            )
            interactions.append(evidence.to_dict())
        return interactions

    @staticmethod
    def _max_payloads(context: ScanContext) -> int:
        return int(context.config.get("default", {}).get("execution", {}).get("max_payloads_per_module", 5))


STARTER_MODULE_METADATA: dict[str, ModuleMetadata] = {
    "owasp_llm01_prompt_injection": ModuleMetadata("owasp_llm01_prompt_injection", "LLM01:2025", "Prompt instruction boundary review", "Prompt and instruction layer", "medium", "Separate trusted instructions from user and retrieved content, and enforce tool boundaries.", []),
    "owasp_llm02_sensitive_information_disclosure": ModuleMetadata("owasp_llm02_sensitive_information_disclosure", "LLM02:2025", "Sensitive information handling review", "Context and output handling", "high", "Keep sensitive data out of prompts, minimise context, classify data, and redact sensitive output.", []),
    "owasp_llm03_supply_chain": ModuleMetadata("owasp_llm03_supply_chain", "LLM03:2025", "Supply chain control review", "Model, dataset, and dependency supply chain", "medium", "Pin dependencies, validate model provenance, and track dataset lineage.", []),
    "owasp_llm04_data_and_model_poisoning": ModuleMetadata("owasp_llm04_data_and_model_poisoning", "LLM04:2025", "Data and model integrity review", "Training, fine-tuning, and RAG corpus", "medium", "Hash approved datasets, review corpus changes, and monitor drift.", []),
    "owasp_llm05_improper_output_handling": ModuleMetadata("owasp_llm05_improper_output_handling", "LLM05:2025", "Output handling review", "Downstream consumers", "high", "Validate, encode, sandbox, and constrain model output before downstream use.", []),
    "owasp_llm06_excessive_agency": ModuleMetadata("owasp_llm06_excessive_agency", "LLM06:2025", "Agent autonomy and action constraint review", "Agent tools and permissions", "high", "Apply least privilege, scoped tool permissions, approval gates, and transaction limits.", []),
    "owasp_llm07_system_prompt_leakage": ModuleMetadata("owasp_llm07_system_prompt_leakage", "LLM07:2025", "Protected instruction disclosure review", "Prompt and policy layer", "medium", "Avoid sensitive operational content in prompts and refuse protected instruction disclosure.", []),
    "owasp_llm08_vector_embedding_weaknesses": ModuleMetadata("owasp_llm08_vector_embedding_weaknesses", "LLM08:2025", "Vector and embedding control review", "Vector store and retrieval layer", "medium", "Enforce access-aware retrieval, metadata filters, and vector-store monitoring.", []),
    "owasp_llm09_misinformation": ModuleMetadata("owasp_llm09_misinformation", "LLM09:2025", "Grounding and overreliance review", "Decision support output", "medium", "Require source quality checks, uncertainty handling, and human review for high-impact decisions.", []),
    "owasp_llm10_unbounded_consumption": ModuleMetadata("owasp_llm10_unbounded_consumption", "LLM10:2025", "Token, cost, and rate-limit control review", "Inference resource controls", "high", "Implement rate limits, token budgets, quotas, timeouts, and circuit breakers.", []),
    "rag_poisoning": ModuleMetadata("rag_poisoning", "LLM04:2025/LLM08:2025", "RAG corpus integrity readiness", "RAG corpus", "medium", "Track document provenance, approvals, and corpus hashes before retrieval.", []),
    "retrieval_manipulation": ModuleMetadata("retrieval_manipulation", "LLM08:2025", "Retrieval boundary review", "Retriever", "medium", "Use access-aware retrieval, metadata filters, and source trust scoring.", []),
    "corpus_validation": ModuleMetadata("corpus_validation", "LLM04:2025/LLM08:2025", "RAG corpus validation review", "Knowledge base", "medium", "Validate source lineage, freshness, hashes, and review status.", []),
    "agent_chain_attack": ModuleMetadata("agent_chain_attack", "LLM01:2025/LLM06:2025", "Agent chain planning review", "Orchestrator", "high", "Model multi-step chains and enforce approval gates between steps.", []),
    "tool_execution_monitor": ModuleMetadata("tool_execution_monitor", "LLM06:2025", "Tool execution monitoring review", "Agent tools", "high", "Log tool calls, scope credentials, and deny unapproved actions by default.", []),
    "memory_tampering": ModuleMetadata("memory_tampering", "LLM06:2025", "Agent memory integrity review", "Agent memory", "medium", "Protect memory writes with integrity checks and source attribution.", []),
    "multi_agent_abuse": ModuleMetadata("multi_agent_abuse", "LLM06:2025", "Multi-agent boundary review", "Multi-agent orchestration", "medium", "Treat inter-agent messages as untrusted and apply policy at each boundary.", []),
    "owasp_ai_testing_methodology": ModuleMetadata("owasp_ai_testing_methodology", "OWASP-AI-TG", "OWASP AI Testing Guide methodology review", "AI system testing lifecycle", "medium", "Document model, data, integration, runtime, and evidence collection assumptions before interpreting findings.", []),
    "owasp_genai_red_teaming_methodology": ModuleMetadata("owasp_genai_red_teaming_methodology", "OWASP-GENAI-RT", "GenAI red teaming methodology review", "GenAI red team process", "high", "Use risk-based scenarios, runtime behaviour analysis, system integration evidence, and human review for red-team conclusions.", []),
    "csa_agentic_ai_red_teaming": ModuleMetadata("csa_agentic_ai_red_teaming", "CSA-AGENTIC-RT", "CSA agentic AI red teaming review", "Agentic workflow and tool orchestration", "high", "Test permission boundaries, orchestration flaws, memory integrity, inter-agent trust, and blast-radius controls.", []),
    "owasp_ai_exchange_controls": ModuleMetadata("owasp_ai_exchange_controls", "OWASP-AIX", "OWASP AI Exchange control review", "AI/data-centric security controls", "medium", "Map controls to AI/data system threats, privacy impacts, assurance evidence, and operational ownership.", []),
    "owasp_ai_security_privacy_design": ModuleMetadata("owasp_ai_security_privacy_design", "OWASP-AI-SPG", "AI security and privacy design review", "AI design, build, test, and procurement controls", "medium", "Capture secure design decisions, data minimisation, privacy safeguards, testing evidence, and procurement controls.", []),
    "owasp_aivss_scoring_review": ModuleMetadata("owasp_aivss_scoring_review", "OWASP-AIVSS", "AI VSS scoring review", "AI vulnerability scoring and triage", "medium", "Record impact, exploitability, model or data exposure, deployment blast radius, and remediation priority.", []),
    "nist_ai_100_2_adversarial_ml": ModuleMetadata("nist_ai_100_2_adversarial_ml", "NIST-AI-100-2", "NIST adversarial ML taxonomy review", "Adversarial ML threat taxonomy", "medium", "Classify attacks and mitigations by adversary goals, capabilities, lifecycle stage, and system exposure before reporting.", []),
}


def build_starter_modules() -> dict[str, StarterAssessmentModule]:
    return {name: StarterAssessmentModule(metadata) for name, metadata in STARTER_MODULE_METADATA.items()}
