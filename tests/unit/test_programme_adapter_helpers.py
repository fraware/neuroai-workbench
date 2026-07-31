from __future__ import annotations

import pytest

from neuroai_workbench.programme_adapter import (
    _access_state,
    _claim_status,
    _claim_type,
    _claimant_record_type,
    _component_type,
    _decision_state,
    _decision_type,
    _evidence_state,
    _evidence_type,
    _finding_access_state,
    _gate_state,
    _list_text,
    _primary_state,
    _text,
    adapt_programme_assessment,
    detect_programme_assessment,
)


def test_detect_rejects_non_programme_shapes() -> None:
    assert detect_programme_assessment([]) is False
    assert detect_programme_assessment({"metadata": {}}) is False


def test_text_and_list_helpers() -> None:
    assert _text(None) == "UNRESOLVED"
    assert _text("  ") == "UNRESOLVED"
    assert _text("ok") == "ok"
    assert '"a"' in _text({"a": 1})
    assert _list_text(None) == []
    assert _list_text("solo") == ["solo"]
    assert _list_text(["a", "", None, "b"]) == ["a", "b"]
    assert _list_text(3) == ["3"]


def test_component_type_branches() -> None:
    assert _component_type("Application software") == "SOFTWARE"
    assert _component_type("Neural processor implant") == "HARDWARE"
    assert _component_type("Inference model algorithm") == "MODEL"
    assert _component_type("Wearable glasses accessory") == "ACCESSORY"
    assert _component_type("Clinical rehabilitation procedure") == "PROCEDURE"
    assert _component_type("Streaming data feed") == "DATA PIPELINE"
    assert _component_type("Unknown widget") == "OTHER"


def test_claim_mapping_branches() -> None:
    assert _claim_type({"claim": "CE mark dossier", "claim_state": ""}) == "AUTHORIZATION"
    assert _claim_type({"claim": "adverse event rate", "claim_state": ""}) == "SAFETY"
    assert _claim_type({"claim": "accuracy improvement", "claim_state": ""}) == "PERFORMANCE"
    assert _claim_type({"claim": "commercial launch", "claim_state": ""}) == "DEPLOYMENT"
    assert _claim_type({"claim": "participant home use", "claim_state": ""}) == "PARTICIPANT EXPERIENCE"
    assert _claim_type({"claim": "restore vision benefit", "claim_state": ""}) == "EFFECTIVENESS"
    assert _claim_type({"claim": "general capability", "claim_state": ""}) == "CAPABILITY"
    assert _claim_status("CONTRADICTED_BY_STUDY") == "CONTRADICTED"
    assert _claim_status("UNSUPPORTED_CLAIM") == "UNSUPPORTED"
    assert _claim_status("WITHDRAWN_LABEL") == "WITHDRAWN OR SUPERSEDED"
    assert _claim_status("UNRESOLVED_PUBLIC") == "NOT REVIEWABLE"
    assert _claimant_record_type({"claim_state": "COMPANY_ANNOUNCEMENT"}) == "CORPORATE COMMUNICATION"
    assert _claimant_record_type({"claim_state": "REGULATOR_NOTE"}) == "REGULATORY AUTHORITY"
    assert _claimant_record_type({"claim_state": "PARTICIPANT_FEEDBACK"}) == "PARTICIPANT STATEMENT"
    assert _claimant_record_type({"claim_state": "ASSESSOR_NOTE"}) == "ASSESSOR-CONTROLLED CLAIM"


def test_evidence_access_and_decision_helpers() -> None:
    assert _evidence_type("PEER_REVIEWED_PAPER") == "PEER-REVIEWED STUDY"
    assert _evidence_type("PREPRINT_SERVER") == "PREPRINT"
    assert _evidence_type("TRIAL_REGISTRY_ENTRY") == "TRIAL REGISTRY"
    assert _evidence_type("FDA_CERTIFICATE") == "REGULATORY AUTHORIZATION"
    assert _evidence_type("SAFETY_VIGILANCE") == "SAFETY OR VIGILANCE RECORD"
    assert _evidence_type("PARTICIPANT_NOTE") == "PARTICIPANT OR CAREGIVER EVIDENCE"
    assert _evidence_type("TECHNICAL_MANUAL") == "METHOD OR TECHNICAL DOCUMENT"
    assert _evidence_type("COMPANY_MEDIA") == "COMMERCIAL CLAIM"
    assert _evidence_type("OTHER_THING") == "OTHER"
    assert _evidence_state({"evidence_class": "PEER_REVIEW", "publication_state": ""}) == "PEER-REVIEWED PUBLICATION"
    assert _evidence_state({"evidence_class": "TRIAL_REGISTRY", "publication_state": ""}) == "TRIAL REGISTRY"
    assert _evidence_state({"evidence_class": "PREPRINT", "publication_state": ""}) == "PREPRINT"
    assert _evidence_state({"evidence_class": "REGULATORY", "publication_state": ""}) == "REGULATORY RECORD"
    assert _evidence_state({"evidence_class": "PATENT", "publication_state": ""}) == "PATENT RECORD"
    assert (
        _evidence_state({"evidence_class": "PARTICIPANT", "publication_state": ""})
        == "PARTICIPANT OR CAREGIVER EVIDENCE"
    )
    assert _evidence_state({"evidence_class": "COMPANY", "publication_state": ""}) == "COMMERCIAL OR MEDIA CLAIM"
    assert _evidence_state({"evidence_class": "DISCOVERY", "publication_state": ""}) == "CONTROLLED DISCOVERY RECORD"
    assert _evidence_state({"evidence_class": "METADATA", "publication_state": ""}) == "PRIMARY METADATA VERIFIED"
    assert (
        _evidence_state({"evidence_class": "PRIVATE", "publication_state": "REQUIRED"}) == "PRIVATE EVIDENCE REQUIRED"
    )
    assert _access_state({"retrieval_state": "METADATA ONLY"}) == "PUBLIC METADATA ONLY"
    assert _access_state({"retrieval_state": "FULL CONTENT RETRIEVED"}) == "PUBLICLY RETRIEVED"
    assert _primary_state("PRIMARY_SOURCE") == "PRIMARY"
    assert _primary_state("MEDIA_REVIEW") == "SECONDARY"
    assert _primary_state("OTHER") == "UNKNOWN"
    assert _finding_access_state("x", "NOT APPLICABLE WITH RATIONALE", "PASS") == "NOT APPLICABLE"
    assert _finding_access_state("REGULATOR HELD", "APPLICABLE", "PASS") == "KNOWN REGULATOR-HELD RECORD"
    assert _finding_access_state("MANUFACTURER HELD", "APPLICABLE", "PASS") == "KNOWN MANUFACTURER-HELD RECORD"
    assert _finding_access_state("SPONSOR HELD", "APPLICABLE", "PASS") == "KNOWN SPONSOR-HELD RECORD"
    assert _finding_access_state("SITE HELD", "APPLICABLE", "PASS") == "KNOWN SITE-HELD RECORD"
    assert (
        _finding_access_state("NOT PUBLIC REQUIRED EVIDENCE", "APPLICABLE", "PASS") == "KNOWN PRIVATE RECORD REQUIRED"
    )
    assert _finding_access_state("METADATA ONLY", "APPLICABLE", "PASS") == "PUBLIC METADATA ONLY"
    assert _finding_access_state("PUBLIC EXTRACT", "APPLICABLE", "PASS") == "PUBLICLY RETRIEVED"
    assert _finding_access_state("PUBLIC EXTRACT", "APPLICABLE", "PARTIAL") == "CONTROLLED PUBLIC EXTRACT"
    assert _finding_access_state("UNKNOWN", "APPLICABLE", "PASS") == "EXISTENCE UNKNOWN"
    assert _gate_state("x", "NOT APPLICABLE WITH RATIONALE") == "CURRENTLY INAPPLICABLE"
    assert _gate_state("PROHIBITED USE", "APPLICABLE") == "PROHIBITED"
    assert _gate_state("OPEN CONDITION REOPEN", "APPLICABLE") == "REOPENING REQUIRED"
    assert _gate_state("CURRENT GATE", "APPLICABLE") == "CURRENTLY APPLICABLE"
    assert _gate_state("OTHER", "APPLICABLE") == "UNRESOLVED"
    assert _decision_type("CONFORMANCE") == "CONFORMANCE DECISION"
    assert _decision_type("REGULATORY AUTHORIZATION") == "LEGAL OR REGULATORY AUTHORIZATION"
    assert _decision_type("REOPEN OBSERVATORY") == "REOPENING DECISION"
    assert _decision_type("CLAIM") == "CLAIM ADJUDICATION"
    assert (
        _decision_state({"decision_class": "CONFORMANCE", "decision": "NOT_ESTABLISHED"})
        == "NO CONFORMANCE DECISION — BLOCKED"
    )
    assert _decision_state({"decision_class": "CONFORMANCE", "decision": "CONDITIONAL"}) == "CONDITIONAL CONFORMANCE"
    assert _decision_state({"decision_class": "CONFORMANCE", "decision": "CONFORMS"}) == "CONFORMS FOR BOUNDED SCOPE"
    assert _decision_state({"decision_class": "REGULATORY", "decision": "NOT_AUTH"}) == "AUTHORIZATION NOT ASSESSED"
    assert (
        _decision_state({"decision_class": "REGULATORY", "decision": "AUTHORIZED"}) == "AUTHORIZED WITHIN BOUNDED SCOPE"
    )
    assert _decision_state({"decision_class": "REOPEN", "decision": "ANY"}) == "REOPENED"
    assert _decision_state({"decision_class": "CLAIM", "decision": "UNSUPPORTED"}) == "UNSUPPORTED"
    assert _decision_state({"decision_class": "CLAIM", "decision": "PARTIAL"}) == "PARTIALLY SUPPORTED"
    assert (
        _decision_state({"decision_class": "CLAIM", "decision": "BOUNDED SUPPORTED"})
        == "SUPPORTED WITHIN BOUNDED SCOPE"
    )


def test_list_text_none_and_scalar() -> None:
    assert _list_text(None) == []
    assert _list_text(3) == ["3"]


def test_claim_status_empty_and_supported() -> None:
    assert _claim_status("") == "NOT REVIEWABLE"
    assert _claim_status("SUPPORTED_PRIMARY") == "SUPPORTED WITHIN BOUNDED SCOPE"
    assert _claim_status("TOTALLY_NOVEL") == "NOT REVIEWABLE"


def test_access_and_decision_unknown_defaults() -> None:
    assert _access_state({"retrieval_state": "MYSTERIOUS"}) == "EVALUATION NOT EXECUTED"
    assert (
        _decision_state({"decision_class": "CONFORMANCE", "decision": "WEIRD"}) == "NO CONFORMANCE DECISION — BLOCKED"
    )
    assert _decision_state({"decision_class": "REGULATORY", "decision": "WEIRD"}) == "AUTHORIZATION NOT ASSESSED"
    assert _decision_state({"decision_class": "CLAIM", "decision": "WEIRD"}) == "ASSESSMENT INCOMPLETE"


def test_adapt_rejects_non_programme() -> None:
    with pytest.raises(ValueError, match="supported programme"):
        adapt_programme_assessment({"metadata": {}})


def test_adapt_rewrites_not_applicable_applicability() -> None:
    import json
    from pathlib import Path

    source = json.loads(
        (
            Path(__file__).resolve().parents[2] / "examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json"
        ).read_text(encoding="utf-8")
    )
    source["requirement_findings"][0]["applicability"] = "NOT APPLICABLE"
    result = adapt_programme_assessment(source)
    finding = result.assessment["requirement_findings"][0]
    assert finding["applicability"] == "NOT APPLICABLE WITH RATIONALE"
