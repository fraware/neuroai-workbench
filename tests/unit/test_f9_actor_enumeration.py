from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

import pytest

from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_ID,
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    F9_ENUMERATION_BOUNDARY,
    F9_QUERY_FAMILY,
    f9_actor_completion_ledger_digest,
    f9_actor_completion_record_id,
    f9_bounded_exhaustion_state,
    f9_enumeration_procedure_digest,
    f9_sole_product_detail_catalogue_risk,
    load_default_f9_actor_enumeration_procedure,
    validate_f9_actor_completion_ledger,
    validate_f9_actor_completion_record,
    validate_f9_actor_enumeration_procedure,
)
from neuroai_workbench.product_discovery_frames import (
    ProductDiscoveryError,
    load_default_analysis_universe,
    load_default_frame_register,
    load_f9_actor_seed_register,
    validate_capture_against_frame,
)


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


def _ledger(
    records: list[dict[str, Any]],
    *,
    sequence: int = 1,
    predecessor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completed = [str(record["actor_organization_id"]) for record in records]
    ledger: dict[str, Any] = {
        "ledger_id": f"TEST_F9_LEDGER_{sequence:03d}",
        "ledger_sha256": "",
        "ledger_sequence": sequence,
        "predecessor_ledger_id": None if predecessor is None else predecessor["ledger_id"],
        "predecessor_ledger_sha256": None if predecessor is None else predecessor["ledger_sha256"],
        "status": "IMMUTABLE_SUCCESSOR",
        "assembled_on": "2026-09-25",
        "analysis_universe_id": "RAU-feb22ac8e7bc2f9ee644ecc2682e974eb73a40bfc5dccfc2ce2f3ee37abd774e",
        "procedure_id": F9_ACTOR_ENUMERATION_PROCEDURE_ID,
        "procedure_sha256": F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
        "actor_seed_register_id": "RELEASE_A_F9_ACTOR_SEED_REGISTER_v1.0",
        "actor_seed_count": 37,
        "completion_records": records,
        "completion_record_count": len(records),
        "completed_actor_ids": completed,
        "actor_completion_records_remaining": 37 - len(records),
        "f9_exhaustion_state": f9_bounded_exhaustion_state(records),
        "source_packet_id": "TEST_PACKET",
        "source_packet_sha256": "0" * 64,
        "boundary": F9_ENUMERATION_BOUNDARY,
    }
    ledger["ledger_sha256"] = f9_actor_completion_ledger_digest(ledger)
    return ledger


def test_f9_completion_ledger_accepts_sequence_one_and_growing_successor() -> None:
    first = _ledger([_completion("ORG-0001")])
    validate_f9_actor_completion_ledger(first)
    second = _ledger([_completion("ORG-0001"), _completion("ORG-0002")], sequence=2, predecessor=first)
    validate_f9_actor_completion_ledger(second, predecessor=first)


def test_f9_completion_ledger_fail_closes_on_digest_and_predecessor_faults() -> None:
    first = _ledger([_completion("ORG-0001")])
    first["ledger_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="ledger_sha256"):
        validate_f9_actor_completion_ledger(first)

    first = _ledger([_completion("ORG-0001")])
    second = _ledger([_completion("ORG-0001"), _completion("ORG-0002")], sequence=2, predecessor=first)
    second["predecessor_ledger_id"] = None
    second["ledger_sha256"] = f9_actor_completion_ledger_digest(second)
    with pytest.raises(ProductDiscoveryError, match="predecessor_ledger_id"):
        validate_f9_actor_completion_ledger(second, predecessor=first)

    second = _ledger([_completion("ORG-0001"), _completion("ORG-0002")], sequence=2, predecessor=first)
    with pytest.raises(ProductDiscoveryError, match="requires the predecessor ledger object"):
        validate_f9_actor_completion_ledger(second)


def test_f9_completion_ledger_fail_closes_on_shrink_duplicate_and_capture_reuse() -> None:
    first = _ledger([_completion("ORG-0001"), _completion("ORG-0002")])
    shrunk = _ledger([_completion("ORG-0001")], sequence=2, predecessor=first)
    with pytest.raises(ProductDiscoveryError, match="shrunk completed_actor_ids"):
        validate_f9_actor_completion_ledger(shrunk, predecessor=first)

    duplicate = _ledger([_completion("ORG-0001")])
    duplicate["completion_records"] = [_completion("ORG-0001"), deepcopy(_completion("ORG-0001"))]
    duplicate["completion_record_count"] = 2
    duplicate["completed_actor_ids"] = ["ORG-0001", "ORG-0001"]
    duplicate["actor_completion_records_remaining"] = 35
    duplicate["ledger_sha256"] = f9_actor_completion_ledger_digest(duplicate)
    with pytest.raises(ProductDiscoveryError, match="Duplicate F9 actor"):
        validate_f9_actor_completion_ledger(duplicate)

    reused = _ledger([_completion("ORG-0001"), _completion("ORG-0002")])
    reused["completion_records"][1]["candidate_manifest"][0]["capture_id"] = reused["completion_records"][0][
        "candidate_manifest"
    ][0]["capture_id"]
    reused["completion_records"][1] = _reseal_record(reused["completion_records"][1])
    reused["ledger_sha256"] = f9_actor_completion_ledger_digest(reused)
    with pytest.raises(ProductDiscoveryError, match="reused across actor"):
        validate_f9_actor_completion_ledger(reused)


def test_f9_completion_ledger_rejects_universe_drift_and_mutated_predecessor_records() -> None:
    first = _ledger([_completion("ORG-0001")])
    drifted = deepcopy(first)
    drifted["analysis_universe_id"] = "RAU-not-the-frozen-universe"
    drifted["ledger_sha256"] = f9_actor_completion_ledger_digest(drifted)
    with pytest.raises(ProductDiscoveryError, match="analysis universe"):
        validate_f9_actor_completion_ledger(drifted)

    second = _ledger([_completion("ORG-0001"), _completion("ORG-0002")], sequence=2, predecessor=first)
    mutated = deepcopy(second)
    mutated["completion_records"][0]["completion_reason"] = "Silently rewritten historical record."
    mutated["completion_records"][0] = _reseal_record(mutated["completion_records"][0])
    mutated["ledger_sha256"] = f9_actor_completion_ledger_digest(mutated)
    with pytest.raises(ProductDiscoveryError, match="mutated predecessor completion record"):
        validate_f9_actor_completion_ledger(mutated, predecessor=first)


def test_sole_product_detail_catalogue_is_flagged_as_underenumeration_risk() -> None:
    safe = _completion("ORG-0001")
    assert f9_sole_product_detail_catalogue_risk(safe) is None

    convenient = _completion("ORG-0001")
    convenient["inspection_surfaces"] = [
        {
            "locator": _actor("ORG-0001")["official_url"],
            "source_class": "MANUFACTURER_VENDOR_OFFICIAL",
            "retrieval_outcome": "RETRIEVED",
            "roles": ["FROZEN_OFFICIAL_LOCATOR"],
        },
        {
            "locator": "https://example.invalid/one-convenient-product",
            "source_class": "MANUFACTURER_VENDOR_OFFICIAL",
            "retrieval_outcome": "RETRIEVED",
            "roles": ["PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE", "PRODUCT_DETAIL_SURFACE"],
        },
    ]
    _reseal_record(convenient)
    validate_f9_actor_completion_record(convenient)
    assert f9_sole_product_detail_catalogue_risk(convenient) == "SOLE_PRODUCT_DETAIL_CATALOGUE_SURFACE"

    with_catalogue_index = deepcopy(convenient)
    with_catalogue_index["inspection_surfaces"].append(
        {
            "locator": "https://example.invalid/product-catalogue",
            "source_class": "MANUFACTURER_VENDOR_OFFICIAL",
            "retrieval_outcome": "RETRIEVED",
            "roles": ["PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE"],
        }
    )
    _reseal_record(with_catalogue_index)
    assert f9_sole_product_detail_catalogue_risk(with_catalogue_index) is None


def test_frozen_ledger_008_marks_medtronic_sole_detail_catalogue_residual_risk() -> None:
    ledger = json.loads(
        files("neuroai_workbench.resources.discovery")
        .joinpath("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008.v1.0.json")
        .read_text(encoding="utf-8")
    )
    by_actor = {record["actor_organization_id"]: record for record in ledger["completion_records"]}
    assert f9_sole_product_detail_catalogue_risk(by_actor["ORG-0020"]) is None  # G.TEC
    assert f9_sole_product_detail_catalogue_risk(by_actor["ORG-0017"]) is None  # OpenBCI
    assert f9_sole_product_detail_catalogue_risk(by_actor["ORG-0003"]) is None  # Bitbrain
    assert f9_sole_product_detail_catalogue_risk(by_actor["ORG-0007"]) is None  # Emotiv
    assert f9_sole_product_detail_catalogue_risk(by_actor["ORG-0036"]) == "SOLE_PRODUCT_DETAIL_CATALOGUE_SURFACE"


def test_f9_capture_cannot_enter_primary_estimator_or_silently_allocate_identity() -> None:
    from neuroai_workbench.product_discovery_frames import product_capture_id

    f9 = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F9")
    universe = load_default_analysis_universe()
    assert f9["capture_estimation_eligible"] is False
    assert "F9" in universe["diagnostic_only_frame_ids"]

    packet = json.loads(
        files("neuroai_workbench.resources.discovery")
        .joinpath("RELEASE_A_A2_F9_BITBRAIN_PROTOCOL_TRANCHE_5.v1.0.json")
        .read_text(encoding="utf-8")
    )
    capture = deepcopy(cast(dict[str, Any], packet["captures"][0]))
    assert capture["canonical_offering_id"] is None
    assert capture["capture_estimation_eligible"] is False
    validate_capture_against_frame(capture, f9)

    capture["capture_estimation_eligible"] = True
    capture["capture_id"] = product_capture_id(capture)
    with pytest.raises(ProductDiscoveryError, match="estimation-eligible|Only resolved"):
        validate_capture_against_frame(capture, f9)

    # F9 protocol packets must not allocate identity; seeded Bitbrain captures stay null.
    assert all(item["canonical_offering_id"] is None for item in packet["captures"])
