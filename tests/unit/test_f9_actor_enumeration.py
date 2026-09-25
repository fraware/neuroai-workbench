from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_ID,
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    F9_ENUMERATION_BOUNDARY,
    F9_QUERY_FAMILY,
    f9_actor_completion_record_id,
    f9_bounded_exhaustion_state,
    f9_enumeration_procedure_digest,
    load_default_f9_actor_enumeration_procedure,
    validate_f9_actor_completion_record,
    validate_f9_actor_enumeration_procedure,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError, load_f9_actor_seed_register


def _reseal_procedure(procedure: dict[str, Any]) -> dict[str, Any]:
    procedure["procedure_sha256"] = f9_enumeration_procedure_digest(procedure)
    return procedure


def _actor(actor_id: str) -> dict[str, Any]:
    register = load_f9_actor_seed_register()
    return next(actor for actor in register["actors"] if actor["organization_id"] == actor_id)


def _completion(
    actor_id: str,
    *,
    state: str = "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL",
    with_candidate: bool = True,
) -> dict[str, Any]:
    actor = _actor(actor_id)
    candidates: list[dict[str, Any]] = []
    if with_candidate:
        candidates.append(
            {
                "candidate_key": f"{actor_id}::EXAMPLE",
                "object_class": "PLAUSIBLE_PRODUCT_OFFERING",
                "capture_id": "PDC-" + actor_id.removeprefix("ORG-").zfill(64),
                "capture_outcome": "UNRESOLVED_IDENTITY",
            }
        )
    record: dict[str, Any] = {
        "completion_record_id": "",
        "procedure_id": F9_ACTOR_ENUMERATION_PROCEDURE_ID,
        "procedure_sha256": F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
        "actor_organization_id": actor_id,
        "query_family": F9_QUERY_FAMILY,
        "inspection_surfaces": [
            {
                "locator": actor["official_url"],
                "source_class": "MANUFACTURER_VENDOR_OFFICIAL",
                "retrieval_outcome": "RETRIEVED",
                "roles": [
                    "FROZEN_OFFICIAL_LOCATOR",
                    "PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE",
                ],
            }
        ],
        "candidate_manifest": candidates,
        "no_named_product_evidence": not with_candidate,
        "catalogue_manifest_complete_under_inspected_surfaces": state == "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL",
        "completion_state": state,
        "completion_reason": "Protocol-bounded test completion.",
        "recorded_at": "2026-09-25T18:30:00Z",
        "boundary": F9_ENUMERATION_BOUNDARY,
    }
    record["completion_record_id"] = f9_actor_completion_record_id(record)
    return record


def _reseal_record(record: dict[str, Any]) -> dict[str, Any]:
    record["completion_record_id"] = f9_actor_completion_record_id(record)
    return record


def test_default_f9_enumeration_procedure_is_exactly_frozen() -> None:
    procedure = load_default_f9_actor_enumeration_procedure()
    assert procedure["procedure_id"] == F9_ACTOR_ENUMERATION_PROCEDURE_ID
    assert procedure["procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert procedure["actor_count"] == 37
    assert len(procedure["actor_identity_ids"]) == 37
    assert procedure["query_family"] == F9_QUERY_FAMILY
    assert procedure["world_time_cutoff"] == "2026-09-24"
    assert procedure["knowledge_time_cutoff"] == "2026-10-24T23:59:59Z"


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("status", "DRAFT", "FROZEN_v1.0"),
        ("frame_id", "F1", "frozen F9"),
        ("frame_register_blob_sha", "bad", "frame-register blob"),
        ("actor_seed_register_blob_sha", "bad", "actor-seed register blob"),
        ("analysis_universe_id", "RAU-bad", "analysis universe"),
        ("world_time_cutoff", "2026-09-25", "world_time_cutoff"),
        ("knowledge_time_cutoff", "2026-10-25T23:59:59Z", "knowledge_time_cutoff"),
        ("query_family", "OTHER", "query_family"),
        ("boundary", "weaker", "boundary"),
    ],
)
def test_f9_enumeration_procedure_rejects_governance_drift(
    field: str,
    replacement: str,
    message: str,
) -> None:
    procedure = load_default_f9_actor_enumeration_procedure()
    procedure[field] = replacement
    _reseal_procedure(procedure)
    with pytest.raises(ProductDiscoveryError, match=message):
        validate_f9_actor_enumeration_procedure(procedure)


def test_f9_enumeration_procedure_rejects_actor_and_domain_drift() -> None:
    procedure = load_default_f9_actor_enumeration_procedure()
    procedure["actor_identity_ids"] = list(reversed(procedure["actor_identity_ids"]))
    _reseal_procedure(procedure)
    with pytest.raises(ProductDiscoveryError, match="actor identities"):
        validate_f9_actor_enumeration_procedure(procedure)

    procedure = load_default_f9_actor_enumeration_procedure()
    procedure["allowed_source_classes"] = ["MANUFACTURER_VENDOR_OFFICIAL"]
    _reseal_procedure(procedure)
    with pytest.raises(ProductDiscoveryError, match="source classes"):
        validate_f9_actor_enumeration_procedure(procedure)

    procedure = load_default_f9_actor_enumeration_procedure()
    procedure["candidate_object_classes"] = ["PLAUSIBLE_PRODUCT_OFFERING"]
    _reseal_procedure(procedure)
    with pytest.raises(ProductDiscoveryError, match="candidate-object domain"):
        validate_f9_actor_enumeration_procedure(procedure)


def test_f9_enumeration_procedure_rejects_unsealed_and_extra_content() -> None:
    procedure = load_default_f9_actor_enumeration_procedure()
    procedure["status"] = "DRAFT"
    with pytest.raises(ProductDiscoveryError, match="procedure_sha256"):
        validate_f9_actor_enumeration_procedure(procedure)

    procedure = load_default_f9_actor_enumeration_procedure()
    procedure["unexpected"] = "drift"
    _reseal_procedure(procedure)
    with pytest.raises(ProductDiscoveryError, match="frozen v1.0 digest"):
        validate_f9_actor_enumeration_procedure(procedure)


def test_complete_actor_record_accepts_captured_candidate_and_empty_manifest_case() -> None:
    validate_f9_actor_completion_record(_completion("ORG-0001"))
    validate_f9_actor_completion_record(_completion("ORG-0002", with_candidate=False))


def test_complete_actor_record_requires_official_and_catalogue_surfaces() -> None:
    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["retrieval_outcome"] = "FAILED_INACCESSIBLE"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="retrieved frozen official locator"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["roles"] = ["FROZEN_OFFICIAL_LOCATOR"]
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="catalogue surface"):
        validate_f9_actor_completion_record(record)


def test_complete_actor_record_requires_exact_candidate_capture_dispositions() -> None:
    record = _completion("ORG-0001")
    record["candidate_manifest"][0]["capture_id"] = None
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="capture disposition"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["candidate_manifest"][0]["capture_id"] = "PDC-short"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="exact PDC identifier"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["candidate_manifest"].append(deepcopy(record["candidate_manifest"][0]))
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="Duplicate F9 candidate_key"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["candidate_manifest"][0]["candidate_key"] = "ORG-0002::OTHER"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="bound to its frozen actor"):
        validate_f9_actor_completion_record(record)


def test_actor_record_fails_closed_on_identity_source_and_completion_semantics() -> None:
    record = _completion("ORG-0001")
    record["actor_organization_id"] = "ORG-9999"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="unknown frozen actor"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["source_class"] = "MEDIA"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="source_class"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["source_class"] = "CURATED_OBSERVATORY_ACTOR"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="first-party manufacturer/vendor"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["completion_state"] = "DONE"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="completion_state"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["completion_reason"] = ""
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="completion_reason"):
        validate_f9_actor_completion_record(record)


def test_actor_record_preserves_explicit_no_product_evidence_semantics() -> None:
    record = _completion("ORG-0001", with_candidate=False)
    record["no_named_product_evidence"] = False
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="no_named_product_evidence"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["catalogue_manifest_complete_under_inspected_surfaces"] = False
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="complete inspected-surface candidate manifest"):
        validate_f9_actor_completion_record(record)


def test_partial_and_blocked_records_do_not_claim_bounded_exhaustion() -> None:
    actor_ids = load_default_f9_actor_enumeration_procedure()["actor_identity_ids"]
    records = [_completion(actor_id) for actor_id in actor_ids]
    assert f9_bounded_exhaustion_state(records[:-1]) == "CONTINUE"
    assert f9_bounded_exhaustion_state(records) == "BOUNDED_FRAME_EXHAUSTED"

    partial = [_completion(actor_id) for actor_id in actor_ids]
    partial[0] = _completion("ORG-0001", state="ACTOR_ENUMERATION_PARTIAL")
    assert f9_bounded_exhaustion_state(partial) == "CONTINUE"

    blocked = [_completion(actor_id) for actor_id in actor_ids]
    blocked[0] = _completion("ORG-0001", state="ACTOR_ENUMERATION_BLOCKED")
    assert f9_bounded_exhaustion_state(blocked) == "UNRESOLVED_SOURCE_BARRIER"


def test_exhaustion_ledger_rejects_duplicate_actor_or_capture_bindings() -> None:
    record = _completion("ORG-0001")
    with pytest.raises(ProductDiscoveryError, match="Duplicate F9 actor completion record"):
        f9_bounded_exhaustion_state([record, deepcopy(record)])

    first = _completion("ORG-0001")
    second = _completion("ORG-0002")
    second["candidate_manifest"][0]["capture_id"] = first["candidate_manifest"][0]["capture_id"]
    _reseal_record(second)
    with pytest.raises(ProductDiscoveryError, match="reused across actor"):
        f9_bounded_exhaustion_state([first, second])


def test_f9_enumeration_procedure_rejects_additional_frozen_domain_drift() -> None:
    cases = [
        ("procedure_id", "OTHER", "procedure_id"),
        ("frame_register_version", "OTHER", "frame register version"),
        ("actor_seed_register_id", "OTHER", "actor-seed register"),
        ("actor_count", 36, "actor_count"),
        ("surface_roles", ["FROZEN_OFFICIAL_LOCATOR"], "surface-role domain"),
        ("retrieval_outcomes", ["RETRIEVED"], "retrieval-outcome domain"),
        ("capture_outcomes", ["INCLUDE_RESOLVED"], "capture-outcome domain"),
        ("actor_completion_states", ["ACTOR_ENUMERATION_PARTIAL"], "actor-completion domain"),
    ]
    for field, replacement, message in cases:
        procedure = load_default_f9_actor_enumeration_procedure()
        procedure[field] = replacement
        _reseal_procedure(procedure)
        with pytest.raises(ProductDiscoveryError, match=message):
            validate_f9_actor_enumeration_procedure(procedure)


def test_actor_completion_record_rejects_binding_drift() -> None:
    cases = [
        ("procedure_id", "OTHER", "procedure ID"),
        ("procedure_sha256", "0" * 64, "procedure digest"),
        ("query_family", "OTHER", "query_family"),
        ("boundary", "weaker", "boundary"),
    ]
    for field, replacement, message in cases:
        record = _completion("ORG-0001")
        record[field] = replacement
        _reseal_record(record)
        with pytest.raises(ProductDiscoveryError, match=message):
            validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["completion_record_id"] = "F9AC-bad"
    with pytest.raises(ProductDiscoveryError, match="completion_record_id"):
        validate_f9_actor_completion_record(record)


def test_actor_completion_record_rejects_malformed_surfaces() -> None:
    record = _completion("ORG-0001")
    record["inspection_surfaces"] = []
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="non-empty inspection_surfaces"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"] = ["bad"]
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="surfaces must be objects"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["locator"] = ""
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="exact locator"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["retrieval_outcome"] = "UNKNOWN"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="retrieval_outcome"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["inspection_surfaces"][0]["roles"] = ["UNKNOWN"]
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="roles are invalid"):
        validate_f9_actor_completion_record(record)


def test_actor_completion_record_rejects_malformed_candidate_manifest() -> None:
    record = _completion("ORG-0001")
    record["candidate_manifest"] = ["bad"]
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="entries must be objects"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["candidate_manifest"][0]["candidate_key"] = ""
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="requires candidate_key"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    second = deepcopy(record["candidate_manifest"][0])
    second["candidate_key"] = "ORG-0001::SECOND"
    record["candidate_manifest"].append(second)
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="Duplicate F9 capture_id"):
        validate_f9_actor_completion_record(record)

    record = _completion("ORG-0001")
    record["no_named_product_evidence"] = "false"
    _reseal_record(record)
    with pytest.raises(ProductDiscoveryError, match="boolean no_named_product_evidence"):
        validate_f9_actor_completion_record(record)
