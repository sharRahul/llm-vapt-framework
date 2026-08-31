from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.05.yaml"
DEFAULT_OUTPUT = Path("docs/reference/mitre-atlas-matrix.md")
UNMAPPED_LABEL = "Unmapped / map later"

OWASP_HINTS = {
    "prompt": "LLM01 Prompt Injection / LLM07 System Prompt Leakage",
    "jailbreak": "LLM01 Prompt Injection",
    "system prompt": "LLM07 System Prompt Leakage",
    "data leakage": "LLM02 Sensitive Information Disclosure",
    "credential": "LLM02 Sensitive Information Disclosure",
    "sensitive": "LLM02 Sensitive Information Disclosure",
    "supply chain": "LLM03 Supply Chain",
    "poison": "LLM04 Data and Model Poisoning / LLM08 Vector and Embedding Weaknesses",
    "rag": "LLM08 Vector and Embedding Weaknesses / LLM04 Data and Model Poisoning",
    "retrieval": "LLM08 Vector and Embedding Weaknesses",
    "tool": "LLM06 Excessive Agency",
    "agent": "LLM06 Excessive Agency",
    "output": "LLM05 Improper Output Handling / LLM09 Misinformation",
    "citation": "LLM09 Misinformation / LLM05 Improper Output Handling",
    "hallucination": "LLM09 Misinformation",
    "cost": "LLM10 Unbounded Consumption",
    "denial": "LLM10 Unbounded Consumption",
    "spam": "LLM10 Unbounded Consumption",
}

COVERAGE_HINTS = {
    "prompt": "Prompt boundary and protected-instruction checks",
    "jailbreak": "Prompt boundary and refusal-quality checks",
    "system prompt": "Protected instruction disclosure checks",
    "data leakage": "Restricted information disclosure checks",
    "credential": "Restricted information handling checks",
    "supply chain": "AI artifact provenance and supply-chain checks",
    "poison": "Corpus/model integrity and provenance checks",
    "rag": "RAG corpus, source trust, and retrieval-boundary checks",
    "retrieval": "Retrieval source trust and access-boundary checks",
    "tool": "Agent tool allowlist and approval checks",
    "agent": "Agent runtime, memory, tool, and approval governance checks",
    "output": "Output validation and downstream handoff checks",
    "citation": "Citation and source-to-claim traceability checks",
    "hallucination": "Claim support and uncertainty checks",
    "cost": "Budget, token, retry, and resource-bound checks",
    "denial": "Availability and resource-bound checks",
    "spam": "Event-volume and resource-bound checks",
}


def load_atlas(source: str) -> dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=60) as response:  # public MITRE ATLAS data fetch
            return yaml.safe_load(response.read().decode("utf-8")) or {}
    return yaml.safe_load(Path(source).read_text(encoding="utf-8")) or {}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return " ".join(text.split())


def _technique_tactics(data: dict[str, Any]) -> dict[str, list[str]]:
    tactics = data.get("tactics", {}) or {}
    tactic_names = {tid: tactic.get("name", tid) for tid, tactic in tactics.items()}
    relationships = data.get("relationships", {}) or {}
    mapped: dict[str, list[str]] = {}
    for source_id, relation in relationships.items():
        achieves = relation.get("achieves", []) if isinstance(relation, dict) else []
        labels: list[str] = []
        for target_id in achieves:
            if target_id in tactic_names:
                labels.append(f"{target_id} — {tactic_names[target_id]}")
        if labels:
            mapped[source_id] = labels
    return mapped


def _mapping_hint(name: str, table: dict[str, str]) -> str:
    lowered = name.lower()
    for keyword, mapping in table.items():
        if keyword in lowered:
            return mapping
    return UNMAPPED_LABEL


def _status_for(owasp_mapping: str, coverage_area: str) -> str:
    if owasp_mapping == UNMAPPED_LABEL and coverage_area == UNMAPPED_LABEL:
        return UNMAPPED_LABEL
    return "Candidate mapping / needs validation"


def render_matrix(data: dict[str, Any], source: str) -> str:
    collection = data.get("collection", {}) or {}
    tactics = data.get("tactics", {}) or {}
    techniques = data.get("techniques", {}) or {}
    technique_tactics = _technique_tactics(data)
    unmapped_tactics: list[str] = []
    unmapped_techniques: list[str] = []

    lines: list[str] = []
    lines.append("# MITRE ATLAS Matrix for AI Systems")
    lines.append("")
    lines.append("This file is the VulnoraIQ implementation planning register for MITRE ATLAS tactics and techniques. It is generated from the official MITRE ATLAS data source so future VulnoraIQ configuration, test assets, and documentation changes can be checked for drift.")
    lines.append("")
    lines.append(f"> **Generated snapshot:** this checked-in snapshot is generated from the official MITRE ATLAS source path used by VulnoraIQ: `{source}`.")
    lines.append("")
    lines.append("> **Third-party notice:** MITRE ATLAS data is copyright 2021-2026 MITRE and licensed under the Apache License, Version 2.0. VulnoraIQ's use of MITRE ATLAS data does not imply endorsement by MITRE. See `THIRD_PARTY_NOTICES.md`.")
    lines.append("")
    lines.append("> **Current status:** source-of-truth planning register. Entries in this file are not automatically active VulnoraIQ checks. If a tactic or technique cannot be confidently mapped to OWASP or a VulnoraIQ coverage area, it is still listed and marked `Unmapped / map later`.")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- Source: `{source}`")
    lines.append(f"- Collection: `{_clean(collection.get('name'))}`")
    lines.append(f"- Content version: `{_clean(collection.get('version'))}`")
    lines.append(f"- Format version: `{_clean(data.get('format-version'))}`")
    lines.append(f"- Modified date: `{_clean(collection.get('modified-date'))}`")
    lines.append(f"- Tactic count: `{len(tactics)}`")
    lines.append(f"- Technique and sub-technique count: `{len(techniques)}`")
    lines.append("")
    lines.append("## How VulnoraIQ should use this matrix")
    lines.append("")
    lines.append("1. Keep this file generated from `mitre-atlas/atlas-data`.")
    lines.append("2. Use the OWASP and VulnoraIQ coverage columns as planning aids, not final security claims.")
    lines.append("3. Items marked `Unmapped / map later` must remain visible until manually mapped or deliberately excluded with rationale.")
    lines.append("4. Add VulnoraIQ module mappings in `config/mitre_atlas_mapping.yaml` only after review.")
    lines.append("5. Add safe test assets, fixtures, deterministic evaluators, evidence fields, and report/dashboard mapping before marking coverage active.")
    lines.append("")
    lines.append("## Tactics")
    lines.append("")
    lines.append("| Tactic ID | Tactic | Related framework ref | OWASP mapping | VulnoraIQ coverage area | Implementation status | Planning notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for tactic_id in sorted(tactics):
        tactic = tactics[tactic_id]
        name = _clean(tactic.get("name"))
        related = (tactic.get("attack-reference") or {}).get("id", "")
        owasp_mapping = _mapping_hint(name, OWASP_HINTS)
        coverage_area = _mapping_hint(name, COVERAGE_HINTS)
        status = _status_for(owasp_mapping, coverage_area)
        if status == UNMAPPED_LABEL:
            unmapped_tactics.append(f"{tactic_id} — {name}")
        lines.append(f"| {tactic_id} | {name} | {_clean(related)} | {owasp_mapping} | {coverage_area} | {status} | Review this tactic and map related techniques to VulnoraIQ coverage work. |")
    lines.append("")
    lines.append("## Techniques and sub-techniques")
    lines.append("")
    lines.append("| Technique ID | Technique | Tactic(s) | Maturity | Platform(s) | OWASP mapping | VulnoraIQ coverage area | Implementation status | Planning notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for technique_id in sorted(techniques):
        technique = techniques[technique_id]
        name = _clean(technique.get("name"))
        tactics_text = "<br>".join(technique_tactics.get(technique_id, [])) or "Unmapped in ATLAS relationships"
        platforms = ", ".join(technique.get("platforms", []) or [])
        owasp_mapping = _mapping_hint(name, OWASP_HINTS)
        coverage_area = _mapping_hint(name, COVERAGE_HINTS)
        status = _status_for(owasp_mapping, coverage_area)
        if status == UNMAPPED_LABEL:
            unmapped_techniques.append(f"{technique_id} — {name}")
        lines.append(f"| {technique_id} | {name} | {_clean(tactics_text)} | {_clean(technique.get('maturity'))} | {_clean(platforms)} | {owasp_mapping} | {coverage_area} | {status} | Add safe test assets, fixtures, evaluator logic, evidence fields, and report/dashboard mapping before marking active. |")
    lines.append("")
    lines.append("## Unmapped / map later backlog")
    lines.append("")
    lines.append("These entries are intentionally preserved so future VulnoraIQ work can map them later rather than losing them during generation.")
    lines.append("")
    lines.append("### Tactics needing mapping review")
    lines.append("")
    lines.extend([f"- {item}" for item in unmapped_tactics] or ["- None"])
    lines.append("")
    lines.append("### Techniques needing mapping review")
    lines.append("")
    lines.extend([f"- {item}" for item in unmapped_techniques] or ["- None"])
    lines.append("")
    lines.append("## Drift-control rule")
    lines.append("")
    lines.append("Future changes must not manually remove generated tactic/technique rows. Update the official source version or generator, regenerate this file, then update VulnoraIQ configuration against the regenerated IDs. Unmapped entries must stay visible until deliberately mapped or excluded with documented rationale.")
    return "\n".join(lines) + "\n"


def write_or_check(source: str, output: Path, check: bool) -> int:
    data = load_atlas(source)
    rendered = render_matrix(data, source)
    if check:
        existing = output.read_text(encoding="utf-8") if output.exists() else ""
        if existing != rendered:
            print(f"MITRE ATLAS matrix is out of date: {output}", file=sys.stderr)
            return 1
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the VulnoraIQ MITRE ATLAS AI matrix documentation from official ATLAS YAML.")
    parser.add_argument("--source", default=DEFAULT_SOURCE_URL, help="Official ATLAS YAML URL or local file path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown output path.")
    parser.add_argument("--check", action="store_true", help="Fail if the output file is not up to date.")
    args = parser.parse_args()
    raise SystemExit(write_or_check(args.source, Path(args.output), args.check))


if __name__ == "__main__":
    main()
