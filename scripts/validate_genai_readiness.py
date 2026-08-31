from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

REQUIRED_GENAI_IDS = tuple(f"DSGAI{number:02d}" for number in range(1, 22))
SOURCE_DISCREPANCY_IDS = ("DSGAI22", "DSGAI23", "DSGAI24", "DSGAI25")
REQUIRED_FIXTURE_TYPES = {"secure", "vulnerable", "ambiguous", "edge_case"}
REQUIRED_CASE_COUNT = len(REQUIRED_GENAI_IDS) * len(REQUIRED_FIXTURE_TYPES)
ALLOWED_DATA_CLASSIFICATIONS = {"public", "internal", "confidential", "secret", "regulated"}
ALLOWED_DATA_SURFACES = {
    "prompt",
    "upload",
    "retrieval",
    "response",
    "tool_trace",
    "memory",
    "log",
    "report",
    "provider_metadata",
    "vector_store",
    "multimodal_input",
    "model_artifact",
}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_EVALUATORS = {
    "data_classification_present",
    "data_surface_allowed",
    "evidence_fields_present",
    "restricted_marker_leakage",
    "context_window_minimised",
    "scenario_expectation",
    "confidence_floor_met",
    "acceptance_criteria_present",
}
MITRE_TACTIC_RE = re.compile(r"^AML\.TA\d{4}$")
CASE_SUFFIX_BY_FIXTURE = {
    "secure": "secure-baseline",
    "vulnerable": "vulnerable-control-gap",
    "ambiguous": "ambiguous-review",
    "edge_case": "edge-case-boundary",
}
REQUIRED_EVIDENCE_FIELDS = {
    "genai_id",
    "genai_risk_area",
    "scenario_id",
    "fixture_type",
    "data_classification",
    "data_surface",
    "control_objective",
    "production_signal",
    "redaction_status",
    "manual_review_reason",
    "evaluator_chain",
    "acceptance_criteria",
    "severity",
    "confidence_floor",
    "mitre_atlas_tactics",
    "false_positive_notes",
    "false_negative_notes",
}
REQUIRED_CATEGORY_FIELDS = ("genai_id", "risk_area", "data_surface", "mitre_atlas_tactics", "control_objective")
REQUIRED_FIXTURE_FIELDS = (
    "fixture_type",
    "case_suffix",
    "data_classification",
    "severity",
    "confidence_floor",
    "production_signal",
    "manual_review_required",
    "safe_fixture",
    "production_grade",
    "real_world_validation_required",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _validate_metadata(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return [f"{path}: missing metadata section"]

    expected_pairs: dict[str, Any] = {
        "version": 2,
        "scope": "controlled_internal_genai_security",
        "status": "production_scenario_harness_complete",
        "scenario_harness_maturity": "production_grade_controlled_internal",
        "source_confirmed_range": "DSGAI01-DSGAI21",
    }
    for key, expected in expected_pairs.items():
        if metadata.get(key) != expected:
            errors.append(f"{path}: metadata.{key} must be {expected!r}")

    boundary = metadata.get("assurance_boundary")
    if not isinstance(boundary, str) or "not independent real-world detection assurance" not in boundary:
        errors.append(f"{path}: metadata.assurance_boundary must preserve the assurance limitation")

    discrepancy = metadata.get("source_discrepancy")
    if not isinstance(discrepancy, dict):
        errors.append(f"{path}: metadata.source_discrepancy must be tracked")
    else:
        if discrepancy.get("status") != "tracked":
            errors.append(f"{path}: source discrepancy status must be tracked")
        unresolved = discrepancy.get("unresolved_ids")
        if not isinstance(unresolved, list) or sorted(unresolved) != sorted(SOURCE_DISCREPANCY_IDS):
            errors.append(f"{path}: source discrepancy must preserve DSGAI22-DSGAI25 as unresolved")

    review_gate = metadata.get("review_gate")
    if not isinstance(review_gate, dict):
        errors.append(f"{path}: metadata.review_gate is required")
    else:
        for key in ("ci_required", "human_review_required", "external_assurance_required_for_public_claims"):
            if review_gate.get(key) is not True:
                errors.append(f"{path}: metadata.review_gate.{key} must be true")

    return errors


def _validate_scenario_matrix(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    matrix = data.get("scenario_matrix")
    if not isinstance(matrix, dict):
        return [f"{path}: scenario_matrix section is required"]
    if matrix.get("expansion") != "categories_x_fixture_cases":
        errors.append(f"{path}: scenario_matrix.expansion must be categories_x_fixture_cases")
    if matrix.get("case_id_format") != "{genai_id}-{case_suffix}":
        errors.append(f"{path}: scenario_matrix.case_id_format must be '{{genai_id}}-{{case_suffix}}'")
    if matrix.get("expected_case_count") != REQUIRED_CASE_COUNT:
        errors.append(f"{path}: scenario_matrix.expected_case_count must be {REQUIRED_CASE_COUNT}")
    if sorted(matrix.get("required_fixture_types") or []) != sorted(REQUIRED_FIXTURE_TYPES):
        errors.append(f"{path}: scenario_matrix.required_fixture_types must cover {sorted(REQUIRED_FIXTURE_TYPES)}")
    return errors


def _validate_evidence_contract(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    contract = data.get("evidence_contract")
    if not isinstance(contract, dict):
        return [f"{path}: evidence_contract section is required"]

    if contract.get("version") != "genai-production-v2":
        errors.append(f"{path}: evidence_contract.version must be genai-production-v2")

    evidence_fields = contract.get("required_evidence_fields")
    if not isinstance(evidence_fields, list):
        errors.append(f"{path}: evidence_contract.required_evidence_fields must be a list")
    else:
        missing = sorted(REQUIRED_EVIDENCE_FIELDS - set(evidence_fields))
        if missing:
            errors.append(f"{path}: evidence_contract.required_evidence_fields missing {missing}")

    evaluator_chain = contract.get("evaluator_chain")
    if not isinstance(evaluator_chain, list) or len(evaluator_chain) < 5:
        errors.append(f"{path}: evidence_contract.evaluator_chain must include at least five evaluators")
    else:
        invalid = sorted(set(evaluator_chain) - ALLOWED_EVALUATORS)
        if invalid:
            errors.append(f"{path}: evidence_contract.evaluator_chain contains unknown evaluators {invalid}")
        for required_evaluator in ("data_classification_present", "data_surface_allowed", "evidence_fields_present", "scenario_expectation"):
            if required_evaluator not in evaluator_chain:
                errors.append(f"{path}: evidence_contract.evaluator_chain missing {required_evaluator}")

    criteria = contract.get("acceptance_criteria")
    if not isinstance(criteria, list) or len(criteria) < 4:
        errors.append(f"{path}: evidence_contract.acceptance_criteria must include at least four criteria")

    for notes_field in ("false_positive_notes", "false_negative_notes"):
        if not isinstance(contract.get(notes_field), str) or not contract[notes_field]:
            errors.append(f"{path}: evidence_contract.{notes_field} is required")

    return errors


def _validate_fixture_cases(data: dict[str, Any], path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    fixture_cases = data.get("fixture_cases")
    if not isinstance(fixture_cases, list):
        return {}, [f"{path}: fixture_cases must be a list"]

    by_type: dict[str, dict[str, Any]] = {}
    for fixture in fixture_cases:
        if not isinstance(fixture, dict):
            errors.append(f"{path}: fixture case must be a mapping")
            continue
        fixture_type = fixture.get("fixture_type")
        prefix = f"{path}.fixture_cases.{fixture_type or '<missing>'}"
        for field in REQUIRED_FIXTURE_FIELDS:
            if fixture.get(field) in (None, "", []):
                errors.append(f"{prefix}: missing required field '{field}'")
        if fixture_type not in REQUIRED_FIXTURE_TYPES:
            errors.append(f"{prefix}: invalid fixture_type")
            continue
        if fixture_type in by_type:
            errors.append(f"{prefix}: duplicate fixture_type")
        by_type[str(fixture_type)] = fixture
        if fixture.get("case_suffix") != CASE_SUFFIX_BY_FIXTURE[fixture_type]:
            errors.append(f"{prefix}: case_suffix must be {CASE_SUFFIX_BY_FIXTURE[fixture_type]}")
        if fixture.get("data_classification") not in ALLOWED_DATA_CLASSIFICATIONS:
            errors.append(f"{prefix}: invalid data_classification")
        if fixture.get("severity") not in ALLOWED_SEVERITIES:
            errors.append(f"{prefix}: invalid severity")
        confidence_floor = fixture.get("confidence_floor")
        if not isinstance(confidence_floor, (float, int)) or not 0.8 <= float(confidence_floor) <= 1.0:
            errors.append(f"{prefix}: confidence_floor must be between 0.8 and 1.0")
        for bool_field in ("manual_review_required", "safe_fixture", "production_grade", "real_world_validation_required"):
            if fixture.get(bool_field) is not True:
                errors.append(f"{prefix}: {bool_field} must be true")
        if fixture_type == "vulnerable" and fixture.get("severity") not in {"high", "critical"}:
            errors.append(f"{prefix}: vulnerable production cases must be high or critical severity")

    missing_types = sorted(REQUIRED_FIXTURE_TYPES - set(by_type))
    if missing_types:
        errors.append(f"{path}: fixture_cases missing {missing_types}")
    return by_type, errors


def _validate_categories(data: dict[str, Any], path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    categories = data.get("categories")
    if not isinstance(categories, list):
        return {}, [f"{path}: categories must be a list"]

    by_id: dict[str, dict[str, Any]] = {}
    for category in categories:
        if not isinstance(category, dict):
            errors.append(f"{path}: category entry must be a mapping")
            continue
        genai_id = category.get("genai_id")
        prefix = f"{path}.categories.{genai_id or '<missing>'}"
        for field in REQUIRED_CATEGORY_FIELDS:
            if category.get(field) in (None, "", []):
                errors.append(f"{prefix}: missing required field '{field}'")
        if genai_id not in REQUIRED_GENAI_IDS:
            errors.append(f"{prefix}: unknown genai_id")
            continue
        if genai_id in by_id:
            errors.append(f"{prefix}: duplicate category")
        by_id[str(genai_id)] = category
        if category.get("data_surface") not in ALLOWED_DATA_SURFACES:
            errors.append(f"{prefix}: invalid data_surface")
        tactics = category.get("mitre_atlas_tactics")
        if not isinstance(tactics, list) or not tactics:
            errors.append(f"{prefix}: mitre_atlas_tactics must be non-empty")
        else:
            for tactic in tactics:
                if not isinstance(tactic, str) or not MITRE_TACTIC_RE.match(tactic):
                    errors.append(f"{prefix}: invalid MITRE ATLAS tactic '{tactic}'")

    missing_ids = sorted(set(REQUIRED_GENAI_IDS) - set(by_id))
    if missing_ids:
        errors.append(f"{path}: categories missing {missing_ids}")

    return by_id, errors


def _expanded_case_ids(categories: dict[str, dict[str, Any]], fixture_cases: dict[str, dict[str, Any]]) -> list[str]:
    return [
        f"{genai_id}-{fixture_cases[fixture_type]['case_suffix']}"
        for genai_id in sorted(categories)
        for fixture_type in sorted(fixture_cases)
    ]


def validate_manifest(path: str | Path = "benchmarks/fixtures/genai/scenarios.yaml") -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {
            "status": "fail",
            "path": str(manifest_path),
            "scenario_count": 0,
            "errors": [f"{manifest_path}: file not found"],
        }

    data = _load_yaml(manifest_path)
    errors = [
        *_validate_metadata(data, manifest_path),
        *_validate_scenario_matrix(data, manifest_path),
        *_validate_evidence_contract(data, manifest_path),
    ]
    categories, category_errors = _validate_categories(data, manifest_path)
    fixture_cases, fixture_errors = _validate_fixture_cases(data, manifest_path)
    errors.extend(category_errors)
    errors.extend(fixture_errors)

    expanded_case_ids = _expanded_case_ids(categories, fixture_cases)
    if len(expanded_case_ids) != REQUIRED_CASE_COUNT:
        errors.append(f"{manifest_path}: expanded scenario matrix must produce {REQUIRED_CASE_COUNT} cases")
    if len(set(expanded_case_ids)) != len(expanded_case_ids):
        errors.append(f"{manifest_path}: expanded scenario matrix produced duplicate case ids")

    return {
        "status": "fail" if errors else "pass",
        "path": str(manifest_path),
        "scenario_count": len(expanded_case_ids),
        "expected_case_count": REQUIRED_CASE_COUNT,
        "expected_genai_ids": list(REQUIRED_GENAI_IDS),
        "required_fixture_types": sorted(REQUIRED_FIXTURE_TYPES),
        "sample_case_ids": expanded_case_ids[:8],
        "errors": errors,
    }


def validate_default() -> dict[str, Any]:
    manifest_result = validate_manifest()
    return {
        "status": manifest_result["status"],
        "manifest": manifest_result,
        "errors": list(manifest_result["errors"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the GenAI Security production-grade scenario harness manifest.")
    parser.add_argument("--manifest", default="benchmarks/fixtures/genai/scenarios.yaml")
    args = parser.parse_args()

    manifest_result = validate_manifest(args.manifest)
    result = {
        "status": manifest_result["status"],
        "manifest": manifest_result,
        "errors": list(manifest_result["errors"]),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
