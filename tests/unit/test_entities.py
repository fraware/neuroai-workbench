from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.entities import (
    AmbiguousResolutionError,
    FuzzyMergeRefusedError,
    OverwriteRefusedError,
    assert_record_immutable,
    initialize_registry,
    load_entity,
    refuse_fuzzy_merge,
    register_alias,
    register_entity,
    register_identifier,
    registry_status,
    resolve_exact,
    validate_registry,
)
from neuroai_workbench.util import atomic_write_json
from tests.fixtures.entities.helpers import seed_entity_workspace

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "entities"


def test_synthetic_fixture_validates() -> None:
    payload = json.loads((FIXTURES / "ENTITY_REGISTRY_SYNTHETIC.json").read_text(encoding="utf-8"))
    result = validate_registry(payload)
    assert result["valid"] is True


def test_exact_resolution_paths(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    assert resolve_exact(workspace, entity_id="ENT-SYNTH-ORG-001", actor="tester")["state"] == "EXISTING_ENTITY"
    assert resolve_exact(workspace, alias_id="ALIAS-SYNTH-001", actor="tester")["entity_id"] == "ENT-SYNTH-ORG-001"
    assert resolve_exact(workspace, identifier_scheme="DOMAIN", identifier_value="synthetic-neuro.example.org", actor="tester")["entity_id"] == "ENT-SYNTH-ORG-001"
    assert resolve_exact(workspace, alias_id="ALIAS-MISSING", actor="tester")["state"] == "UNRESOLVED"


def test_append_only_registration(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "MODEL", "Synthetic Decoder v1", entity_id="ENT-NEW-MODEL", actor="tester")
    register_alias(workspace, "ENT-NEW-MODEL", "SynDecoder", "ABBREVIATION", alias_id="ALIAS-NEW-001", actor="tester")
    register_identifier(workspace, "ENT-NEW-MODEL", "CUSTOM", "syn-decoder-v1", identifier_id="ID-NEW-001", actor="tester")
    assert registry_status(workspace)["entity_count"] == 1


def test_fuzzy_merge_refusal(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(FuzzyMergeRefusedError):
        resolve_exact(workspace, entity_id="ENT-SYNTH-ORG-001", normalized_name="Synthetic Neuro", actor="tester")
    with pytest.raises(FuzzyMergeRefusedError):
        resolve_exact(workspace, entity_id="ENT-SYNTH-ORG-001", similarity_threshold=0.85, actor="tester")
    with pytest.raises(FuzzyMergeRefusedError):
        resolve_exact(workspace, entity_id="ENT-SYNTH-ORG-001", match_mode="FUZZY_NAME", actor="tester")


def test_overwrite_refusal(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(OverwriteRefusedError):
        register_entity(workspace, "ORGANIZATION", "Duplicate Org", entity_id="ENT-SYNTH-ORG-001", actor="tester")
    with pytest.raises(OverwriteRefusedError):
        register_alias(workspace, "ENT-SYNTH-ORG-001", "Other Name", "TRADE_NAME", alias_id="ALIAS-SYNTH-001", actor="tester")
    entity = load_entity(workspace, "ENT-SYNTH-ORG-001")
    entity_path = workspace / "observatory" / "entities" / "records" / "ENT-SYNTH-ORG-001.json"
    atomic_write_json(entity_path, {**entity, "display_name": "Tampered Name"})
    with pytest.raises(OverwriteRefusedError):
        assert_record_immutable(entity_path, entity)


def test_path_traversal_refusal(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid entity_id"):
        load_entity(workspace, "../escape")
    with pytest.raises(ValueError, match="Invalid entity_id"):
        load_entity(workspace, "..")


def test_ambiguous_identifier_registration(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "ORGANIZATION", "Org A", entity_id="ENT-A", actor="tester")
    register_entity(workspace, "ORGANIZATION", "Org B", entity_id="ENT-B", actor="tester")
    register_identifier(workspace, "ENT-A", "DOMAIN", "shared.example.org", identifier_id="ID-A", actor="tester")
    with pytest.raises(AmbiguousResolutionError):
        register_identifier(workspace, "ENT-B", "DOMAIN", "shared.example.org", identifier_id="ID-B", actor="tester")


def test_registry_edge_cases(tmp_path: Path) -> None:
    assert validate_registry({"metadata": {}, "entities": "not-a-list"})["valid"] is False
    with pytest.raises(ValueError, match="not initialized"):
        from neuroai_workbench.entities import load_registry

        load_registry(tmp_path / "missing-workspace")
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "PRODUCT", "Widget", entity_id="ENT-W", actor="tester")
    entity_path = workspace / "observatory" / "entities" / "records" / "ENT-W.json"
    record = json.loads(entity_path.read_text(encoding="utf-8"))
    tampered = {**record, "entity_id": "ENT-TAMPER"}
    atomic_write_json(entity_path, tampered)
    with pytest.raises(ValueError, match="identifier mismatch"):
        load_entity(workspace, "ENT-W")
    with pytest.raises(FuzzyMergeRefusedError):
        refuse_fuzzy_merge(workspace, reason="only normalized", actor="tester")
    assert resolve_exact(workspace, identifier_scheme="DOMAIN", identifier_value="missing.example.org", actor="tester")["state"] == "UNRESOLVED"
    with pytest.raises(ValueError, match="Unsupported entity_type"):
        register_entity(workspace, "INVALID", "Bad", entity_id="ENT-BAD", actor="tester")
    with pytest.raises(ValueError, match="display_name"):
        register_entity(workspace, "PRODUCT", "  ", entity_id="ENT-EMPTY", actor="tester")
    with pytest.raises(ValueError, match="reason must not be empty"):
        refuse_fuzzy_merge(workspace, reason="  ", actor="tester")
    atomic_write_json(entity_path, record)
    with pytest.raises(ValueError, match="Unsupported alias_kind"):
        register_alias(workspace, "ENT-W", "Alias", "INVALID", alias_id="ALIAS-BAD", actor="tester")
    with pytest.raises(ValueError, match="Unsupported scheme"):
        register_identifier(workspace, "ENT-W", "INVALID", "value", identifier_id="ID-BAD", actor="tester")
    entity_path.unlink()
    with pytest.raises(OverwriteRefusedError, match="Missing canonical record"):
        assert_record_immutable(entity_path, record)
    atomic_write_json(entity_path, tampered)
    with pytest.raises(OverwriteRefusedError, match="was altered"):
        assert_record_immutable(entity_path, record)
    workspace2 = tmp_path / "workspace2"
    duplicate_seed = json.loads((FIXTURES / "ENTITY_REGISTRY_SYNTHETIC.json").read_text(encoding="utf-8"))
    initialize_registry(workspace2, seed=duplicate_seed, actor="tester")
    tampered_seed = json.loads(json.dumps(duplicate_seed))
    tampered_seed["entities"][0]["display_name"] = "Tampered Org Name"
    with pytest.raises(OverwriteRefusedError):
        initialize_registry(workspace2, seed=tampered_seed, actor="tester")
    assert registry_status(workspace)["initialized"] is True


def test_validate_registry_semantic_errors() -> None:
    payload = {
        "metadata": {"title": "x", "version": "1", "status": "x", "record_count": 1, "boundary": "b"},
        "entities": [
            {
                "entity_id": "bad/id",
                "entity_type": "UNKNOWN",
                "display_name": "Name",
                "status": "ACTIVE",
                "created_at": "2026-01-01T00:00:00Z",
                "boundary": "b",
            },
            {
                "entity_id": "ENT-DUP",
                "entity_type": "ORGANIZATION",
                "display_name": "Dup",
                "status": "ACTIVE",
                "created_at": "2026-01-01T00:00:00Z",
                "boundary": "b",
            },
            {
                "entity_id": "ENT-DUP",
                "entity_type": "ORGANIZATION",
                "display_name": "Dup2",
                "status": "ACTIVE",
                "created_at": "2026-01-01T00:00:00Z",
                "boundary": "b",
            },
        ],
    }
    result = validate_registry(payload)
    codes = {item["code"] for item in result["errors"]}
    assert {"INVALID_IDENTIFIER", "UNSUPPORTED_ENTITY_TYPE", "DUPLICATE_ENTITY_ID"} <= codes


def test_alias_mismatch_on_resolve(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    alias_path = workspace / "observatory" / "entities" / "aliases" / "ALIAS-SYNTH-001.json"
    alias = json.loads(alias_path.read_text(encoding="utf-8"))
    atomic_write_json(alias_path, {**alias, "alias_id": "ALIAS-TAMPER"})
    with pytest.raises(ValueError, match="Alias record identifier mismatch"):
        resolve_exact(workspace, alias_id="ALIAS-SYNTH-001", actor="tester")
    with pytest.raises(ValueError, match="identifier_scheme and identifier_value"):
        resolve_exact(workspace, identifier_scheme="DOMAIN", actor="tester")
    with pytest.raises(ValueError, match="Unsupported identifier_scheme"):
        resolve_exact(workspace, identifier_scheme="INVALID", identifier_value="x", actor="tester")


def test_registration_input_validation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "ORGANIZATION", "Org", entity_id="ENT-ORG", actor="tester")
    with pytest.raises(ValueError, match="alias_text"):
        register_alias(workspace, "ENT-ORG", "  ", "TRADE_NAME", alias_id="ALIAS-EMPTY", actor="tester")
    with pytest.raises(ValueError, match="value"):
        register_identifier(workspace, "ENT-ORG", "DOMAIN", "  ", identifier_id="ID-EMPTY", actor="tester")


def test_registry_status_invalid_event_chain(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    events_path = workspace / "observatory" / "entities" / "events.jsonl"
    events_path.write_text(events_path.read_text(encoding="utf-8") + '{"seq": 999}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="event chain is invalid"):
        registry_status(workspace)
