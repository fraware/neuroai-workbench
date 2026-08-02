from __future__ import annotations

from typing import Any

from ..util import canonical_json_bytes, sha256_bytes
from .constants import ACCESS_UNKNOWN


def digest_payload(payload: Any) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def unknown_lineage_digest() -> str:
    return ACCESS_UNKNOWN


def observatory_v1_4_lineage(value: dict[str, Any], source_sha256: str) -> str:
    metadata = value.get("metadata", {})
    payload = {
        "family": "OBSERVATORY_V1_4",
        "version": metadata.get("version"),
        "source_sha256": source_sha256,
        "counts": {
            key: len(value.get(key, []))
            for key in (
                "organizations",
                "organization_resolution",
                "regional_expansion",
                "capital_and_ownership_events",
                "representative_model_records",
                "model_and_dataset_registry",
                "trial_site_relationships",
                "participant_authority_relationships",
                "supplier_dependency_relationships",
                "sources",
            )
        },
    }
    return digest_payload(payload)


def observatory_v1_6_lineage(value: dict[str, Any], source_sha256: str) -> str:
    metadata = value.get("metadata", {})
    payload = {
        "family": "OBSERVATORY_V1_6",
        "version": metadata.get("version"),
        "release_id": metadata.get("release_id") or value.get("delta_id") or value.get("refresh_id"),
        "predecessor": metadata.get("predecessor"),
        "source_sha256": source_sha256,
        "top_level_keys": sorted(value.keys()),
    }
    return digest_payload(payload)


def observatory_v1_7_lineage(value: dict[str, Any], source_sha256: str) -> str:
    metadata = value.get("metadata", {})
    baseline = value.get("baseline_reference", {})
    payload = {
        "family": "OBSERVATORY_V1_7",
        "version": metadata.get("version"),
        "predecessor": metadata.get("predecessor"),
        "source_sha256": source_sha256,
        "baseline_sha256": baseline.get("canonical_sha256"),
        "successor_effective_counts": value.get("successor_effective_counts"),
    }
    return digest_payload(payload)


def assessment_v4_2_lineage(value: dict[str, Any], source_sha256: str) -> str:
    metadata = value.get("assessment_metadata", {})
    payload = {
        "family": "ASSESSMENT_V4_2",
        "assessment_id": metadata.get("assessment_id"),
        "instrument_version": metadata.get("instrument_version"),
        "source_sha256": source_sha256,
        "requirement_count": len(value.get("requirement_findings", [])),
        "evidence_count": len(value.get("evidence_register", [])),
    }
    return digest_payload(payload)


def source_registry_lineage(value: dict[str, Any], source_sha256: str) -> str:
    sources = value.get("sources", [])
    source_ids = sorted(
        record["source_id"]
        for record in sources
        if isinstance(record, dict) and isinstance(record.get("source_id"), str)
    )
    metadata = value.get("metadata", {})
    payload = {
        "family": "SOURCE_REGISTRY",
        "source_sha256": source_sha256,
        "record_count": metadata.get("record_count", len(sources)),
        "source_ids": source_ids,
    }
    return digest_payload(payload)


def programme_adapter_lineage(value: dict[str, Any], source_sha256: str) -> str:
    metadata = value.get("metadata", {})
    payload = {
        "family": "PROGRAMME_ADAPTER",
        "assessment_id": metadata.get("assessment_id"),
        "instrument_version": metadata.get("instrument_version"),
        "assessment_version": metadata.get("assessment_version"),
        "source_sha256": source_sha256,
        "claim_count": len(value.get("claims", [])),
        "evidence_count": len(value.get("evidence_register", [])),
    }
    return digest_payload(payload)
