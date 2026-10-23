"""Regression tests for the nonterminal literature/registry text crosswalk."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import r1_7_compare_review_registry as crosswalk


def test_frozen_six_entity_registry_is_real_and_unchanged() -> None:
    registry, digest = crosswalk.load_frozen_registry()
    assert len(registry["rows"]) == 6
    assert {x["canonical_entity_id"] for x in registry["rows"]} == crosswalk.EXPECTED_ENTITY_IDS
    assert len(digest) == 64


@pytest.mark.parametrize(
    ("label", "category", "candidate"),
    [
        ("Emotiv EPOC X", "EXACT_TEXTUAL_REGISTRY_ID_LABEL_CANDIDATE", "PRD-EMOTIV-EPOC-X"),
        ("Muse S ATHENA", "EXACT_TEXTUAL_REGISTRY_ID_LABEL_CANDIDATE", "PRD-MUSE-S-ATHENA"),
        ("Smartbuds", "PARTIAL_NAME_OVERLAP_IDENTITY_AMBIGUOUS", "PRD-NEXTSENSE-SMARTBUDS"),
        ("Muse 2", "NO_TEXTUAL_REGISTRY_ID_MATCH", None),
        ("OpenBCI Galea", "NO_TEXTUAL_REGISTRY_ID_MATCH", None),
        ("BitBrain Ikon/Ikon sleep", "NO_TEXTUAL_REGISTRY_ID_MATCH", None),
        ("Emotiv Insight", "NO_TEXTUAL_REGISTRY_ID_MATCH", None),
    ],
)
def test_no_automatic_identity_from_text(label: str, category: str, candidate: str | None) -> None:
    result = crosswalk.classify_designation(label, set(crosswalk.EXPECTED_ENTITY_IDS))
    assert result["registry_comparison_category"] == category
    assert result["potential_registry_entity_id"] == candidate
    assert result["canonical_entity_id_allocated"] is None
    assert result["identity_adjudication"] == "UNRESOLVED"
    assert result["new_offering_status"] == "UNDETERMINED"
    assert result["composite_name_needs_splitting_review"] == ("/" in label)


def test_match_requires_frozen_registry_presence() -> None:
    with pytest.raises(ValueError, match="missing"):
        crosswalk.classify_designation("Muse S ATHENA", set())


def test_tampered_registry_identity_is_rejected() -> None:
    registry, _ = crosswalk.load_frozen_registry()
    tampered = deepcopy(registry)
    tampered["rows"][0]["canonical_entity_id"] = "PRD-UNSUPPORTED"
    with pytest.raises(ValueError, match="identity set"):
        crosswalk.make_crosswalk(b"not real XML", tampered, "0" * 64)
