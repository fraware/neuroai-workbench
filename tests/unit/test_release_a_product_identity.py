from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.release_a_product_identity import (
    ReleaseAProductIdentityError,
    cross_validate_product_entities_against_a1,
    load_default_seed_product_entity_registry,
    seed_product_entity_registry_sha256,
    validate_seed_product_entity_registry,
)
from neuroai_workbench.release_a_seed_registry import load_default_seed_artifacts


def _artifacts() -> tuple[dict, dict]:
    identity = load_default_seed_product_entity_registry()
    seed = load_default_seed_artifacts()
    return identity, seed


def test_seed_product_entity_registry_covers_exact_a1_offering_set() -> None:
    identity, seed = _artifacts()
    cross_validate_product_entities_against_a1(
        identity,
        seed_manifest=seed["manifest"],
        seed_registry=seed["registry"],
        evidence_packet=seed["packet"],
    )
    ids = {entity["entity_id"] for entity in identity["entities"]}
    assert ids == {
        "PRD-MUSE-S-ATHENA",
        "PRD-NEXTSENSE-SMARTBUDS",
        "PRD-EMOTIV-EPOC-X",
        "PRD-FLOW-FL-100",
        "PRD-MODIUS-SPERO",
        "PRD-SYNCHRON-STENTRODE",
    }
    assert len(seed_product_entity_registry_sha256(identity)) == 64


def test_pending_identity_candidate_cannot_be_consumed_as_frozen_authority() -> None:
    identity = load_default_seed_product_entity_registry()
    with pytest.raises(ReleaseAProductIdentityError, match="not frozen"):
        validate_seed_product_entity_registry(identity, require_frozen=True)


def test_identity_registry_rejects_unregistered_wrong_type_and_label_drift() -> None:
    identity, seed = _artifacts()

    missing = deepcopy(identity)
    missing["entities"] = missing["entities"][:-1]
    missing["entity_count"] -= 1
    with pytest.raises(ReleaseAProductIdentityError, match="cardinality|exactly cover"):
        cross_validate_product_entities_against_a1(
            missing,
            seed_manifest=seed["manifest"],
            seed_registry=seed["registry"],
            evidence_packet=seed["packet"],
        )

    wrong_type = deepcopy(identity)
    wrong_type["entities"][0]["entity_type"] = "SYSTEM"
    with pytest.raises(ReleaseAProductIdentityError, match="entity_type PRODUCT"):
        validate_seed_product_entity_registry(wrong_type)

    wrong_label = deepcopy(identity)
    wrong_label["entities"][0]["canonical_label"] = "Different product"
    with pytest.raises(ReleaseAProductIdentityError, match="canonical label"):
        validate_seed_product_entity_registry(wrong_label)


def test_identity_registry_rejects_duplicate_id_and_evidence_mismatch() -> None:
    identity, seed = _artifacts()

    duplicate = deepcopy(identity)
    duplicate["entities"][1]["entity_id"] = duplicate["entities"][0]["entity_id"]
    with pytest.raises(ReleaseAProductIdentityError, match="Duplicate"):
        validate_seed_product_entity_registry(duplicate)

    evidence_drift = deepcopy(identity)
    evidence_drift["identity_bindings"][0]["source_observation_refs"] = ["OBS-NOT-BOUND"]
    with pytest.raises(ReleaseAProductIdentityError, match="identity evidence"):
        cross_validate_product_entities_against_a1(
            evidence_drift,
            seed_manifest=seed["manifest"],
            seed_registry=seed["registry"],
            evidence_packet=seed["packet"],
        )


def test_frozen_authority_requires_exact_approval_binding_and_approved_allocations() -> None:
    identity = load_default_seed_product_entity_registry()

    claimed_frozen = deepcopy(identity)
    claimed_frozen["authority_state"] = "FROZEN_v1.0"
    with pytest.raises(ReleaseAProductIdentityError, match="candidate blob and approval ref"):
        validate_seed_product_entity_registry(claimed_frozen)

    claimed_frozen["approved_candidate_blob_sha"] = "1" * 40
    claimed_frozen["approval_ref"] = "issue-347-comment-placeholder"
    with pytest.raises(ReleaseAProductIdentityError, match="approved allocation state"):
        validate_seed_product_entity_registry(claimed_frozen)
