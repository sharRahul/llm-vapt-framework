from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from webui import assistant_knowledge, assistant_tools
from webui.assistant_llm import LocalAssistantModel, ModelUnavailable
from webui.payload import dict_field


@dataclass(slots=True)
class AssistantSettings:
    provider: str
    model: str
    temperature: float
    system_prompt: str
    max_tokens: int


class AssistantOrchestrator:
    # IMPORTANT: this MUST stay byte-for-byte in sync with the prompt the model was
    # fine-tuned on (model/prepare_dataset.py :: SYSTEM_PROMPT). Serving a different
    # system prompt than the one baked into training measurably degrades Nora's
    # behaviour (a diverged/shorter prompt was observed to drop eval ~80% -> ~73%).
    DEFAULT_SYSTEM_PROMPT = (
        "You are Nora, the assistant inside the VulnoraIQ platform — a focused helper for authorised "
        "AI/LLM security assessment. Your name is Nora; VulnoraIQ is the product you work in, not your "
        "name. When asked who you are, say you are Nora. You explain vulnerabilities, summarise "
        "evidence, and suggest mitigations.\n"
        "Scope: you only handle AI/LLM security assessment. Politely decline anything outside that "
        "(general coding, writing, unrelated tasks) and redirect to what you can help with.\n"
        "Boundaries: you provide mitigation guidance only and never claim to apply fixes, deploy, or "
        "remediate on a target — that is the human's job. Findings are evidence requiring human review, "
        "not certified assurance.\n"
        "Honesty: ground every answer in the supplied finding evidence and reference material. Never "
        "invent CVE identifiers, CVSS scores, versions, or facts — defer to the provided reference and "
        "lookups. If required information is missing or the request is ambiguous, ask one clarifying "
        "question instead of guessing.\n"
        "Style: be concise and direct. No filler, no preamble, lead with the answer.\n"
        "When assessing a specific finding, structure the answer as — Severity: <level + one-line why>; "
        "Evidence: <what the scan/material shows>; Recommendation: <advisory mitigation steps>; "
        "Note: requires human review before action. For general questions, answer in plain prose and "
        "do not force the template."
    )

    def __init__(self) -> None:
        self.provider = os.getenv("VULNORAIQ_ASSISTANT_PROVIDER", "local").strip().lower()
        self.default_model = os.getenv("VULNORAIQ_ASSISTANT_MODEL", "nora-assistant").strip()
        self.allowed_models = {
            item.strip()
            for item in os.getenv("VULNORAIQ_ASSISTANT_ALLOWED_MODELS", self.default_model).split(",")
            if item.strip()
        }
        self._model = LocalAssistantModel.instance()

    # ── configuration ─────────────────────────────────────────────────────────
    def available_config(self) -> dict[str, Any]:
        status = self._model.status()
        return {
            "provider": self.provider,
            "default_model": self.default_model,
            "allowed_models": sorted(self.allowed_models),
            "default_temperature": 0.2,
            "default_system_prompt": self.DEFAULT_SYSTEM_PROMPT,
            "streaming_supported": False,
            "local_model": status,
            "tools": ["knowledge_base", "web_fetch", "read_docs", "cve_lookup", "cve_reference"],
        }

    # ── chat ────────────────────────────────────────────────────────────────────
    def chat(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        started = time.monotonic()
        settings = self._settings(payload)
        prompt = self._prompt(payload)
        finding = dict_field(payload, "finding")
        content, backend, tools_used = self._respond(settings, prompt, finding)
        return {
            "role": "assistant",
            "content": content,
            "provider": settings.provider,
            "model": settings.model,
            "backend": backend,
            "tools_used": tools_used,
            "temperature": settings.temperature,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "actor": actor,
            "safety_note": "Assistant output is advisory and requires human review before remediation or closure.",
        }

    def explain_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Generate a grounded, human-readable explanation for a single finding."""
        started = time.monotonic()
        summary = self._finding_summary(finding)
        query = " ".join(
            str(finding.get(key, "")) for key in ("title", "category", "owasp", "affected_component")
        ) or str(finding.get("title", ""))
        context = assistant_knowledge.context_block(query, limit=2)
        cve_block = assistant_tools.cve_lookup(finding)
        if cve_block:
            context = context + "\n\n" + cve_block if context else cve_block
        cve_ref = assistant_tools.cve_reference_lookup(summary + " " + query)
        if cve_ref:
            context = context + "\n\n" + cve_ref if context else cve_ref
        if self._model.available():
            messages = [
                {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Explain this security finding in 3-4 sentences for a reviewer: what the weakness is, "
                        "why it matters, and what to check. Do not propose code fixes.\n\n"
                        f"Finding:\n{summary}\n\nReference material:\n{context or '(none)'}"
                    ),
                },
            ]
            try:
                text = self._model.generate(messages, temperature=0.2, max_tokens=320)
                backend = "local-model"
            except ModelUnavailable as exc:
                text, backend = self._templated_explanation(finding, context), f"templated ({exc})"
        else:
            text, backend = self._templated_explanation(finding, context), "templated"
        return {
            "explanation": text,
            "backend": backend,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "safety_note": "Explanation is advisory; a human reviewer must validate the finding.",
        }

    # ── internals ─────────────────────────────────────────────────────────────
    def _respond(self, settings: AssistantSettings, prompt: str, finding: dict[str, Any]) -> tuple[str, str, list[str]]:
        tools_used: list[str] = []
        finding_ctx = self._finding_summary(finding)
        kb = assistant_knowledge.context_block(prompt + " " + finding_ctx, limit=3)
        if kb:
            tools_used.append("knowledge_base")
        fetched = ""
        url = assistant_tools.extract_url(prompt)
        if url:
            fetched = assistant_tools.web_fetch(url)[:4000]
            tools_used.append("web_fetch")
        cve_block = assistant_tools.cve_lookup(finding)
        if cve_block:
            tools_used.append("cve_lookup")
        # Fetch authoritative NVD records for any CVE id named in the prompt, so
        # Nora can answer CVE/CVSS questions from the source instead of guessing.
        cve_ref = assistant_tools.cve_reference_lookup(prompt)
        if cve_ref:
            tools_used.append("cve_reference")

        if not self._model.available():
            return self._templated_chat(prompt, finding_ctx, kb, fetched, cve_block, available=False), "templated", tools_used

        reference = "\n\n".join(
            part for part in (
                kb,
                (f"Fetched from {url}:\n{fetched}" if fetched else ""),
                cve_block,
                cve_ref,
            ) if part
        )
        messages = [
            {"role": "system", "content": settings.system_prompt},
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    f"Finding context:\n{finding_ctx}\n\n"
                    f"Reference material (may be empty):\n{reference or '(none)'}"
                ),
            },
        ]
        try:
            text = self._model.generate(messages, temperature=settings.temperature, max_tokens=settings.max_tokens)
            return text, "local-model", tools_used
        except ModelUnavailable as exc:
            return self._templated_chat(prompt, finding_ctx, kb, fetched, cve_block, available=False, error=str(exc)), "templated", tools_used

    def _settings(self, payload: dict[str, Any]) -> AssistantSettings:
        controls = dict_field(payload, "controls")
        provider = str(controls.get("provider") or self.provider or "local").strip().lower()
        model = str(controls.get("model") or self.default_model).strip()
        if not model:
            raise ValueError("assistant model is required")
        if self.allowed_models and model not in self.allowed_models and provider == self.provider:
            raise ValueError(f"assistant model '{model}' is not allowed by server configuration")
        try:
            temperature = float(controls.get("temperature", 0.2))
        except (TypeError, ValueError) as exc:
            raise ValueError("temperature must be numeric") from exc
        if temperature < 0 or temperature > 1:
            raise ValueError("temperature must be between 0 and 1")
        system_prompt = str(controls.get("system_prompt") or self.DEFAULT_SYSTEM_PROMPT).strip()
        if len(system_prompt) > 2000:
            raise ValueError("system prompt exceeds 2000 characters")
        max_tokens = int(controls.get("max_tokens", 800) or 800)
        if max_tokens < 64 or max_tokens > 4096:
            raise ValueError("max_tokens must be between 64 and 4096")
        return AssistantSettings(provider, model, temperature, system_prompt, max_tokens)

    @staticmethod
    def _prompt(payload: dict[str, Any]) -> str:
        prompt = str(payload.get("message") or payload.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("assistant message is required")
        if len(prompt) > 8000:
            raise ValueError("assistant message exceeds 8000 characters")
        return prompt

    @staticmethod
    def _finding_summary(finding: dict[str, Any]) -> str:
        if not finding:
            return "No finding context supplied."
        parts = [
            f"Title: {finding.get('title', 'unknown')}",
            f"Severity: {finding.get('severity', 'unknown')}",
            f"Status: {finding.get('status', 'unknown')}",
            f"Affected component: {finding.get('affectedPath') or finding.get('affected_component') or 'unknown'}",
        ]
        recommendation = finding.get("remediation") or finding.get("recommendation")
        if isinstance(recommendation, dict):
            parts.append(f"Recommendation: {recommendation.get('summary') or recommendation.get('rationale') or 'review required'}")
        elif recommendation:
            parts.append(f"Recommendation: {recommendation}")
        return "\n".join(str(part)[:1000] for part in parts)

    def _templated_explanation(self, finding: dict[str, Any], context: str) -> str:
        title = finding.get("title", "this finding")
        base = (
            f"{title} is reported as evidence from the authorised scan and requires human review. "
            "Confirm the affected component, review the captured evidence, and assess exposure in the "
            "deployment context before treating it as confirmed."
        )
        if context:
            base += "\n\nRelevant reference:\n" + context.split("\n\n")[0]
        base += "\n\n(The bundled assistant model is not installed; install the 'vulnoraiq[assistant]' extra for richer explanations.)"
        return base

    def _templated_chat(
        self, prompt: str, finding_ctx: str, kb: str, fetched: str, cve_block: str = "", *, available: bool, error: str = ""
    ) -> str:
        lower = prompt.lower()
        if "test" in lower or "validate" in lower:
            guidance = (
                "Validation approach:\n1. Re-run the relevant VulnoraIQ profile.\n2. Confirm the original "
                "evidence no longer reproduces.\n3. Add a regression check.\n4. Record reviewer sign-off."
            )
        elif "risk" in lower or "priority" in lower:
            guidance = "Risk review:\nPrioritise by exposure, trust boundary, data sensitivity, and governance category."
        elif "mitig" in lower or "fix" in lower or "remed" in lower:
            guidance = "Mitigation guidance:\nApply deterministic controls, preserve evidence, and verify with a human reviewer. VulnoraIQ advises only; it does not change the target."
        else:
            guidance = "Analysis guidance:\nReview the evidence, mapped governance context, and current mitigation state before updating the finding."
        extra = ""
        if kb:
            extra += f"\n\nReference material:\n{kb.split(chr(10) + chr(10))[0]}"
        if fetched:
            extra += f"\n\nFetched content (excerpt):\n{fetched[:600]}"
        if cve_block:
            extra += f"\n\n{cve_block}"
        note = (
            "\n\n(The bundled assistant model is not installed, so this is templated guidance. "
            "Install the 'vulnoraiq[assistant]' extra to enable the local model.)"
        )
        if error:
            note = f"\n\n(Local model unavailable: {error}. Showing templated guidance.)"
        return f"{guidance}\n\nFinding context considered:\n{finding_ctx}{extra}{note}"
