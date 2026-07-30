from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .resource_loader import read_resource_bytes
from .util import canonical_json_bytes, sha256_bytes
from .validation import validate_assessment

PROGRAMME_FORMAT = "UNESCO_NEUROAI_COMPLETED_ASSESSMENT"
ADAPTER_VERSION = "1"


@dataclass(frozen=True)
class AdapterResult:
    assessment: dict[str, Any]
    report: dict[str, Any]


def detect_programme_assessment(value: Any) -> bool:
    return isinstance(value, dict) and all(
        key in value
        for key in ("metadata", "system", "claims", "evidence_register", "requirement_findings", "decisions")
    )


def _text(value: Any, default: str = "UNRESOLVED") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _list_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_text(item, "") for item in value if _text(item, "")]
    return [_text(value, "")]


def _component_type(raw: str) -> str:
    text = raw.lower()
    if "software" in text:
        return "SOFTWARE"
    if "processor" in text or "compute" in text or "hardware" in text or "implant" in text or "camera" in text:
        return "HARDWARE"
    if "algorithm" in text or "model" in text:
        return "MODEL"
    if "accessory" in text or "glasses" in text:
        return "ACCESSORY"
    if "procedure" in text or "rehabilitation" in text or "training" in text or "clinical" in text:
        return "PROCEDURE"
    if "data" in text:
        return "DATA PIPELINE"
    return "OTHER"


def _claim_type(claim: dict[str, Any]) -> str:
    text = f"{claim.get('claim', '')} {claim.get('claim_state', '')}".lower()
    if any(word in text for word in ("ce mark", "authorization", "hud", "hde", "regulatory")):
        return "AUTHORIZATION"
    if any(word in text for word in ("safety", "adverse", "harm")):
        return "SAFETY"
    if any(word in text for word in ("accuracy", "performance", "improvement", "logmar", "rate")):
        return "PERFORMANCE"
    if any(word in text for word in ("commercial", "implantation", "launch", "deployment")):
        return "DEPLOYMENT"
    if any(word in text for word in ("participant", "home use", "experience")):
        return "PARTICIPANT EXPERIENCE"
    if any(word in text for word in ("effective", "benefit", "restore", "vision")):
        return "EFFECTIVENESS"
    return "CAPABILITY"


def _claim_status(state: str) -> str:
    text = state.upper().strip()
    if not text:
        return "NOT REVIEWABLE"
    if any(token in text for token in ("CONTRADICT", "REJECTED")):
        return "CONTRADICTED"
    if any(token in text for token in ("UNSUPPORTED", "NOT_SUPPORTED")):
        return "UNSUPPORTED"
    if any(token in text for token in ("WITHDRAWN", "SUPERSEDED")):
        return "WITHDRAWN OR SUPERSEDED"
    if any(token in text for token in ("UNRESOLVED", "NOT_REVIEWABLE", "INACCESSIBLE", "UNKNOWN")):
        return "NOT REVIEWABLE"
    # Announcement / planned states before generic "supported" tokens so company
    # announcements are not over-mapped to fully supported within scope.
    if any(token in text for token in ("PARTIAL", "ANNOUNCEMENT", "PLANNED", "EXPECTED", "ROADMAP")):
        return "PARTIALLY SUPPORTED"
    if any(token in text for token in ("SUPPORTED", "CORROBORATED", "ESTABLISHED")):
        return "SUPPORTED WITHIN BOUNDED SCOPE"
    # Novel or unmatched programme claim_state strings stay unresolved.
    return "NOT REVIEWABLE"


def _claimant_record_type(claim: dict[str, Any]) -> str:
    state = _text(claim.get("claim_state"), "").upper()
    if "COMPANY" in state or "ANNOUNCEMENT" in state:
        return "CORPORATE COMMUNICATION"
    if "REGULATOR" in state or "AUTHORITY" in state:
        return "REGULATORY AUTHORITY"
    if "PARTICIPANT" in state:
        return "PARTICIPANT STATEMENT"
    return "ASSESSOR-CONTROLLED CLAIM"


def _evidence_type(raw: str) -> str:
    text = raw.upper()
    if "PEER_REVIEW" in text or "CLINICAL_STUDY" in text:
        return "PEER-REVIEWED STUDY"
    if "PREPRINT" in text:
        return "PREPRINT"
    if "TRIAL_REGISTRY" in text:
        return "TRIAL REGISTRY"
    if any(token in text for token in ("REGULATORY", "CERTIFICATE", "FDA", "CE_MARK")):
        return "REGULATORY AUTHORIZATION"
    if any(token in text for token in ("SAFETY", "VIGILANCE", "ADVERSE")):
        return "SAFETY OR VIGILANCE RECORD"
    if any(token in text for token in ("PARTICIPANT", "CAREGIVER")):
        return "PARTICIPANT OR CAREGIVER EVIDENCE"
    if any(token in text for token in ("MANUAL", "TECHNICAL", "METHOD", "REPOSITORY")):
        return "METHOD OR TECHNICAL DOCUMENT"
    if any(token in text for token in ("COMMERCIAL", "COMPANY", "MEDIA", "ANNOUNCEMENT")):
        return "COMMERCIAL CLAIM"
    return "OTHER"


def _evidence_state(record: dict[str, Any]) -> str:
    text = f"{record.get('evidence_class', '')} {record.get('publication_state', '')}".upper()
    if "PEER_REVIEW" in text or "PUBLISHED_PRIMARY" in text:
        return "PEER-REVIEWED PUBLICATION"
    if "TRIAL_REGISTRY" in text or "REGISTRY" in text:
        return "TRIAL REGISTRY"
    if "PREPRINT" in text:
        return "PREPRINT"
    if "REGULATORY" in text or "CERTIFICATE" in text:
        return "REGULATORY RECORD"
    if "PATENT" in text:
        return "PATENT RECORD"
    if "PARTICIPANT" in text or "CAREGIVER" in text:
        return "PARTICIPANT OR CAREGIVER EVIDENCE"
    if "COMPANY" in text or "MEDIA" in text or "COMMERCIAL" in text:
        return "COMMERCIAL OR MEDIA CLAIM"
    return "PRIMARY SOURCE VERIFIED"


def _access_state(record: dict[str, Any]) -> str:
    text = _text(record.get("retrieval_state"), "").upper()
    if "METADATA" in text and "CONTENT" not in text:
        return "PUBLIC METADATA ONLY"
    if any(token in text for token in ("RETRIEVED", "CONTENT", "FULL")):
        return "PUBLICLY RETRIEVED"
    if "PRIVATE" in text:
        return "KNOWN PRIVATE RECORD REQUIRED"
    return "CONTROLLED PUBLIC EXTRACT"


def _primary_state(raw: str) -> str:
    text = raw.upper()
    if any(token in text for token in ("PRIMARY", "REGISTRY", "REGULATORY", "MANUAL")):
        return "PRIMARY"
    if any(token in text for token in ("MEDIA", "REVIEW", "SECONDARY")):
        return "SECONDARY"
    return "UNKNOWN"


def _finding_access_state(raw: str, applicability: str, status: str) -> str:
    if applicability.startswith("NOT APPLICABLE"):
        return "NOT APPLICABLE"
    text = raw.upper()
    if "REGULATOR" in text:
        return "KNOWN REGULATOR-HELD RECORD"
    if "MANUFACTURER" in text:
        return "KNOWN MANUFACTURER-HELD RECORD"
    if "SPONSOR" in text:
        return "KNOWN SPONSOR-HELD RECORD"
    if "SITE" in text:
        return "KNOWN SITE-HELD RECORD"
    if "NOT PUBLIC" in text or "REQUIRED EVIDENCE" in text:
        return "KNOWN PRIVATE RECORD REQUIRED"
    if "METADATA" in text:
        return "PUBLIC METADATA ONLY"
    if "PUBLIC" in text and status == "PASS":
        return "PUBLICLY RETRIEVED"
    if "PUBLIC" in text:
        return "CONTROLLED PUBLIC EXTRACT"
    return "EXISTENCE UNKNOWN"


def _gate_state(raw: str, applicability: str) -> str:
    if applicability.startswith("NOT APPLICABLE"):
        return "CURRENTLY INAPPLICABLE"
    text = raw.upper()
    if "PROHIBITED" in text:
        return "PROHIBITED"
    if "OPEN" in text or "REOPEN" in text or "CONDITION" in text:
        return "REOPENING REQUIRED"
    if "CURRENT" in text:
        return "CURRENTLY APPLICABLE"
    return "UNRESOLVED"


def _decision_type(raw: str) -> str:
    text = raw.upper()
    if "CONFORMANCE" in text:
        return "CONFORMANCE DECISION"
    if "REGULATORY" in text or "AUTHORIZATION" in text:
        return "LEGAL OR REGULATORY AUTHORIZATION"
    if "REOPEN" in text or "OBSERVATORY" in text:
        return "REOPENING DECISION"
    return "CLAIM ADJUDICATION"


def _decision_state(record: dict[str, Any]) -> str:
    kind = _decision_type(_text(record.get("decision_class"), ""))
    decision = _text(record.get("decision"), "").upper()
    if kind == "CONFORMANCE DECISION":
        if "NOT_ESTABLISHED" in decision or "BLOCK" in decision:
            return "NO CONFORMANCE DECISION — BLOCKED"
        if "CONDITIONAL" in decision:
            return "CONDITIONAL CONFORMANCE"
        return "CONFORMS FOR BOUNDED SCOPE"
    if kind == "LEGAL OR REGULATORY AUTHORIZATION":
        if "NOT_AUTH" in decision or "HUD_ONLY" in decision:
            return "AUTHORIZATION NOT ASSESSED"
        return "AUTHORIZED WITHIN BOUNDED SCOPE"
    if kind == "REOPENING DECISION":
        return "REOPENED"
    if "UNSUPPORTED" in decision:
        return "UNSUPPORTED"
    if "PARTIAL" in decision or "BOUNDED" in decision:
        return "SUPPORTED WITHIN BOUNDED SCOPE"
    return "PARTIALLY SUPPORTED"


def _classification(system: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    rationale = "; ".join(f"{key}={value}" for key, value in raw.items() if key != "risk_escalators")
    mapping = {
        "sc_01": ["Implanted"],
        "sc_02": ["Record", "Stimulate/modulate"],
        "sc_03": ["Therapeutic", "Assistive"],
        "sc_04": ["Direct neural", "Multimodal"],
        "sc_05": ["Signal processing"],
        "sc_06": ["Longitudinal", "Permanent implant"],
        "sc_07": ["Clinically burdensome", "Partially irreversible"],
        "sc_08": ["User initiated", "Clinician supervised"],
        "sc_09": ["Clinical", "Home/community"],
        "sc_10": ["Person with disability", "Older person"],
        "sc_11": ["Controlled clinical", "Authorized use"],
        "sc_12": ["Offline/local", "Connected"],
    }
    return {
        key: {
            "values": values,
            "certainty": "PROVISIONAL",
            "rationale": f"Adapter projection from programme classification. {rationale}"[:2000],
        }
        for key, values in mapping.items()
    }


def _preservation_checks(source: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    """Independent mechanical preservation checks. Passing does not re-appraise evidence."""
    source_findings = [item for item in source.get("requirement_findings", []) if isinstance(item, dict)]
    native_findings = [item for item in assessment.get("requirement_findings", []) if isinstance(item, dict)]
    source_ids = [_text(item.get("requirement_id"), "") for item in source_findings]
    native_ids = [_text(item.get("requirement_id"), "") for item in native_findings]
    source_status = {
        _text(item.get("requirement_id"), ""): _text(item.get("status"), "NOT ASSESSED") for item in source_findings
    }
    native_status = {
        _text(item.get("requirement_id"), ""): _text(item.get("finding_status"), "NOT ASSESSED")
        for item in native_findings
    }
    status_mismatches = sorted(
        req_id for req_id, status in source_status.items() if native_status.get(req_id) != status
    )
    source_fail = sum(1 for status in source_status.values() if status == "FAIL")
    native_fail = sum(1 for status in native_status.values() if status == "FAIL")
    checks = {
        "requirement_ids_count_78": len(native_ids) == 78 and len(source_ids) == 78,
        "requirement_ids_unique": len(native_ids) == len(set(native_ids)) and len(source_ids) == len(set(source_ids)),
        "requirement_ids_equal": set(native_ids) == set(source_ids),
        "finding_status_preserved": not status_mismatches,
        "no_missing_evidence_converted_to_fail": native_fail == source_fail,
        "claims_count_preserved": len(assessment.get("claim_register", [])) == len(source.get("claims", [])),
        "evidence_count_preserved": len(assessment.get("evidence_register", []))
        == len(source.get("evidence_register", [])),
        "gaps_count_preserved": len(assessment.get("gap_register", [])) == len(source.get("gaps_and_requests", [])),
        "decisions_count_preserved": len(assessment.get("decision_register", [])) == len(source.get("decisions", [])),
        "historical_finding_flag_set": all(
            item.get("historical_finding_preserved") is True for item in native_findings
        ),
    }
    return {
        "checks": checks,
        "preservation_verified": all(checks.values()),
        "status_mismatches": status_mismatches,
        "source_fail_count": source_fail,
        "native_fail_count": native_fail,
        "boundary": (
            "preservation_verified is a mechanical reconciliation of identifiers and finding statuses; "
            "it does not establish scientific truth, authorization, conformance, or independent re-appraisal."
        ),
    }


def adapt_programme_assessment(value: dict[str, Any]) -> AdapterResult:
    if not detect_programme_assessment(value):
        raise ValueError("Input does not match the supported programme completed-assessment format")

    source_sha = sha256_bytes(canonical_json_bytes(value))
    blank = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
    assessment = copy.deepcopy(blank)
    metadata = value.get("metadata", {})
    system = value.get("system", {})
    classification = value.get("classification", {})
    sources = {item.get("source_id"): item for item in value.get("sources", []) if isinstance(item, dict)}

    assessment["assessment_metadata"] = {
        "assessment_id": _text(metadata.get("assessment_id"), "ASSESSMENT-ADAPTED"),
        "instrument_version": "v4.2",
        "title": _text(metadata.get("title"), "Adapted programme assessment"),
        "assessment_status": "CLOSED",
        "assessment_purpose": "Preserve and operationalize a completed programme public-evidence assessment in the native v4.2 workbench object model.",
        "evidence_cutoff": _text(metadata.get("evidence_cutoff"), "2026-07-29"),
        "evidence_freeze_id": _text(metadata.get("evidence_freeze_id"), ""),
        "jurisdictions": list(system.get("regulatory_state", {}).keys())
        if isinstance(system.get("regulatory_state"), dict)
        else [],
        "assessors": [
            {
                "actor_id": "ASSESSOR-PROGRAMME-RECORD",
                "name_or_role": "Programme-controlled assessment author",
                "organization": "UNRESOLVED",
                "responsibility": "Prepared the bounded public-evidence assessment represented by the source record.",
                "accountability_state": "SOURCE RECORD ONLY",
                "source_or_basis": _text(metadata.get("assessment_version"), "PROGRAMME SOURCE"),
            }
        ],
        "public_private_state": "PUBLIC EVIDENCE ONLY",
        "source_corpus_version": _text(metadata.get("assessment_version"), "PROGRAMME SOURCE"),
        "limitations": [
            _text(metadata.get("boundary"), "No broader authority is created by adaptation."),
            "Adapter validation confirms structural preservation only; it does not re-appraise the underlying evidence.",
        ],
    }

    components = []
    for component in value.get("components", []):
        components.append(
            {
                "component_id": _text(component.get("component_id"), "COMPONENT-UNASSIGNED"),
                "component_type": _component_type(_text(component.get("type"), "")),
                "name": _text(component.get("name"), "UNRESOLVED"),
                "version": _text(component.get("status"), "UNRESOLVED"),
                "effective_period": _text(metadata.get("evidence_cutoff"), "UNRESOLVED"),
                "supplier_or_owner": _text(system.get("developer_owner"), "UNRESOLVED"),
                "dependency": _text(component.get("identity"), "UNRESOLVED"),
                "evidence_ids": _list_text(component.get("evidence_ids")),
            }
        )

    actors = []
    for actor in value.get("actors", []):
        roles = _list_text(actor.get("roles"))
        actors.append(
            {
                "actor_id": _text(actor.get("actor_id"), "ACTOR-UNASSIGNED"),
                "name_or_role": _text(actor.get("actor"), "UNRESOLVED"),
                "organization": _text(actor.get("actor"), "UNRESOLVED"),
                "responsibility": "; ".join(roles) or "UNRESOLVED",
                "accountability_state": "PUBLIC RECORD PARTIAL",
                "source_or_basis": ", ".join(_list_text(actor.get("evidence_ids"))),
            }
        )

    config_id = f"CONFIG-{_text(metadata.get('assessment_id'), 'ADAPTED')}"
    assessment["system_profile"] = {
        "system_id": f"SYSTEM-{_text(metadata.get('assessment_id'), 'ADAPTED')}",
        "system_name": _text(system.get("system_name"), "UNRESOLVED"),
        "system_family": _text(system.get("system_class"), "UNRESOLVED"),
        "configuration_id": config_id,
        "configuration_effective_period": f"Public-evidence boundary through {_text(metadata.get('evidence_cutoff'), 'UNRESOLVED')}",
        "components": components,
        "classification": _classification(system, classification),
        "intended_uses": [_text(system.get("function"), "UNRESOLVED")],
        "excluded_uses": _list_text(value.get("prohibited_inferences"))
        or ["Uses outside the assessed public-evidence scope"],
        "populations": [_text(system.get("intended_population_public_evidence"), "UNRESOLVED")],
        "contexts": [_text(system.get("setting"), "UNRESOLVED")],
        "accountable_actors": actors,
        "affected_third_parties": [],
        "lifecycle_state": _text(classification.get("lifecycle_state"), "UNRESOLVED"),
        "material_dependencies": [_text(system.get("operational_independence"), "UNRESOLVED")],
        "known_change_history": [
            f"Adapted from programme assessment {_text(metadata.get('assessment_version'), 'UNRESOLVED')} with source SHA-256 {source_sha}."
        ],
        "unresolved_identity_questions": [
            "The adapter preserves the programme configuration boundary; unresolved exact commercial configuration questions remain unresolved."
        ],
    }

    triggered = {str(item).split()[0] for item in _list_text(classification.get("risk_escalators"))}
    assessment["profile_selection"] = {
        "initial_profile_id": "AP-3",
        "triggered_escalators": [
            {
                "escalator_id": f"ESC-{index:02d}",
                "triggered": f"ESC-{index:02d}" in triggered,
                "rationale": "Projected from programme risk-escalator record.",
            }
            for index in range(1, 9)
        ],
        "final_profile_id": "AP-3",
        "target_conformance_level": "CL-4",
        "mandatory_modules": [f"NK-{index:02d}" for index in range(1, 14)],
        "additional_gates": ["Participant-version evidence", "Incident and continuity evidence", "Long-term follow-up"],
        "selection_rationale": _text(metadata.get("target_profile"), "AP-3 selected for implanted clinical system."),
        "unresolved_profile_questions": [],
    }

    assessment["deployment_state"] = {
        "current_states": ["CLINICAL INVESTIGATIONAL", "CLINICAL AUTHORIZED", "HOME OR COMMUNITY"],
        "future_use_gates": [
            {
                "state": "CONSUMER",
                "gate_status": "REOPENING REQUIRED",
                "rationale": "Material scope expansion requires reassessment.",
            },
            {
                "state": "WORKPLACE",
                "gate_status": "REOPENING REQUIRED",
                "rationale": "Material scope expansion requires reassessment.",
            },
        ],
        "modifiers": [_text(classification.get("deployment_state"), "UNRESOLVED")],
    }

    assessment["claim_register"] = []
    for claim in value.get("claims", []):
        evidence_ids = _list_text(claim.get("evidence_ids"))
        assessment["claim_register"].append(
            {
                "claim_id": _text(claim.get("claim_id"), "CLAIM-UNASSIGNED"),
                "claim_text": _text(claim.get("claim"), "UNRESOLVED"),
                "claimant": "Programme source record(s): " + ", ".join(evidence_ids),
                "claim_type": _claim_type(claim),
                "claimed_scope": {
                    "system_and_version": _text(system.get("configuration_boundary"), "UNRESOLVED"),
                    "population": _text(system.get("intended_population_public_evidence"), "UNRESOLVED"),
                    "context": _text(system.get("setting"), "UNRESOLVED"),
                    "endpoint": "See linked evidence and endpoint registers",
                    "observation_window": f"Through {_text(metadata.get('evidence_cutoff'), 'UNRESOLVED')}",
                    "jurisdiction": ", ".join(assessment["assessment_metadata"]["jurisdictions"]),
                },
                "evidence_ids": evidence_ids,
                "claim_status": _claim_status(_text(claim.get("claim_state"), "")),
                "strongest_supported_claim": _text(claim.get("strongest_supportable_claim"), "UNRESOLVED"),
                "prohibited_inferences": [
                    _text(claim.get("prohibited_inference"), "No broader inference is permitted.")
                ],
                "limitations": [_text(claim.get("prohibited_inference"), "Bounded to linked public evidence.")],
                "required_evidence_to_change_status": [],
                "claimant_record_type": _claimant_record_type(claim),
                "verbatim_text": _text(claim.get("claim"), "UNRESOLVED"),
                "source_location": ", ".join(evidence_ids),
                "propagation_history": [],
                "current_applicability": f"Applicable to the programme assessment through {_text(metadata.get('evidence_cutoff'), 'UNRESOLVED')}",
                "future_use_gate": "REOPENING REQUIRED"
                if "PLANNED" in _text(claim.get("claim_state"), "").upper()
                else "CURRENTLY APPLICABLE",
            }
        )

    assessment["evidence_register"] = []
    for record in value.get("evidence_register", []):
        source_ids = _list_text(record.get("source_ids"))
        source_records = [sources[item] for item in source_ids if item in sources]
        source_text = "; ".join(
            f"{item.get('publisher', 'UNRESOLVED')}: {item.get('title', item.get('source_id', 'UNRESOLVED'))}"
            for item in source_records
        ) or ", ".join(source_ids)
        url = next((item.get("url") for item in source_records if item.get("url")), "")
        assessment["evidence_register"].append(
            {
                "evidence_id": _text(record.get("evidence_id"), "EVIDENCE-UNASSIGNED"),
                "evidence_type": _evidence_type(_text(record.get("evidence_class"), "")),
                "title": _text(record.get("title"), "UNRESOLVED"),
                "source": source_text or "UNRESOLVED",
                "url_or_path": url,
                "identifiers": {"programme_source_ids": ",".join(source_ids)},
                "evidence_state": _evidence_state(record),
                "system_and_version": _text(system.get("configuration_boundary"), "UNRESOLVED"),
                "population": _text(system.get("intended_population_public_evidence"), "UNRESOLVED"),
                "function": _text(system.get("function"), "UNRESOLVED"),
                "endpoint": _text(record.get("supports"), "UNRESOLVED"),
                "observation_window": f"Evidence state through {_text(record.get('evidence_cutoff'), metadata.get('evidence_cutoff'))}",
                "controls_or_comparators": "See source record; no additional comparator is inferred by the adapter.",
                "result_or_record_content": _text(record.get("supports"), "UNRESOLVED"),
                "publication_or_record_state": _text(record.get("publication_state"), "UNRESOLVED"),
                "source_retrieval_state": _text(record.get("retrieval_state"), "UNRESOLVED"),
                "primary_or_secondary": _primary_state(_text(record.get("evidence_class"), "")),
                "strongest_supported_claim": _text(record.get("supports"), "UNRESOLVED"),
                "prohibited_inferences": [_text(record.get("limitation"), "No broader inference is permitted.")],
                "limitations": [_text(record.get("limitation"), "UNRESOLVED")],
                "access_state": _access_state(record),
                "known_holder": source_text or "UNRESOLVED",
                "retrieval_or_authorization_required": _text(
                    record.get("limitation"), "No additional retrieval requirement recorded."
                ),
                "reproducibility_tier": "R0 NONE",
            }
        )

    assessment["denominator_register"] = [
        {
            "denominator_id": _text(item.get("denominator_id"), "DENOMINATOR-UNASSIGNED"),
            "denominator_type": _text(item.get("unit"), "OTHER"),
            "population_definition": _text(item.get("name"), "UNRESOLVED"),
            "value_state": "REPORTED PUBLIC VALUE",
            "value": item.get("value"),
            "time_window": _text(item.get("timepoint"), "UNRESOLVED"),
            "configuration_id": config_id,
            "evidence_ids": _list_text(item.get("evidence_ids")),
            "transition_from_ids": [],
            "limitations": [],
        }
        for item in value.get("denominators", [])
    ]

    assessment["endpoint_register"] = []
    for item in value.get("endpoints", []):
        result = _text(item.get("result"), "UNRESOLVED")
        endpoint_class = _text(item.get("endpoint_class"), "UNRESOLVED")
        statistic = "PROPORTION" if any(token in result for token in ("%", "/")) else "OTHER"
        assessment["endpoint_register"].append(
            {
                "endpoint_id": _text(item.get("endpoint_id"), "ENDPOINT-UNASSIGNED"),
                "population": _text(system.get("intended_population_public_evidence"), "UNRESOLVED"),
                "system_and_version": _text(system.get("configuration_boundary"), "UNRESOLVED"),
                "endpoint": _text(item.get("endpoint"), "UNRESOLVED"),
                "measurement_method": endpoint_class,
                "observation_window": _text(item.get("boundary"), "See source evidence"),
                "comparator_or_control": "Baseline or comparator defined by the linked source; the adapter introduces no new comparator.",
                "result": result,
                "uncertainty": result if "CI" in result or "confidence" in result.lower() else "UNRESOLVED",
                "null_adverse_or_burden_state": "No absence-of-harm inference is introduced.",
                "source_evidence_ids": _list_text(item.get("evidence_ids")),
                "transfer_limitations": [
                    _text(item.get("boundary"), "Bounded to the reported endpoint and denominator.")
                ],
                "metric_direction": "UNRESOLVED",
                "aggregation_level": "COHORT",
                "statistic_type": statistic,
                "derivation": endpoint_class,
                "denominator_ids": _list_text(item.get("denominator_ids")),
                "protocol_state": "PUBLICATION-DERIVED",
                "ground_truth_state": "EXTERNAL OBSERVED TARGET",
                "correction_timing": "NO CORRECTION",
                "configuration_epoch_ids": [],
            }
        )

    assessment["requirement_findings"] = []
    for item in value.get("requirement_findings", []):
        applicability = _text(item.get("applicability"), "UNCERTAIN — RESOLUTION REQUIRED")
        if applicability == "NOT APPLICABLE":
            applicability = "NOT APPLICABLE WITH RATIONALE"
        status = _text(item.get("status"), "NOT ASSESSED")
        gap_action = _text(item.get("gap_action"), "")
        assessment["requirement_findings"].append(
            {
                "requirement_id": _text(item.get("requirement_id"), ""),
                "module_id": _text(item.get("module_id"), ""),
                "priority": _text(item.get("priority"), "P2"),
                "applicability": applicability,
                "applicability_rationale": _text(item.get("applicability_rationale"), "UNRESOLVED"),
                "finding_status": status,
                "evidence_ids": _list_text(item.get("evidence_ids")),
                "finding": _text(item.get("finding"), "UNRESOLVED"),
                "strongest_supported_claim": _text(item.get("strongest_supportable_claim"), "UNRESOLVED"),
                "prohibited_inferences": [
                    _text(item.get("prohibited_inference"), "No broader inference is permitted.")
                ],
                "evidence_gap": gap_action if status != "PASS" else "",
                "required_action": gap_action,
                "owner": _text(item.get("owner"), "UNASSIGNED"),
                "target_date": None,
                "reassessment_trigger": _text(
                    item.get("reopening_trigger"), "Material evidence or configuration change."
                ),
                "evidence_access_state": _finding_access_state(
                    _text(item.get("access_state"), ""), applicability, status
                ),
                "future_use_gate_status": _gate_state(_text(item.get("future_gate"), ""), applicability),
                "historical_finding_preserved": True,
            }
        )

    assessment["gap_register"] = [
        {
            "gap_id": _text(item.get("gap_id"), "GAP-UNASSIGNED"),
            "linked_requirement_ids": [],
            "linked_claim_ids": [],
            "priority": _text(item.get("priority"), "P2"),
            "missing_evidence": _text(item.get("missing_evidence"), "UNRESOLVED"),
            "request_text": _text(item.get("required_action"), "UNRESOLVED"),
            "closure_criterion": _text(item.get("closure_test"), "UNRESOLVED"),
            "responsible_actor": _text(item.get("owner"), "UNASSIGNED"),
            "state": _text(item.get("state"), "OPEN")
            if _text(item.get("state"), "OPEN")
            in {"OPEN", "REQUEST READY", "REQUEST ISSUED", "PARTIAL RESPONSE", "CLOSED", "INAPPLICABLE"}
            else "OPEN",
            "response_evidence_ids": [],
            "remaining_limitation": _text(item.get("missing_evidence"), "UNRESOLVED"),
            "evidence_access_state": "KNOWN PRIVATE RECORD REQUIRED"
            if _text(item.get("priority"), "") == "P0"
            else "EXISTENCE UNKNOWN",
        }
        for item in value.get("gaps_and_requests", [])
    ]

    all_evidence_ids = [item["evidence_id"] for item in assessment["evidence_register"]]
    assessment["decision_register"] = []
    for item in value.get("decisions", []):
        assessment["decision_register"].append(
            {
                "decision_id": _text(item.get("decision_id"), "DECISION-UNASSIGNED"),
                "decision_object_type": _decision_type(_text(item.get("decision_class"), "")),
                "authority": "Programme assessment author under controlled public-evidence scope",
                "authority_basis": "Completed programme assessment record; no regulatory, clinical, or certification authority is inferred.",
                "decision_state": _decision_state(item),
                "scope": {"description": _text(item.get("scope"), "UNRESOLVED")},
                "evidence_threshold": "Bounded public-evidence threshold defined by the source assessment.",
                "evidence_ids": all_evidence_ids,
                "strongest_supported_claim": _text(item.get("determination"), "UNRESOLVED"),
                "prohibited_inferences": _list_text(value.get("prohibited_inferences")),
                "conditions": _list_text(item.get("conditions")),
                "expiry": _text(item.get("expiry"), "REOPEN ON MATERIAL CHANGE"),
                "reopening_triggers": _list_text(value.get("reopening_triggers"))
                or ["Material system, evidence, population, context, or lifecycle change."],
                "limitations": [
                    _text(metadata.get("boundary"), "No broader authority is created by this decision record.")
                ],
            }
        )

    assessment["assessment_notes"] = [
        f"Adapted from {PROGRAMME_FORMAT} with source SHA-256 {source_sha}.",
        f"Programme counts: {json.dumps(value.get('counts', {}), ensure_ascii=False, sort_keys=True)}",
        "Safety-event categories preserved below as source-assessment notes because v4.2 has no standalone safety-event register.",
    ] + [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value.get("safety_events", [])]

    preservation = _preservation_checks(value, assessment)
    assessment["migration_provenance"] = {
        "migration_id": f"ADAPTER-{_text(metadata.get('assessment_id'), 'UNASSIGNED')}",
        "source_instrument_version": _text(metadata.get("instrument_version"), "v4.2"),
        "target_instrument_version": "v4.2",
        "source_assessment_id": _text(metadata.get("assessment_id"), "UNASSIGNED"),
        "source_sha256": source_sha,
        "historical_projection_sha256": sha256_bytes(canonical_json_bytes(value.get("requirement_findings", []))),
        "migration_ruleset": f"programme-adapter/{ADAPTER_VERSION}",
        "migration_date": _text(metadata.get("executed_at"), metadata.get("evidence_cutoff"))[:10],
        "preservation_verified": preservation["preservation_verified"],
        "migration_warnings": [
            "Programme-only source, safety-event, and packaging fields are represented through evidence records, notes, and provenance.",
            "The adapter does not re-appraise evidence or upgrade any finding, claim, authorization, or conformance state.",
            "Native gap_register.linked_requirement_ids are empty because the programme source gaps do not carry requirement links.",
            "Classification sc_01–sc_12 values are provisional adapter projections and require human domain confirmation.",
            "preservation_verified is computed from mechanical identifier/status reconciliation only; detailed checks are in the adapter report.",
        ],
    }

    validation = validate_assessment(assessment).to_dict()
    report = {
        "adapter": f"programme-adapter/{ADAPTER_VERSION}",
        "source_format": PROGRAMME_FORMAT,
        "source_sha256": source_sha,
        "assessment_id": assessment["assessment_metadata"]["assessment_id"],
        "preserved_counts": {
            "claims": len(assessment["claim_register"]),
            "evidence_objects": len(assessment["evidence_register"]),
            "endpoints": len(assessment["endpoint_register"]),
            "denominators": len(assessment["denominator_register"]),
            "requirement_findings": len(assessment["requirement_findings"]),
            "gaps": len(assessment["gap_register"]),
            "decisions": len(assessment["decision_register"]),
            "safety_event_notes": len(value.get("safety_events", [])),
        },
        "preservation": preservation,
        "no_reappraisal": {
            "reappraisal_performed": False,
            "finding_status_upgrades_forbidden": True,
            "missing_evidence_to_fail_forbidden": True,
            "statement": (
                "Adaptation projects source determinations into the native object model only. "
                "It does not re-weigh evidence, change requirement meanings, or convert unresolved gaps into FAIL."
            ),
        },
        "validation": validation,
        "loss_boundaries": [
            "Source-register rows are consolidated into native evidence records and provenance identifiers.",
            "Standalone safety-event rows are retained as deterministic assessment notes.",
            "Native gap_register.linked_requirement_ids remain [] because programme gaps_and_requests lack linked requirement IDs.",
            "Classification sc_01–sc_12 values are provisional hardcoded projections pending domain confirmation.",
            "Unmatched programme claim_state strings map to NOT REVIEWABLE rather than supported-within-scope.",
            "No model-generated content is introduced by this adapter.",
        ],
        "boundary": "Adaptation preserves a source assessment in the workbench object model; it does not constitute independent appraisal or endorsement.",
    }
    return AdapterResult(assessment=assessment, report=report)


def adapt_programme_file(source: Path, output: Path, report_output: Path | None = None) -> AdapterResult:
    value = json.loads(source.read_text(encoding="utf-8"))
    result = adapt_programme_assessment(value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report_output:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(result.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
