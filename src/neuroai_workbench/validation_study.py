from __future__ import annotations

import json
import re
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from .resource_loader import read_resource_bytes
from .util import canonical_json_bytes, load_json, sha256_bytes

OPERATIONS_PACKAGE = "neuroai_workbench.resources.operations"
CASE_SCHEMA = "VALIDATION_CASE_MANIFEST.schema.json"
PARAMETER_SCHEMA = "VALIDATION_STUDY_PARAMETER_SET.schema.json"
AMENDMENT_SCHEMA = "VALIDATION_PROTOCOL_AMENDMENT.schema.json"

CASE_BOUNDARY = (
    "A validation case manifest freezes case, evidence, and instrument inputs only. It contains no assessor outcome, "
    "participant record, empirical validation result, release decision, or clinical or regulatory claim."
)
PARAMETER_BOUNDARY = (
    "A validation study parameter set freezes pre-outcome design and analysis choices. It does not establish observed "
    "reliability, validity, accessibility, usefulness, publication readiness, or release authority."
)
AMENDMENT_BOUNDARY = (
    "A validation protocol amendment preserves an append-only change to a frozen study plan. It does not rewrite the "
    "predecessor preregistration or manufacture retrospective pre-outcome status."
)

REQUIRED_ESTIMAND_FAMILIES = frozenset(
    {
        "REQUIREMENT_APPLICABILITY",
        "REQUIREMENT_FINDING",
        "ASSESSMENT_COVERAGE",
        "CLAIM_STATUS",
        "EVIDENCE_ACCESS_STATE",
        "GAP_REOPENING",
        "TYPED_DECISION",
        "EVIDENCE_SELECTION",
        "CLAIM_EVIDENCE_LINKS",
    }
)

DECISION_STATE_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "CLAIM ADJUDICATION": (
        "SUPPORTED WITHIN BOUNDED SCOPE",
        "PARTIALLY SUPPORTED",
        "UNSUPPORTED",
        "CONTRADICTED",
        "ASSESSMENT INCOMPLETE",
    ),
    "LEGAL OR REGULATORY AUTHORIZATION": (
        "AUTHORIZED WITHIN BOUNDED SCOPE",
        "NOT AUTHORIZED",
        "AUTHORIZATION NOT ASSESSED",
        "NOT APPLICABLE",
        "ASSESSMENT INCOMPLETE",
    ),
    "CONFORMANCE DECISION": (
        "CONFORMS FOR BOUNDED SCOPE",
        "CONDITIONAL CONFORMANCE",
        "NO CONFORMANCE DECISION — BLOCKED",
        "NOT APPLICABLE",
        "ASSESSMENT INCOMPLETE",
    ),
    "PROHIBITED-USE DECISION": (
        "PROHIBITED OR DISPROPORTIONATE USE",
        "NOT APPLICABLE",
        "ASSESSMENT INCOMPLETE",
    ),
    "REOPENING DECISION": (
        "REOPENED",
        "NOT APPLICABLE",
        "ASSESSMENT INCOMPLETE",
    ),
}

_REQUIRED_CONSEQUENTIAL = frozenset(
    {
        ("REQUIREMENT_FINDING", "", "STATE_PAIR", "PASS", "FAIL"),
        ("CLAIM_STATUS", "", "STATE_PAIR", "SUPPORTED WITHIN BOUNDED SCOPE", "UNSUPPORTED"),
        ("CLAIM_STATUS", "", "STATE_PAIR", "SUPPORTED WITHIN BOUNDED SCOPE", "CONTRADICTED"),
        (
            "TYPED_DECISION",
            "LEGAL OR REGULATORY AUTHORIZATION",
            "STATE_PAIR",
            "AUTHORIZED WITHIN BOUNDED SCOPE",
            "NOT AUTHORIZED",
        ),
        (
            "TYPED_DECISION",
            "CONFORMANCE DECISION",
            "STATE_PAIR",
            "CONFORMS FOR BOUNDED SCOPE",
            "NO CONFORMANCE DECISION — BLOCKED",
        ),
        (
            "TYPED_DECISION",
            "PROHIBITED-USE DECISION",
            "PRESENCE_ABSENCE",
            "PROHIBITED OR DISPROPORTIONATE USE",
            "",
        ),
        ("TYPED_DECISION", "REOPENING DECISION", "PRESENCE_ABSENCE", "REOPENED", ""),
    }
)


def _schema(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(OPERATIONS_PACKAGE).joinpath(name).read_text(encoding="utf-8")))


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name), format_checker=FormatChecker())
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _commit(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _reference_token(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith(("public-ref:", "protected-ref:")):
        return False
    suffix = value.split(":", 1)[1]
    if not suffix or suffix.startswith(("/", "\\", "~")) or "file://" in suffix.casefold():
        return False
    return re.match(r"^[A-Za-z]:[\\/]", suffix) is None


def _reference_errors(value: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [_error("INVALID_REFERENCE", path, "Reference must be an object")]
    errors: list[dict[str, str]] = []
    if not _reference_token(value.get("reference")):
        errors.append(
            _error(
                "INVALID_REFERENCE", path + ".reference", "Reference must use a bounded public-ref: or protected-ref:"
            )
        )
    if not _digest(value.get("sha256")):
        errors.append(_error("INVALID_DIGEST", path + ".sha256", "Reference SHA-256 is invalid"))
    return errors


def _record_sha256(value: dict[str, Any], digest_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != digest_field}
    return sha256_bytes(canonical_json_bytes(controlled))


def case_manifest_sha256(value: dict[str, Any]) -> str:
    return _record_sha256(value, "manifest_sha256")


def study_parameter_set_sha256(value: dict[str, Any]) -> str:
    return _record_sha256(value, "parameter_set_sha256")


def protocol_amendment_sha256(value: dict[str, Any]) -> str:
    return _record_sha256(value, "amendment_sha256")


def current_v42_normative_identity(software_commit_sha: str) -> dict[str, str]:
    if not _commit(software_commit_sha):
        raise ValueError("software_commit_sha must be a lowercase 40-character commit SHA")
    return {
        "object_model_version": "v4.2",
        "kernel_requirements_sha256": sha256_bytes(read_resource_bytes("KERNEL_REQUIREMENTS_v4.2.json")),
        "controlled_vocabularies_sha256": sha256_bytes(read_resource_bytes("CONTROLLED_VOCABULARIES_v4.2.json")),
        "assessment_schema_sha256": sha256_bytes(read_resource_bytes("UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json")),
        "software_commit_sha": software_commit_sha,
    }


def _normative_errors(value: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [_error("NORMATIVE_IDENTITY_INVALID", path, "Normative identity must be an object")]
    commit_sha = value.get("software_commit_sha")
    if not _commit(commit_sha):
        return [_error("NORMATIVE_IDENTITY_INVALID", path + ".software_commit_sha", "Software commit SHA is invalid")]
    expected = current_v42_normative_identity(str(commit_sha))
    if value != expected:
        return [
            _error("NORMATIVE_IDENTITY_MISMATCH", path, "Normative identity does not match packaged v4.2 resources")
        ]
    return []


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _controlled_vocabularies() -> dict[str, list[str]]:
    return cast(dict[str, list[str]], json.loads(read_resource_bytes("CONTROLLED_VOCABULARIES_v4.2.json")))


def _compatibility_is_controlled() -> bool:
    vocab = _controlled_vocabularies()
    decision_types = set(vocab["decision_object_type"])
    decision_states = set(vocab["decision_state"])
    return set(DECISION_STATE_COMPATIBILITY) == decision_types and all(
        set(states) <= decision_states for states in DECISION_STATE_COMPATIBILITY.values()
    )


def finalize_case_manifest(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["manifest_sha256"] = case_manifest_sha256(result)
    return result


def finalize_study_parameter_set(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["parameter_set_sha256"] = study_parameter_set_sha256(result)
    return result


def finalize_protocol_amendment(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result["amendment_sha256"] = protocol_amendment_sha256(result)
    return result


def load_validation_record(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Validation study record {path} must be a JSON object")
    return cast(dict[str, Any], value)


def load_case_manifests(directory: Path) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        value = load_validation_record(path)
        case_id = value.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"Validation case manifest {path.name} has no case_id")
        if case_id in manifests:
            raise ValueError(f"Duplicate validation case_id {case_id!r}")
        manifests[case_id] = value
    return manifests


def validate_case_manifest(value: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = list(_schema_errors(value, CASE_SCHEMA))
    errors.extend(_normative_errors(value.get("normative_identity"), "normative_identity"))
    errors.extend(_reference_errors(value.get("case_instructions"), "case_instructions"))
    errors.extend(_reference_errors(value.get("evidence_manifest"), "evidence_manifest"))

    if value.get("boundary") != CASE_BOUNDARY:
        errors.append(_error("BOUNDARY_MISMATCH", "boundary", "Case-manifest boundary text is not canonical"))
    expected_hash = case_manifest_sha256(value)
    if value.get("manifest_sha256") != expected_hash:
        errors.append(_error("HASH_MISMATCH", "manifest_sha256", "Case manifest canonical digest mismatch"))

    evidence = value.get("evidence_objects")
    evidence_items = evidence if isinstance(evidence, list) else []
    evidence_ids = [str(item.get("evidence_id", "")) for item in evidence_items if isinstance(item, dict)]
    duplicates = _duplicates(evidence_ids)
    if duplicates:
        errors.append(_error("DUPLICATE_EVIDENCE_ID", "evidence_objects", f"Duplicate evidence IDs: {duplicates}"))

    protected_count = 0
    for index, raw in enumerate(evidence_items):
        if not isinstance(raw, dict):
            continue
        reference = raw.get("reference")
        access = raw.get("access")
        if not _reference_token(reference):
            errors.append(
                _error("INVALID_REFERENCE", f"evidence_objects.{index}.reference", "Evidence reference is not bounded")
            )
            continue
        if access == "PUBLIC" and not str(reference).startswith("public-ref:"):
            errors.append(
                _error("ACCESS_REFERENCE_MISMATCH", f"evidence_objects.{index}", "PUBLIC evidence requires public-ref:")
            )
        if access == "PROTECTED":
            protected_count += 1
            if not str(reference).startswith("protected-ref:"):
                errors.append(
                    _error(
                        "ACCESS_REFERENCE_MISMATCH",
                        f"evidence_objects.{index}",
                        "PROTECTED evidence requires protected-ref:",
                    )
                )
        if not _digest(raw.get("sha256")):
            errors.append(_error("INVALID_DIGEST", f"evidence_objects.{index}.sha256", "Evidence SHA-256 is invalid"))

    boundary = value.get("public_private_boundary")
    if protected_count and boundary != "MIXED_WITH_PROTECTED_REFERENCES":
        errors.append(
            _error("PUBLIC_PRIVATE_MISMATCH", "public_private_boundary", "Protected evidence requires mixed boundary")
        )
    if not protected_count and boundary != "PUBLIC_ONLY":
        errors.append(
            _error("PUBLIC_PRIVATE_MISMATCH", "public_private_boundary", "Public-only evidence requires PUBLIC_ONLY")
        )

    return {
        "valid": not errors,
        "errors": errors,
        "case_id": value.get("case_id"),
        "manifest_id": value.get("manifest_id"),
        "canonical_sha256": expected_hash,
        "evidence_count": len(evidence_items),
        "protected_evidence_count": protected_count,
        "boundary": CASE_BOUNDARY,
    }


def _consequential_signature(rule: dict[str, Any]) -> tuple[str, str, str, str, str]:
    left = str(rule.get("left_state", ""))
    right = str(rule.get("right_state", ""))
    if rule.get("comparison_mode") == "STATE_PAIR" and right < left:
        left, right = right, left
    return (
        str(rule.get("field_family", "")),
        str(rule.get("decision_object_type", "")),
        str(rule.get("comparison_mode", "")),
        left,
        right,
    )


def _required_signatures_normalized() -> set[tuple[str, str, str, str, str]]:
    result: set[tuple[str, str, str, str, str]] = set()
    for family, decision_type, mode, left, right in _REQUIRED_CONSEQUENTIAL:
        if mode == "STATE_PAIR" and right < left:
            left, right = right, left
        result.add((family, decision_type, mode, left, right))
    return result


def _consequential_errors(rules: Any) -> list[dict[str, str]]:
    if not isinstance(rules, list):
        return [_error("CONSEQUENTIAL_RULES_INVALID", "consequential_disagreements", "Rules must be a list")]
    errors: list[dict[str, str]] = []
    vocab = _controlled_vocabularies()
    finding_states = set(vocab["finding_status"])
    claim_states = set(vocab["claim_status"])
    rule_ids = [str(item.get("rule_id", "")) for item in rules if isinstance(item, dict)]
    duplicates = _duplicates(rule_ids)
    if duplicates:
        errors.append(_error("DUPLICATE_RULE_ID", "consequential_disagreements", f"Duplicate rule IDs: {duplicates}"))

    signatures: set[tuple[str, str, str, str, str]] = set()
    for index, raw in enumerate(rules):
        if not isinstance(raw, dict):
            continue
        family = raw.get("field_family")
        mode = raw.get("comparison_mode")
        left = raw.get("left_state")
        right = raw.get("right_state")
        decision_type = raw.get("decision_object_type")
        allowed: set[str]
        if family == "REQUIREMENT_FINDING":
            allowed = finding_states
            if decision_type is not None:
                errors.append(
                    _error(
                        "UNEXPECTED_DECISION_TYPE",
                        f"consequential_disagreements.{index}",
                        "Finding rule cannot name decision type",
                    )
                )
        elif family == "CLAIM_STATUS":
            allowed = claim_states
            if decision_type is not None:
                errors.append(
                    _error(
                        "UNEXPECTED_DECISION_TYPE",
                        f"consequential_disagreements.{index}",
                        "Claim rule cannot name decision type",
                    )
                )
        elif family == "TYPED_DECISION" and decision_type in DECISION_STATE_COMPATIBILITY:
            allowed = set(DECISION_STATE_COMPATIBILITY[str(decision_type)])
        else:
            errors.append(
                _error("INVALID_RULE_DOMAIN", f"consequential_disagreements.{index}", "Rule field/type is invalid")
            )
            continue
        if left not in allowed:
            errors.append(
                _error(
                    "INVALID_RULE_STATE",
                    f"consequential_disagreements.{index}.left_state",
                    "Left state is incompatible",
                )
            )
        if mode == "STATE_PAIR":
            if right not in allowed or right == left:
                errors.append(
                    _error(
                        "INVALID_RULE_STATE",
                        f"consequential_disagreements.{index}.right_state",
                        "Right state is incompatible or identical",
                    )
                )
        elif mode == "PRESENCE_ABSENCE":
            if family != "TYPED_DECISION" or right is not None:
                errors.append(
                    _error(
                        "INVALID_PRESENCE_RULE",
                        f"consequential_disagreements.{index}",
                        "Presence/absence is only valid for typed decisions and has no right_state",
                    )
                )
        if not str(raw.get("interval_method", "")).strip():
            errors.append(
                _error(
                    "MISSING_INTERVAL_METHOD",
                    f"consequential_disagreements.{index}.interval_method",
                    "Interval method must be frozen",
                )
            )
        signatures.add(_consequential_signature(raw))

    missing = _required_signatures_normalized() - signatures
    if missing:
        errors.append(
            _error(
                "MISSING_CONSEQUENTIAL_RULE",
                "consequential_disagreements",
                f"Required consequential rules missing: {sorted(missing)}",
            )
        )
    return errors


def validate_study_parameter_set(
    value: dict[str, Any], *, case_manifests: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = list(_schema_errors(value, PARAMETER_SCHEMA))
    warnings: list[dict[str, Any]] = []
    errors.extend(_normative_errors(value.get("normative_identity"), "normative_identity"))
    if value.get("boundary") != PARAMETER_BOUNDARY:
        errors.append(_error("BOUNDARY_MISMATCH", "boundary", "Parameter-set boundary text is not canonical"))
    expected_hash = study_parameter_set_sha256(value)
    if value.get("parameter_set_sha256") != expected_hash:
        errors.append(_error("HASH_MISMATCH", "parameter_set_sha256", "Study parameter-set canonical digest mismatch"))

    if not _compatibility_is_controlled():
        errors.append(
            _error(
                "INTERNAL_COMPATIBILITY_INVALID",
                "decision_state_compatibility",
                "Built-in matrix uses invalid v4.2 states",
            )
        )
    declared_compatibility = value.get("decision_state_compatibility")
    expected_compatibility = {key: list(states) for key, states in DECISION_STATE_COMPATIBILITY.items()}
    if declared_compatibility != expected_compatibility:
        errors.append(
            _error(
                "DECISION_COMPATIBILITY_MISMATCH",
                "decision_state_compatibility",
                "Decision compatibility matrix is not canonical",
            )
        )

    for path, reference in (
        ("protocol_reference", value.get("protocol_reference")),
        (
            "analysis_identity.code_reference",
            (value.get("analysis_identity") or {}).get("code_reference")
            if isinstance(value.get("analysis_identity"), dict)
            else None,
        ),
        (
            "analysis_identity.environment_reference",
            (value.get("analysis_identity") or {}).get("environment_reference")
            if isinstance(value.get("analysis_identity"), dict)
            else None,
        ),
        (
            "assessor_design.training_reference",
            (value.get("assessor_design") or {}).get("training_reference")
            if isinstance(value.get("assessor_design"), dict)
            else None,
        ),
        (
            "precision_plan.simulation_code_reference",
            (value.get("precision_plan") or {}).get("simulation_code_reference")
            if isinstance(value.get("precision_plan"), dict)
            else None,
        ),
        (
            "decision_usefulness.comparator_reference",
            (value.get("decision_usefulness") or {}).get("comparator_reference")
            if isinstance(value.get("decision_usefulness"), dict)
            else None,
        ),
    ):
        errors.extend(_reference_errors(reference, path))

    strata = value.get("case_strata") if isinstance(value.get("case_strata"), list) else []
    stratum_ids = [str(item.get("stratum_id", "")) for item in strata if isinstance(item, dict)]
    duplicate_strata = _duplicates(stratum_ids)
    if duplicate_strata:
        errors.append(_error("DUPLICATE_STRATUM_ID", "case_strata", f"Duplicate strata: {duplicate_strata}"))

    cases = value.get("cases") if isinstance(value.get("cases"), list) else []
    case_ids = [str(item.get("case_id", "")) for item in cases if isinstance(item, dict)]
    duplicate_cases = _duplicates(case_ids)
    if duplicate_cases:
        errors.append(_error("DUPLICATE_CASE_ID", "cases", f"Duplicate cases: {duplicate_cases}"))
    manifest_digests = [str(item.get("manifest_sha256", "")) for item in cases if isinstance(item, dict)]
    duplicate_manifests = _duplicates(manifest_digests)
    if duplicate_manifests:
        errors.append(
            _error("DUPLICATE_CASE_MANIFEST", "cases", f"Duplicate case-manifest digests: {duplicate_manifests}")
        )
    unknown_strata = sorted(
        {str(item.get("case_class_id", "")) for item in cases if isinstance(item, dict)} - set(stratum_ids)
    )
    if unknown_strata:
        errors.append(_error("UNKNOWN_CASE_STRATUM", "cases", f"Cases reference unknown strata: {unknown_strata}"))

    count_by_stratum: dict[str, int] = {key: 0 for key in stratum_ids}
    for item in cases:
        if isinstance(item, dict) and str(item.get("case_class_id", "")) in count_by_stratum:
            count_by_stratum[str(item["case_class_id"])] += 1
    if any(count == 0 for count in count_by_stratum.values()):
        errors.append(_error("EMPTY_CASE_STRATUM", "cases", "Every frozen stratum must contain at least one case"))

    precision = value.get("precision_plan") if isinstance(value.get("precision_plan"), dict) else {}
    planned_counts = (
        precision.get("case_counts_by_stratum") if isinstance(precision.get("case_counts_by_stratum"), list) else []
    )
    planned = {
        str(item.get("stratum_id", "")): item.get("case_count") for item in planned_counts if isinstance(item, dict)
    }
    if planned != count_by_stratum:
        errors.append(
            _error(
                "CASE_COUNT_MISMATCH",
                "precision_plan.case_counts_by_stratum",
                "Planned case counts do not match frozen cases",
            )
        )
    sensitivity = precision.get("disagreement_prevalence_sensitivity")
    if isinstance(sensitivity, list) and len(set(sensitivity)) != len(sensitivity):
        errors.append(
            _error(
                "DUPLICATE_SENSITIVITY_POINT",
                "precision_plan.disagreement_prevalence_sensitivity",
                "Sensitivity points must be unique",
            )
        )

    assessor = value.get("assessor_design") if isinstance(value.get("assessor_design"), dict) else {}
    assessor_count = assessor.get("final_assessors_per_case")
    if (
        isinstance(assessor_count, int)
        and assessor_count < 3
        and not str(assessor.get("precision_override_justification", "")).strip()
    ):
        errors.append(
            _error(
                "ASSESSOR_COUNT_UNJUSTIFIED",
                "assessor_design.final_assessors_per_case",
                "Fewer than three assessors requires a frozen precision justification",
            )
        )

    analysis = value.get("analysis_identity") if isinstance(value.get("analysis_identity"), dict) else {}
    seeds = analysis.get("random_seeds") if isinstance(analysis.get("random_seeds"), list) else []
    if len(seeds) != len(set(seeds)):
        errors.append(_error("DUPLICATE_RANDOM_SEED", "analysis_identity.random_seeds", "Random seeds must be unique"))

    estimands = value.get("reliability_estimands") if isinstance(value.get("reliability_estimands"), list) else []
    families = [str(item.get("field_family", "")) for item in estimands if isinstance(item, dict)]
    if set(families) != REQUIRED_ESTIMAND_FAMILIES or len(families) != len(REQUIRED_ESTIMAND_FAMILIES):
        errors.append(
            _error(
                "ESTIMAND_COVERAGE",
                "reliability_estimands",
                "Exactly the nine required estimand families must be frozen once each",
            )
        )
    for index, item in enumerate(estimands):
        if not isinstance(item, dict):
            continue
        if set(item.get("clustering_units", [])) != {"CASE", "ASSESSOR"} or len(item.get("clustering_units", [])) != 2:
            errors.append(
                _error(
                    "CLUSTERING_REQUIRED",
                    f"reliability_estimands.{index}.clustering_units",
                    "Confirmatory uncertainty must preserve case and assessor clustering",
                )
            )
        if item.get("field_family") == "REQUIREMENT_FINDING" and "NOT ASSESSED" not in item.get(
            "excluded_structural_states", []
        ):
            errors.append(
                _error(
                    "STRUCTURAL_STATE_COLLAPSE",
                    f"reliability_estimands.{index}",
                    "NOT ASSESSED must stay outside the ordinal finding-state estimand",
                )
            )

    errors.extend(_consequential_errors(value.get("consequential_disagreements")))

    linguistic = value.get("linguistic_validation") if isinstance(value.get("linguistic_validation"), dict) else {}
    locales = (
        linguistic.get("proposed_non_english_publication_locales")
        if isinstance(linguistic.get("proposed_non_english_publication_locales"), list)
        else []
    )
    locale_rows = linguistic.get("locale_parameters") if isinstance(linguistic.get("locale_parameters"), list) else []
    if _duplicates([str(locale) for locale in locales]):
        errors.append(
            _error(
                "DUPLICATE_LOCALE",
                "linguistic_validation.proposed_non_english_publication_locales",
                "Locales must be unique",
            )
        )
    if any(str(locale).casefold() == "en" or str(locale).casefold().startswith("en-") for locale in locales):
        errors.append(
            _error(
                "ENGLISH_IN_NON_ENGLISH_SET",
                "linguistic_validation.proposed_non_english_publication_locales",
                "English locales do not belong in the non-English publication set",
            )
        )
    locale_param_ids = [str(item.get("locale", "")) for item in locale_rows if isinstance(item, dict)]
    if set(locale_param_ids) != set(str(locale) for locale in locales) or len(locale_param_ids) != len(locales):
        errors.append(
            _error(
                "LOCALE_PARAMETER_MISMATCH",
                "linguistic_validation.locale_parameters",
                "Locale parameters must match the proposed non-English locale set exactly",
            )
        )

    accessibility = value.get("accessibility") if isinstance(value.get("accessibility"), dict) else {}
    tasks = accessibility.get("critical_tasks") if isinstance(accessibility.get("critical_tasks"), list) else []
    duplicate_tasks = _duplicates([str(item.get("task_id", "")) for item in tasks if isinstance(item, dict)])
    if duplicate_tasks:
        errors.append(
            _error(
                "DUPLICATE_ACCESSIBILITY_TASK", "accessibility.critical_tasks", f"Duplicate task IDs: {duplicate_tasks}"
            )
        )

    usefulness = value.get("decision_usefulness") if isinstance(value.get("decision_usefulness"), dict) else {}
    defects = (
        usefulness.get("critical_defect_taxonomy")
        if isinstance(usefulness.get("critical_defect_taxonomy"), list)
        else []
    )
    duplicate_defects = _duplicates([str(item) for item in defects])
    if duplicate_defects:
        errors.append(
            _error(
                "DUPLICATE_CRITICAL_DEFECT",
                "decision_usefulness.critical_defect_taxonomy",
                f"Duplicate defect definitions: {duplicate_defects}",
            )
        )

    if case_manifests is None:
        errors.append(
            _error(
                "CASE_MANIFESTS_REQUIRED",
                "cases",
                "Full parameter-set validation requires the referenced case manifests",
            )
        )
    else:
        parameter_normative = value.get("normative_identity")
        study_wave_id = value.get("study_wave_id")
        for index, raw in enumerate(cases):
            if not isinstance(raw, dict):
                continue
            case_id = str(raw.get("case_id", ""))
            if not _reference_token(raw.get("manifest_reference")):
                errors.append(
                    _error(
                        "INVALID_REFERENCE",
                        f"cases.{index}.manifest_reference",
                        "Case manifest reference is not bounded",
                    )
                )
            manifest = case_manifests.get(case_id)
            if manifest is None:
                errors.append(
                    _error("CASE_MANIFEST_MISSING", f"cases.{index}", f"Case manifest {case_id!r} is missing")
                )
                continue
            manifest_report = validate_case_manifest(manifest)
            if manifest_report["valid"] is not True:
                errors.append(
                    _error("CASE_MANIFEST_INVALID", f"cases.{index}", f"Case manifest {case_id!r} is invalid")
                )
            if raw.get("manifest_sha256") != case_manifest_sha256(manifest):
                errors.append(
                    _error(
                        "CASE_MANIFEST_DIGEST_MISMATCH",
                        f"cases.{index}.manifest_sha256",
                        "Referenced case digest does not match content",
                    )
                )
            if manifest.get("study_wave_id") != study_wave_id:
                errors.append(
                    _error("CASE_WAVE_MISMATCH", f"cases.{index}", "Case study wave does not match parameter set")
                )
            if manifest.get("normative_identity") != parameter_normative:
                errors.append(
                    _error(
                        "CASE_NORMATIVE_MISMATCH",
                        f"cases.{index}",
                        "Case normative identity does not match parameter set",
                    )
                )
            if manifest.get("case_class_id") != raw.get("case_class_id"):
                errors.append(_error("CASE_CLASS_MISMATCH", f"cases.{index}", "Case stratum does not match manifest"))
            if manifest.get("calibration_status") != raw.get("calibration_status"):
                errors.append(
                    _error(
                        "CASE_CALIBRATION_MISMATCH", f"cases.{index}", "Case calibration status does not match manifest"
                    )
                )
        extra_cases = sorted(set(case_manifests) - set(case_ids))
        if extra_cases:
            warnings.append(
                {
                    "code": "UNREFERENCED_CASE_MANIFESTS",
                    "case_ids": extra_cases,
                    "message": "Case manifests were supplied but are not part of this frozen parameter set.",
                }
            )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "parameter_set_id": value.get("parameter_set_id"),
        "canonical_sha256": expected_hash,
        "case_count": len(cases),
        "stratum_count": len(strata),
        "boundary": PARAMETER_BOUNDARY,
    }


def validate_protocol_amendment(
    value: dict[str, Any], *, parameter_sets: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = list(_schema_errors(value, AMENDMENT_SCHEMA))
    warnings: list[dict[str, Any]] = []
    if value.get("boundary") != AMENDMENT_BOUNDARY:
        errors.append(_error("BOUNDARY_MISMATCH", "boundary", "Amendment boundary text is not canonical"))
    expected_hash = protocol_amendment_sha256(value)
    if value.get("amendment_sha256") != expected_hash:
        errors.append(_error("HASH_MISMATCH", "amendment_sha256", "Amendment canonical digest mismatch"))

    predecessor_id = value.get("predecessor_parameter_set_id")
    successor_id = value.get("successor_parameter_set_id")
    if predecessor_id == successor_id:
        errors.append(
            _error(
                "SELF_REFERENTIAL_AMENDMENT",
                "successor_parameter_set_id",
                "Amendment must create a distinct successor parameter set",
            )
        )
    if value.get("predecessor_parameter_set_sha256") == value.get("successor_parameter_set_sha256"):
        errors.append(
            _error(
                "UNCHANGED_PARAMETER_DIGEST",
                "successor_parameter_set_sha256",
                "Amended parameter set must have a distinct digest",
            )
        )

    changed_fields = value.get("changed_fields") if isinstance(value.get("changed_fields"), list) else []
    duplicate_fields = _duplicates([str(item) for item in changed_fields])
    if duplicate_fields:
        errors.append(
            _error("DUPLICATE_CHANGED_FIELD", "changed_fields", f"Duplicate changed fields: {duplicate_fields}")
        )
    impact = value.get("analysis_class_impact") if isinstance(value.get("analysis_class_impact"), list) else []
    if "NO_ANALYSIS_IMPACT" in impact and len(impact) > 1:
        errors.append(
            _error(
                "ANALYSIS_IMPACT_CONFLICT",
                "analysis_class_impact",
                "NO_ANALYSIS_IMPACT cannot be combined with analysis classes",
            )
        )
    affected = sum(
        len(value.get(key, [])) if isinstance(value.get(key), list) else 0
        for key in ("affected_cases", "affected_outcomes", "affected_analyses")
    )
    if affected == 0:
        errors.append(
            _error(
                "AMENDMENT_EFFECT_UNSPECIFIED",
                "affected_cases",
                "At least one affected case, outcome, or analysis must be identified",
            )
        )

    if parameter_sets is None:
        warnings.append(
            {
                "code": "PARAMETER_SETS_NOT_PROVIDED",
                "message": "Amendment lineage digests were not cross-checked against parameter-set objects.",
            }
        )
    else:
        predecessor = parameter_sets.get(str(predecessor_id))
        successor = parameter_sets.get(str(successor_id))
        if predecessor is None or successor is None:
            errors.append(
                _error(
                    "AMENDMENT_PARAMETER_SET_MISSING",
                    "predecessor_parameter_set_id",
                    "Predecessor or successor parameter set is missing",
                )
            )
        else:
            if value.get("predecessor_parameter_set_sha256") != study_parameter_set_sha256(predecessor):
                errors.append(
                    _error(
                        "PREDECESSOR_DIGEST_MISMATCH",
                        "predecessor_parameter_set_sha256",
                        "Predecessor digest does not match object",
                    )
                )
            if value.get("successor_parameter_set_sha256") != study_parameter_set_sha256(successor):
                errors.append(
                    _error(
                        "SUCCESSOR_DIGEST_MISMATCH",
                        "successor_parameter_set_sha256",
                        "Successor digest does not match object",
                    )
                )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "amendment_id": value.get("amendment_id"),
        "canonical_sha256": expected_hash,
        "boundary": AMENDMENT_BOUNDARY,
    }


def validate_case_manifest_file(path: Path) -> dict[str, Any]:
    return validate_case_manifest(load_validation_record(path))


def validate_study_parameter_set_file(path: Path, *, case_manifest_dir: Path) -> dict[str, Any]:
    return validate_study_parameter_set(
        load_validation_record(path), case_manifests=load_case_manifests(case_manifest_dir)
    )


def validate_protocol_amendment_file(
    path: Path, *, parameter_sets: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    return validate_protocol_amendment(load_validation_record(path), parameter_sets=parameter_sets)
