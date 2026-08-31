from __future__ import annotations

import json

import pytest

from neuroai_workbench import __version__
from neuroai_workbench.observatory_migration import (
    MIGRATION_BOUNDARY,
    ObservatoryMigrationError,
    materialize_predecessor_source,
    materialize_predecessor_sources,
    predecessor_time_value,
    verify_predecessor_trace,
    write_predecessor_source_package,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes

IDENTITIES = {
    "v14_input_sha256": "a" * 64,
    "v16_input_sha256": "b" * 64,
    "producer_commit": "c" * 40,
    "runtime_execution_pin": "d" * 40,
    "s2_predecessor_commit": "e" * 40,
}


def _v14_source(source_id: str = "SRC-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Official page",
        "publisher": "Publisher",
        "url": "https://example.test/source",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "supports": "Current official representation",
        "claim_boundary": "Retrieval does not establish substantive truth.",
        "legacy_source_ids": ["LEGACY-1"],
    }


def _v16_source(source_id: str = "SRC-16-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Official announcement",
        "publisher": "Publisher",
        "url": "https://example.test/announcement",
        "published": "2026-07-22",
        "retrieved": "2026-07-29T12:38:00Z",
        "source_class": "OFFICIAL_COMPANY_ANNOUNCEMENT",
        "evidence_state": "COMPANY_ANNOUNCEMENT",
        "supports": "Bounded source statement",
        "claim_boundary": "No broader inference.",
    }


def test_predecessor_time_value_preserves_precision() -> None:
    assert predecessor_time_value("2026")["precision"] == "YEAR"
    assert predecessor_time_value("2026-07-22")["precision"] == "DATE"
    timestamp = predecessor_time_value("2026-07-29T12:38:00Z")
    assert timestamp["precision"] == "TIMESTAMP"
    assert timestamp["value"] == "2026-07-29T12:38:00Z"
    assert predecessor_time_value(None) is None


def test_predecessor_time_value_refuses_ambiguous_literal() -> None:
    with pytest.raises(ObservatoryMigrationError, match="Unsupported predecessor temporal literal"):
        predecessor_time_value("July 2026")
    with pytest.raises(ObservatoryMigrationError, match="string or null"):
        predecessor_time_value(2026)


def test_v14_source_materialization_does_not_promote_retrieved_to_publication_date() -> None:
    predecessor = _v14_source()

    source, trace = materialize_predecessor_source(predecessor, role="V14", record_index=0)

    assert source["source_id"] == predecessor["source_id"]
    assert source["canonical_url_or_reference"] == predecessor["url"]
    assert source["access_class"] == "UNKNOWN"
    assert source["redistribution_state"] == "UNKNOWN_NOT_ADJUDICATED"
    assert "publication_or_record_date" not in source
    assert source["boundary"] == MIGRATION_BOUNDARY
    assert trace["predecessor_record"] == predecessor
    assert trace["native_authority"] is False
    assert len(trace["predecessor_record_sha256"]) == 64
    assert verify_predecessor_trace(trace, expected_native_object_id=source["source_id"]) == []


def test_v16_explicit_publication_date_is_preserved() -> None:
    predecessor = _v16_source()

    source, trace = materialize_predecessor_source(predecessor, role="V16", record_index=3)

    assert source["publication_or_record_date"]["value"] == "2026-07-22"
    assert source["publication_or_record_date"]["precision"] == "DATE"
    assert trace["family"] == "new_sources"
    assert trace["record_index"] == 3


def test_unsupported_source_role_fails_closed() -> None:
    with pytest.raises(ObservatoryMigrationError, match="Unsupported predecessor source role"):
        materialize_predecessor_source(_v14_source(), role="UNKNOWN", record_index=0)


def test_trace_verifier_detects_tampering_and_binding_substitution() -> None:
    source, trace = materialize_predecessor_source(_v14_source(), role="V14", record_index=0)

    tampered = {**trace, "predecessor_record": {**trace["predecessor_record"], "title": "Substituted"}}
    assert "predecessor_record_sha256 mismatch" in verify_predecessor_trace(tampered)
    assert "native_object_id binding mismatch" in verify_predecessor_trace(
        trace,
        expected_native_object_id="SRC-SUBSTITUTED",
    )

    wrong_role = {**trace, "role": "V16"}
    assert "migration trace family/role mismatch" in verify_predecessor_trace(wrong_role)

    elevated = {**trace, "native_authority": True}
    assert "native_authority must remain false for migration traces" in verify_predecessor_trace(elevated)
    assert source["source_id"] == "SRC-1"


def test_materialize_predecessor_sources_is_noncanonical_and_complete() -> None:
    result = materialize_predecessor_sources(
        v14_release={"sources": [_v14_source("SRC-1"), _v14_source("SRC-2")]},
        v16_refresh={"new_sources": [_v16_source("SRC-16-1")]},
    )

    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["object_class"] == "Source"
    assert result["object_count"] == 3
    assert result["predecessor_trace_count"] == 3
    assert result["retrieved_not_promoted_to_publication_time"] is True
    assert {source["source_id"] for source in result["sources"]} == {"SRC-1", "SRC-2", "SRC-16-1"}
    assert all(trace["predecessor_record"] for trace in result["predecessor_traces"])


def test_source_package_is_deterministic_manifest_bound_and_identity_explicit(tmp_path) -> None:
    result = materialize_predecessor_sources(
        v14_release={"sources": [_v14_source("SRC-1")]},
        v16_refresh={"new_sources": [_v16_source("SRC-16-1")]},
    )
    first = write_predecessor_source_package(result, tmp_path / "first", **IDENTITIES)
    second = write_predecessor_source_package(result, tmp_path / "second", **IDENTITIES)

    assert first == second
    for filename in ("sources.jsonl", "predecessor-traces.jsonl", "descriptor.json", "manifest.json"):
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()

    descriptor = json.loads((tmp_path / "first" / "descriptor.json").read_text(encoding="utf-8"))
    assert descriptor["workbench_compatibility_version"] == __version__
    assert descriptor["producer_workbench_commit"] == IDENTITIES["producer_commit"]
    assert descriptor["runtime_execution_pin"] == IDENTITIES["runtime_execution_pin"]
    assert descriptor["s2_predecessor_commit"] == IDENTITIES["s2_predecessor_commit"]
    assert descriptor["observatory_graph_schema_version"] == "1"

    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
    assert manifest["release_authorized"] is False


def test_source_package_refuses_trace_tampering(tmp_path) -> None:
    result = materialize_predecessor_sources(
        v14_release={"sources": [_v14_source()]},
        v16_refresh={"new_sources": []},
    )
    result["predecessor_traces"][0]["predecessor_record"]["title"] = "Tampered"

    with pytest.raises(ObservatoryMigrationError, match="trace verification failed"):
        write_predecessor_source_package(result, tmp_path / "bad", **IDENTITIES)


def test_source_package_refuses_authority_upgrade(tmp_path) -> None:
    result = materialize_predecessor_sources(
        v14_release={"sources": [_v14_source()]},
        v16_refresh={"new_sources": []},
    )
    result["release_authorized"] = True

    with pytest.raises(ObservatoryMigrationError, match="noncanonical, unauthorized input"):
        write_predecessor_source_package(result, tmp_path / "bad", **IDENTITIES)


def test_source_package_refuses_malformed_identity_bindings(tmp_path) -> None:
    result = materialize_predecessor_sources(
        v14_release={"sources": [_v14_source()]},
        v16_refresh={"new_sources": []},
    )
    bad = {**IDENTITIES, "producer_commit": "NOT-A-COMMIT"}
    with pytest.raises(ObservatoryMigrationError, match="producer_commit must be"):
        write_predecessor_source_package(result, tmp_path / "bad", **bad)


def test_duplicate_source_ids_fail_closed() -> None:
    with pytest.raises(ObservatoryMigrationError, match="Duplicate predecessor source id SRC-X"):
        materialize_predecessor_sources(
            v14_release={"sources": [_v14_source("SRC-X")]},
            v16_refresh={"new_sources": [_v16_source("SRC-X")]},
        )


def test_missing_required_source_fields_fail_closed() -> None:
    broken = _v14_source()
    broken["publisher"] = ""

    with pytest.raises(ObservatoryMigrationError, match="missing required predecessor fields"):
        materialize_predecessor_source(broken, role="V14", record_index=0)


def test_source_arrays_are_required() -> None:
    with pytest.raises(ObservatoryMigrationError, match="Expected v1.4 sources and v1.6 new_sources arrays"):
        materialize_predecessor_sources(v14_release={}, v16_refresh={"new_sources": []})
