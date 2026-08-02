from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.shadow_refresh import (
    bind_reviewed_cohort_to_registry,
    discover_cohort_candidates,
    load_reviewed_cohort_manifest,
    validate_shadow_refresh_cohort,
)
from neuroai_workbench.util import load_json

ROOT = Path(__file__).resolve().parents[2]
REVIEWED = ROOT / "examples" / "shadow_refresh" / "SHADOW_REFRESH_COHORT_REVIEWED_v202608.json"
SYNTHETIC = ROOT / "examples" / "shadow_refresh" / "SHADOW_REFRESH_COHORT_v202608.json"


def test_reviewed_cohort_validates_exact_ids() -> None:
    cohort = load_reviewed_cohort_manifest(REVIEWED)
    assert validate_shadow_refresh_cohort(cohort) == []
    assert cohort["metadata"]["source_count"] == 25
    assert len({item["source_id"] for item in cohort["sources"]}) == 25
    assert all(item["coverage_label"] == item["cohort_category"] for item in cohort["sources"])
    assert all("DIVERSITY_PAD" not in (item["coverage_label"], item["cohort_category"]) for item in cohort["sources"])


def test_reviewed_cohort_rejects_meta_as_prima_science() -> None:
    cohort = load_json(REVIEWED)
    by_id = {item["source_id"]: item for item in cohort["sources"]}
    # Meta Brain2Qwerty announcement is labeled BRAIN2QWERTY, never PRIMA_SCIENCE.
    assert by_id["SRC-0038"]["coverage_label"] == "BRAIN2QWERTY"
    # Meta PRIMARY_RESEARCH_PAGE (SRC-0039) must not appear as PRIMA_SCIENCE.
    assert "SRC-0039" not in by_id
    prima = [item for item in cohort["sources"] if item["coverage_label"] == "PRIMA_SCIENCE"]
    assert all("meta" not in item["publisher"].lower() for item in prima)
    assert all("ai.meta.com" not in item["url"] for item in prima)


def test_reviewed_cohort_rejects_heraeus_as_fda_adbs() -> None:
    cohort = load_json(REVIEWED)
    by_id = {item["source_id"]: item for item in cohort["sources"]}
    assert by_id["SRC-14-007"]["coverage_label"] == "SUPPLIER_DEPENDENCY"
    fda = [item for item in cohort["sources"] if item["coverage_label"] == "FDA_ADBS"]
    assert all("heraeus" not in item["publisher"].lower() for item in fda)
    assert all("heraeus" not in item["url"].lower() for item in fda)


def test_reviewed_cohort_rejects_ec_health_food_safety_as_safety_supplier() -> None:
    cohort = load_json(REVIEWED)
    by_id = {item["source_id"]: item for item in cohort["sources"]}
    assert by_id["SRC-0121"]["coverage_label"] == "REGISTRY"
    safety = [item for item in cohort["sources"] if item["coverage_label"] == "SAFETY"]
    assert all("health and food safety" not in item["publisher"].lower() for item in safety)
    assert all("health.ec.europa.eu" not in item["url"].lower() for item in safety)


def test_load_reviewed_cohort_rejects_duplicates_and_diversity_pad(tmp_path: Path) -> None:
    cohort = load_json(REVIEWED)
    cohort["sources"][1] = dict(cohort["sources"][0])
    path = tmp_path / "dup.json"
    path.write_text(__import__("json").dumps(cohort), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate source_id"):
        load_reviewed_cohort_manifest(path)

    cohort = load_json(REVIEWED)
    cohort["sources"][0]["cohort_category"] = "DIVERSITY_PAD"
    cohort["sources"][0]["coverage_label"] = "DIVERSITY_PAD"
    # Schema rejects DIVERSITY_PAD enum before diversity check; either is acceptable.
    bad = tmp_path / "pad.json"
    bad.write_text(__import__("json").dumps(cohort), encoding="utf-8")
    with pytest.raises(ValueError):
        load_reviewed_cohort_manifest(bad)


def test_discover_candidates_are_non_authoritative_and_not_freeze() -> None:
    registry = {
        "sources": [
            {
                "source_id": "SRC-0039",
                "monitor_id": "MON-0039",
                "publisher": "Meta AI",
                "url": "https://ai.meta.com/research/publications/accurate-decoding",
                "source_class": "PRIMARY_RESEARCH_PAGE",
            },
            {
                "source_id": "SRC-14-007",
                "monitor_id": "MON-14-007",
                "publisher": "Heraeus Medevio",
                "url": "https://www.heraeus-medevio.com/en/medical-components/neuromodulation/",
                "source_class": "OFFICIAL_SUPPLIER_PAGE",
            },
            {
                "source_id": "SRC-0121",
                "monitor_id": "MON-0121",
                "publisher": "European Commission Directorate-General for Health and Food Safety",
                "url": "https://health.ec.europa.eu/medical-devices-sector_en",
                "source_class": "OFFICIAL_ORGANIZATION_WEBPAGE",
            },
        ]
    }
    candidates = discover_cohort_candidates(registry, target_count=10)
    assert candidates
    assert all(item.get("authoritative") is False for item in candidates)
    assert all(item.get("discovery_only") is True for item in candidates)
    # Discovery may misclassify; that is why freeze requires reviewed IDs.
    meta = next(item for item in candidates if item["source_id"] == "SRC-0039")
    assert meta["discovery_category"] == "PRIMA_SCIENCE"


def test_bind_reviewed_cohort_requires_registry_ids() -> None:
    cohort = load_reviewed_cohort_manifest(REVIEWED)
    with pytest.raises(ValueError, match="missing from registry"):
        bind_reviewed_cohort_to_registry(cohort, {"sources": []})


def test_synthetic_cohort_still_validates() -> None:
    assert validate_shadow_refresh_cohort(load_json(SYNTHETIC)) == []
