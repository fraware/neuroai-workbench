from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .resource_loader import read_resource_bytes
from .util import canonical_json_bytes
from .validation import validate_assessment

BLANK = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def migrate_v4_1_2(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("assessment_metadata", {}).get("instrument_version") != "v4.1.2":
        raise ValueError("Source instrument_version must be v4.1.2")
    output = copy.deepcopy(source)
    assessment_id = source["assessment_metadata"]["assessment_id"]
    output["assessment_metadata"]["instrument_version"] = "v4.2"
    output["assessment_metadata"]["migrated_from_version"] = "v4.1.2"
    output["assessment_metadata"]["migration_id"] = f"MIG-{assessment_id}-v4.2"
    output["deployment_state"] = copy.deepcopy(BLANK["deployment_state"])
    for claim in output["claim_register"]:
        claim.update({
            "claimant_record_type": "ASSESSOR-CONTROLLED CLAIM",
            "verbatim_text": claim.get("claim_text", ""),
            "source_location": "See linked evidence object.",
            "propagation_history": [],
            "current_applicability": "CURRENT ASSESSED SCOPE",
            "future_use_gate": "REOPENING REQUIRED",
        })
    for evidence in output["evidence_register"]:
        evidence.update({
            "access_state": "PUBLICLY RETRIEVED" if evidence.get("evidence_state") != "PRIVATE EVIDENCE REQUIRED" else "KNOWN PRIVATE RECORD REQUIRED",
            "known_holder": "",
            "retrieval_or_authorization_required": "Resolve controlled access when required.",
            "reproducibility_tier": "R1 FIGURES",
        })
    output["configuration_relationships"] = []
    output["source_version_relationships"] = []
    output["provenance_discrepancies"] = []
    output["configuration_epochs"] = [{
        "epoch_id": "EPOCH-01",
        "configuration_id": output["system_profile"]["configuration_id"],
        "start": output["system_profile"].get("configuration_effective_period", "UNRESOLVED"),
        "end": "OPEN OR UNRESOLVED",
        "material_changes": ["Migration did not infer additional epochs."],
        "endpoint_ids": [row["endpoint_id"] for row in output["endpoint_register"]],
        "evidence_ids": [row["evidence_id"] for row in output["evidence_register"]],
        "limitations": ["Resolve material epochs from controlled records."],
    }]
    output["denominator_register"] = []
    for index, endpoint in enumerate(output["endpoint_register"], 1):
        denominator_id = f"DEN-{index:02d}"
        output["denominator_register"].append({
            "denominator_id": denominator_id,
            "denominator_type": "ENDPOINT-SPECIFIC",
            "population_definition": endpoint.get("population", "UNRESOLVED"),
            "value_state": "UNRESOLVED",
            "value": "UNRESOLVED",
            "time_window": endpoint.get("observation_window", ""),
            "configuration_id": endpoint.get("system_and_version", output["system_profile"]["configuration_id"]),
            "evidence_ids": endpoint.get("source_evidence_ids", []),
            "transition_from_ids": [],
            "limitations": ["Migration does not invent a denominator."],
        })
        endpoint.update({
            "metric_direction": "UNRESOLVED",
            "aggregation_level": "UNRESOLVED",
            "statistic_type": "UNRESOLVED",
            "derivation": "Preserve source result.",
            "denominator_ids": [denominator_id],
            "protocol_state": "UNRESOLVED",
            "ground_truth_state": "UNRESOLVED",
            "correction_timing": "UNRESOLVED",
            "configuration_epoch_ids": ["EPOCH-01"],
        })
    for finding in output["requirement_findings"]:
        finding.update({
            "evidence_access_state": "NOT APPLICABLE" if finding["applicability"] == "NOT APPLICABLE WITH RATIONALE" else "EVALUATION NOT EXECUTED" if finding["finding_status"] == "NOT ASSESSED" else "CONTROLLED PUBLIC EXTRACT",
            "future_use_gate_status": "REOPENING REQUIRED" if finding["applicability"] == "NOT APPLICABLE WITH RATIONALE" else "CURRENTLY APPLICABLE",
            "historical_finding_preserved": True,
        })
    for gap in output["gap_register"]:
        gap["evidence_access_state"] = "KNOWN PRIVATE RECORD REQUIRED"
    legacy = output.pop("bounded_decision")
    output["legacy_bounded_decision"] = copy.deepcopy(legacy)
    for key in [
        "functional_contribution_register", "independence_assessment", "latency_register",
        "control_authority_register", "operational_burden_register", "update_lineage_register",
        "participant_authority_register", "postmarket_exposure_register", "reproducibility_register",
    ]:
        output[key] = []
    output["decision_register"] = [
        {
            "decision_id": legacy["decision_id"] + "-CLAIM",
            "decision_object_type": "CLAIM ADJUDICATION",
            "authority": "Migrated historical assessor",
            "authority_basis": "Historical v4.1.2 bounded decision",
            "decision_state": "PARTIALLY SUPPORTED",
            "scope": legacy.get("scope", {}),
            "evidence_threshold": "Historical bounded decision",
            "evidence_ids": [row["evidence_id"] for row in output["evidence_register"]],
            "strongest_supported_claim": legacy.get("strongest_supported_claim", ""),
            "prohibited_inferences": legacy.get("prohibited_inferences", []),
            "conditions": legacy.get("p1_conditions", []),
            "expiry": legacy.get("expiry", "NOT SET"),
            "reopening_triggers": legacy.get("reopening_triggers", []),
            "linked_legacy_decision_id": legacy["decision_id"],
            "limitations": ["Generic migration; review typed decision state."],
        },
        {
            "decision_id": legacy["decision_id"] + "-CONF",
            "decision_object_type": "CONFORMANCE DECISION",
            "authority": "No competent conformance authority assigned",
            "authority_basis": "Migration-generated decision separation",
            "decision_state": "NO CONFORMANCE DECISION — BLOCKED",
            "scope": legacy.get("scope", {}),
            "evidence_threshold": "All applicable P0 evidence and target-level conditions",
            "evidence_ids": [],
            "strongest_supported_claim": "No v4.2 conformance decision has been made.",
            "prohibited_inferences": ["Historical claim support does not establish conformance."],
            "conditions": legacy.get("p0_nonconformities", []) + legacy.get("p1_conditions", []),
            "expiry": "NOT SET",
            "reopening_triggers": legacy.get("reopening_triggers", []),
            "linked_legacy_decision_id": legacy["decision_id"],
            "limitations": ["Independent review required."],
        },
    ]
    output["migration_provenance"] = {
        "migration_id": f"MIG-{assessment_id}-v4.2",
        "source_instrument_version": "v4.1.2",
        "target_instrument_version": "v4.2",
        "source_assessment_id": assessment_id,
        "source_sha256": _sha(source),
        "historical_projection_sha256": _sha(source),
        "migration_ruleset": "MIGRATION-v4.1.2-to-v4.2",
        "migration_date": "2026-07-28",
        "preservation_verified": True,
        "migration_warnings": ["Generic migration leaves calibrated structured objects unresolved."],
    }
    output["assessment_notes"] = source.get("assessment_notes", []) + ["Migrated additively to v4.2."]
    report = validate_assessment(output)
    if not report.valid:
        raise ValueError(json.dumps(report.to_dict(), ensure_ascii=False))
    return output


def migrate_file(source: Path, output: Path) -> dict[str, Any]:
    migrated = migrate_v4_1_2(json.loads(source.read_text(encoding="utf-8")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return migrated
