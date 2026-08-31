"""Adversarial coverage for observatory-graph and temporal modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_IDENTIFIER,
    KIND_RESOLVED_ENTITY_REFERENCE,
    KIND_UNRESOLVED_LITERAL,
    IdentityError,
    UnresolvedLiteralError,
    assert_non_authoritative,
    attach_digest,
    build_assertion,
    build_entity,
    build_event,
    build_observation,
    build_relationship,
    build_source,
    compile_temporal_graph,
    dump_identity_ref,
    materialize_derived_projection,
    object_digest,
    parse_identity_ref,
    persistable,
    require_resolved_entity_id,
    state_valid_at,
    validate_graph_object,
    validate_or_raise,
    validate_temporal_integrity,
)
from neuroai_workbench.observatory_graph.digest import assert_digest
from neuroai_workbench.observatory_graph.loaders import (
    load_release_descriptor,
    load_release_manifest,
    read_jsonl_records,
)
from neuroai_workbench.release import ReleaseCompiler
from neuroai_workbench.temporal import (
    TIME_VALUE_BOUNDARY,
    TemporalValueError,
    parse_time_value,
)
from neuroai_workbench.temporal.time_value import is_time_value
from neuroai_workbench.util import atomic_write_json


def _resolved(entity_id: str) -> dict[str, str]:
    return {"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": entity_id, "boundary": GRAPH_BOUNDARY}


def _date(value: str = "2026-08-01") -> dict[str, str | None]:
    return {"value": value, "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}


def _ts(value: str = "2026-08-31T12:00:00Z") -> dict[str, str | None]:
    return {"value": value, "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY}


def test_digest_assert_and_identity_adversarial() -> None:
    record = attach_digest({"object_class": "Entity", "entity_id": "ENT-D", "label": "x"})
    assert assert_digest(record) == record["canonical_sha256"]
    with pytest.raises(ValueError, match="digest"):
        assert_digest({**record, "canonical_sha256": "0" * 64})

    with pytest.raises(IdentityError, match="object"):
        parse_identity_ref("ENT-1")
    with pytest.raises(IdentityError, match="Unknown"):
        parse_identity_ref({"kind": "OTHER", "boundary": GRAPH_BOUNDARY})
    with pytest.raises(IdentityError, match="unsupported"):
        parse_identity_ref({"kind": KIND_UNRESOLVED_LITERAL, "value": "x", "boundary": GRAPH_BOUNDARY, "extra": 1})
    with pytest.raises(IdentityError, match="boundary"):
        parse_identity_ref({"kind": KIND_UNRESOLVED_LITERAL, "value": "x", "boundary": " "})
    with pytest.raises(IdentityError, match="non-empty value"):
        parse_identity_ref({"kind": KIND_UNRESOLVED_LITERAL, "value": " ", "boundary": GRAPH_BOUNDARY})
    with pytest.raises(IdentityError, match="must not carry entity_id"):
        parse_identity_ref(
            {"kind": KIND_UNRESOLVED_LITERAL, "value": "x", "entity_id": "ENT-1", "boundary": GRAPH_BOUNDARY}
        )
    with pytest.raises(IdentityError, match="scheme"):
        parse_identity_ref({"kind": KIND_IDENTIFIER, "value": "abc", "boundary": GRAPH_BOUNDARY})
    with pytest.raises(IdentityError, match="non-empty value"):
        parse_identity_ref({"kind": KIND_IDENTIFIER, "value": "", "scheme": "DOI", "boundary": GRAPH_BOUNDARY})
    with pytest.raises(IdentityError, match="must not carry entity_id"):
        parse_identity_ref(
            {
                "kind": KIND_IDENTIFIER,
                "value": "10.1/x",
                "scheme": "DOI",
                "entity_id": "ENT-1",
                "boundary": GRAPH_BOUNDARY,
            }
        )
    with pytest.raises(IdentityError, match="entity_id"):
        parse_identity_ref({"kind": KIND_RESOLVED_ENTITY_REFERENCE, "boundary": GRAPH_BOUNDARY})
    with pytest.raises(IdentityError, match="must equal"):
        parse_identity_ref(
            {
                "kind": KIND_RESOLVED_ENTITY_REFERENCE,
                "entity_id": "ENT-1",
                "value": "ENT-2",
                "boundary": GRAPH_BOUNDARY,
            }
        )

    literal = dump_identity_ref({"kind": KIND_UNRESOLVED_LITERAL, "value": " Acme ", "boundary": GRAPH_BOUNDARY})
    assert literal["value"] == "Acme"
    identifier = dump_identity_ref(
        {"kind": KIND_IDENTIFIER, "value": "10.1/x", "scheme": "DOI", "boundary": GRAPH_BOUNDARY}
    )
    assert identifier["scheme"] == "DOI"
    resolved = dump_identity_ref(
        {"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": "ENT-1", "scheme": "INTERNAL", "boundary": GRAPH_BOUNDARY}
    )
    assert resolved["entity_id"] == "ENT-1"
    assert resolved["scheme"] == "INTERNAL"

    with pytest.raises(UnresolvedLiteralError):
        require_resolved_entity_id(literal, field="subject")
    assert require_resolved_entity_id(_resolved("ENT-9"), field="subject") == "ENT-9"


def test_loaders_non_authoritative(tmp_path: Path) -> None:
    release = tmp_path / "release"
    ReleaseCompiler().build(
        [build_entity(entity_id="ENT-L1", entity_type="SYSTEM", canonical_label="L")],
        release,
        candidate_id="CAND-L1",
    )
    descriptor = load_release_descriptor(release)
    assert isinstance(descriptor, dict)
    manifest = load_release_manifest(release)
    assert isinstance(manifest, dict)

    bad = tmp_path / "bad"
    bad.mkdir()
    atomic_write_json(bad / "descriptor.json", [])
    atomic_write_json(bad / "manifest.json", {})
    with pytest.raises(ValueError, match="descriptor"):
        load_release_descriptor(bad)
    atomic_write_json(bad / "descriptor.json", {})
    atomic_write_json(bad / "manifest.json", [])
    with pytest.raises(ValueError, match="manifest"):
        load_release_manifest(bad)

    assert read_jsonl_records(tmp_path / "missing.jsonl") == []
    jsonl = tmp_path / "rows.jsonl"
    jsonl.write_text('\n{"a":1}\n[]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        read_jsonl_records(jsonl)

    with pytest.raises(ValueError, match="Unsupported"):
        materialize_derived_projection(release, loader="oracle", target="x")  # type: ignore[arg-type]

    authorized = tmp_path / "authorized"
    ReleaseCompiler().build(
        [build_entity(entity_id="ENT-L2", entity_type="SYSTEM", canonical_label="L2")],
        authorized,
        candidate_id="CAND-L2",
    )
    desc = json.loads((authorized / "descriptor.json").read_text(encoding="utf-8"))
    desc["release_authorized"] = True
    atomic_write_json(authorized / "descriptor.json", desc)
    projection = materialize_derived_projection(authorized, loader="duckdb", target="mem")
    assert projection["authoritative"] is False
    assert projection["release_authorized"] is False
    assert (
        "non-authoritative" in projection["authorization_note"].lower()
        or "still non-authoritative" in projection["authorization_note"]
    )
    assert_non_authoritative(projection)
    with pytest.raises(ValueError, match="never claim"):
        assert_non_authoritative({**projection, "authoritative": True})
    with pytest.raises(ValueError, match="release_authorized"):
        assert_non_authoritative({**projection, "release_authorized": True})


def test_schema_and_object_builders_adversarial() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        validate_graph_object({}, "NotAClass")
    errors = validate_graph_object("x", "Entity")
    assert errors
    with pytest.raises(ValueError, match="validation failed"):
        validate_or_raise({"object_class": "Entity"}, "Entity")

    mixed = {
        "object_class": "Source",
        "source_id": "SRC-1",
        "source_class": "REGISTRY",
        "title": "t",
        "publisher": "p",
        "canonical_url_or_reference": "https://example.test",
        "access_class": "PUBLIC",
        "redistribution_state": "UNKNOWN_NOT_ADJUDICATED",
        "publication_or_record_date": _date(),
        "publication_or_record_date_timestamp": "2026-08-01T00:00:00Z",
        "boundary": GRAPH_BOUNDARY,
    }
    mixed_errors = validate_graph_object(mixed, "Source")
    assert any(item["code"] == "TEMPORAL_ERROR" for item in mixed_errors)

    bare_subject = {
        "object_class": "Assertion",
        "assertion_id": "AST-1",
        "subject_id": "ENT-1",
        "predicate": "P",
        "value": "V",
        "evidence_state": "SOURCE_STATED",
        "verification_state": "UNVERIFIED",
        "review_state": "NOT_REVIEWED",
        "claim_boundary": "b",
        "boundary": GRAPH_BOUNDARY,
    }
    assert any(item["code"] == "UNRESOLVED_LITERAL" for item in validate_graph_object(bare_subject, "Assertion"))

    entity_with_bad_subject = build_entity(entity_id="ENT-S", entity_type="SYSTEM", canonical_label="S")
    entity_with_bad_subject["subject"] = {"kind": "NOPE", "boundary": GRAPH_BOUNDARY}
    # Entity is not in RESOLVED_SUBJECT_CLASSES; identity parse errors are recorded.
    subject_errors = validate_graph_object(
        {k: v for k, v in entity_with_bad_subject.items() if k != "canonical_sha256"},
        "Entity",
    )
    assert any(item.get("code") == "IDENTITY_ERROR" for item in subject_errors)

    with pytest.raises(ValueError, match="object_ref or value"):
        build_assertion(
            assertion_id="AST-X",
            subject=_resolved("ENT-S"),
            predicate="P",
            evidence_state="SOURCE_STATED",
            verification_state="UNVERIFIED",
            review_state="NOT_REVIEWED",
            claim_boundary="b",
        )

    assertion = build_assertion(
        assertion_id="AST-OK",
        subject=_resolved("ENT-S"),
        predicate="P",
        value="V",
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        review_state="NOT_REVIEWED",
        claim_boundary="b",
        observed_at=_ts(),
        valid_from=_date("2026-01-01"),
        valid_until=_date("2026-12-31"),
    )
    assert "observed_at" in assertion
    event = build_event(
        event_id="EVT-1",
        event_type="STATUS_CHANGE",
        subject=_resolved("ENT-S"),
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        claim_boundary="b",
        occurred_at=_ts(),
    )
    assert event["occurred_at"]["precision"] == "TIMESTAMP"
    rel = build_relationship(
        relationship_id="REL-1",
        relationship_type="OWNS",
        subject=_resolved("ENT-S"),
        object_ref=_resolved("ENT-S"),
        evidence_state="SOURCE_STATED",
        claim_boundary="b",
        valid_from=_date("2026-01-01"),
        valid_until=_date("2026-06-01"),
    )
    assert rel["valid_until"]["value"] == "2026-06-01"
    persisted = persistable(assertion)
    assert object_digest(persisted) == persisted["canonical_sha256"]


def test_temporal_value_adversarial_paths() -> None:
    with pytest.raises(TemporalValueError, match="object"):
        parse_time_value("2026")
    with pytest.raises(TemporalValueError, match="non-empty"):
        parse_time_value({"value": " ", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="out of range"):
        parse_time_value({"value": "0000", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="real calendar"):
        parse_time_value({"value": "2026-02-30", "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="RFC 3339|ISO 8601"):
        parse_time_value({"value": "2026-08-31T99:00:00Z", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="timezone"):
        parse_time_value({"value": "2026-08-31T12:00:00", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY})
    assert not is_time_value({"value": "bad", "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY})


def test_temporal_compiler_integrity_and_windows() -> None:
    entity = build_entity(entity_id="ENT-T1", entity_type="SYSTEM", canonical_label="T")
    source = build_source(
        source_id="SRC-T1",
        source_class="REGISTRY",
        title="S",
        publisher="P",
        canonical_url_or_reference="https://example.test/t",
    )
    observation = build_observation(
        observation_id="OBS-T1",
        source_id="SRC-T1",
        observed_at=_ts(),
        retrieval_method="HTTP_GET",
        retrieval_outcome="RETRIEVED",
        requested_locator="https://example.test/t",
    )
    good = build_assertion(
        assertion_id="AST-T1",
        subject=_resolved("ENT-T1"),
        predicate="STATUS",
        value="ACTIVE",
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        review_state="NOT_REVIEWED",
        claim_boundary="b",
        valid_from=_date("2026-01-01"),
        valid_until=_date("2026-06-01"),
        source_ids=["SRC-T1"],
        observation_ids=["OBS-T1"],
    )
    compiled = compile_temporal_graph([entity, source, observation, good])
    assert compiled["mechanical_pass"] is True
    assert compiled["release_authorized"] is False

    inverted = {
        **good,
        "assertion_id": "AST-BAD",
        "valid_from": _date("2026-12-01"),
        "valid_until": _date("2026-01-01"),
    }
    inverted = attach_digest({k: v for k, v in inverted.items() if k != "canonical_sha256"})
    errors = validate_temporal_integrity([entity, source, observation, inverted])
    assert any("precedes" in item for item in errors)

    dangling = {
        **good,
        "assertion_id": "AST-DANGLE",
        "source_ids": ["SRC-MISSING"],
        "observation_ids": [],
    }
    dangling = attach_digest({k: v for k, v in dangling.items() if k != "canonical_sha256"})
    assert any("dangling" in item for item in validate_temporal_integrity([entity, dangling]))

    unknown = {"object_class": "Nope", "nope_id": "X"}
    assert any("Unknown object_class" in item for item in validate_temporal_integrity([unknown]))

    duplicate = validate_temporal_integrity([entity, entity])
    assert any("Duplicate" in item for item in duplicate)

    windowed = state_valid_at(
        [entity, source, observation, good],
        as_of=_date("2026-03-01"),
    )
    assert any(item.get("assertion_id") == "AST-T1" for item in windowed["objects"])
    outside = state_valid_at(
        [entity, source, observation, good],
        as_of=_date("2025-01-01"),
    )
    assert not any(item.get("assertion_id") == "AST-T1" for item in outside["objects"])
