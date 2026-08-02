from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.entities import (
    FuzzyMergeRefusedError,
    initialize_registry,
    load_blinded_benchmark_stub,
    load_resolution_proposal,
    normalize_mention,
    propose_resolution,
    record_resolution_disposition,
    register_entity,
    resolver_status,
    run_blinded_benchmark,
)
from neuroai_workbench.util import atomic_write_json
from tests.fixtures.entities.helpers import seed_entity_workspace


def test_normalize_mention_deterministic() -> None:
    assert normalize_mention("  Synthetic Neuro Devices Inc. ") == "synthetic neuro devices inc"


def test_exact_entity_id_auto_confirms(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Synthetic Neuro Devices Inc.",
        entity_id="ENT-SYNTH-ORG-001",
        actor="tester",
    )
    assert proposal["resolution_state"] == "EXISTING_ENTITY"
    assert proposal["match_layer"] == "EXACT_ENTITY_ID"
    assert proposal["auto_confirmed"] is True
    assert proposal["status"] == "AUTO_CONFIRMED"
    assert proposal["automatic_mutation_performed"] is False


def test_alias_match_requires_human_disposition(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Synthetic Neuro",
        alias_id="ALIAS-SYNTH-001",
        actor="tester",
    )
    assert proposal["resolution_state"] == "EXISTING_ENTITY"
    assert proposal["match_layer"] == "EXACT_ALIAS_ID"
    assert proposal["auto_confirmed"] is False
    assert proposal["status"] == "PENDING_HUMAN_DISPOSITION"


def test_identifier_match_requires_human_disposition(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="synthetic-neuro.example.org",
        identifier_scheme="DOMAIN",
        identifier_value="synthetic-neuro.example.org",
        actor="tester",
    )
    assert proposal["resolution_state"] == "EXISTING_ENTITY"
    assert proposal["match_layer"] == "EXACT_IDENTIFIER"
    assert proposal["auto_confirmed"] is False


def test_normalized_name_duplicate_candidate(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Synthetic Neuro Devices Inc.", actor="tester")
    assert proposal["resolution_state"] == "DUPLICATE_CANDIDATE"
    assert proposal["match_layer"] == "NORMALIZED_NAME"
    assert proposal["candidate_entity_ids"] == ["ENT-SYNTH-ORG-001"]
    assert proposal["auto_confirmed"] is False


def test_new_entity_when_no_match(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Totally Novel Organization", actor="tester")
    assert proposal["resolution_state"] == "NEW_ENTITY"
    assert proposal["match_layer"] == "NO_MATCH"
    assert proposal["auto_confirmed"] is False


def test_ambiguous_normalized_name_matches(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "ORGANIZATION", "Shared Name Corp", entity_id="ENT-A", actor="tester")
    register_entity(workspace, "ORGANIZATION", "Shared Name Corp", entity_id="ENT-B", actor="tester")
    proposal = propose_resolution(workspace, raw_mention="Shared Name Corp", actor="tester")
    assert proposal["resolution_state"] == "AMBIGUOUS"
    assert proposal["match_layer"] == "NORMALIZED_NAME"
    assert set(proposal["candidate_entity_ids"]) == {"ENT-A", "ENT-B"}


def test_record_disposition_without_registry_mutation(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Synthetic Neuro",
        alias_id="ALIAS-SYNTH-001",
        actor="tester",
    )
    disposition = record_resolution_disposition(
        workspace,
        proposal["proposal_id"],
        "ACCEPT",
        rationale="Alias matches cited public source",
        actor="reviewer",
    )
    assert disposition["registry_mutation_performed"] is False
    updated = load_resolution_proposal(workspace, proposal["proposal_id"])
    assert updated["status"] == "DISPOSITION_RECORDED"


def test_blinded_benchmark_stub_loads() -> None:
    stub = load_blinded_benchmark_stub()
    assert stub["benchmark_id"] == "ENTITY-RES-BENCH-BLIND-001"
    assert len(stub["cases"]) == 5


def test_blinded_benchmark_runs_on_synthetic_workspace(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    report = run_blinded_benchmark(workspace, actor="tester")
    assert report["passed"] is True
    assert report["counts"]["total"] == 5
    assert report["metrics_stub"]["precision"] is None
    assert report["metrics_stub"]["recall"] is None


def test_resolver_status_counts(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    propose_resolution(
        workspace, raw_mention="Synthetic Neuro Devices Inc.", entity_id="ENT-SYNTH-ORG-001", actor="tester"
    )
    propose_resolution(workspace, raw_mention="Synthetic Neuro", alias_id="ALIAS-SYNTH-001", actor="tester")
    status = resolver_status(workspace)
    assert status["proposal_count"] == 2
    assert status["auto_confirmed_count"] == 1
    assert status["pending_disposition_count"] == 1


def test_fuzzy_inputs_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(FuzzyMergeRefusedError):
        propose_resolution(
            workspace,
            raw_mention="Synthetic Neuro",
            entity_id="ENT-SYNTH-ORG-001",
            similarity_threshold=0.9,
            actor="tester",
        )
    with pytest.raises(FuzzyMergeRefusedError):
        propose_resolution(
            workspace,
            raw_mention="Synthetic Neuro",
            normalized_name="synthetic neuro",
            actor="tester",
        )
    with pytest.raises(FuzzyMergeRefusedError):
        propose_resolution(
            workspace,
            raw_mention="Synthetic Neuro",
            match_mode="FUZZY_NAME",
            actor="tester",
        )


def test_proposal_persisted_and_loadable(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Novel Entity", actor="tester")
    loaded = load_resolution_proposal(workspace, proposal["proposal_id"])
    assert loaded["proposal_id"] == proposal["proposal_id"]
    path = workspace / "observatory" / "entities" / "proposals" / f"{proposal['proposal_id']}.json"
    assert path.is_file()


def test_ambiguous_identifier_collision(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "ORGANIZATION", "Org A", entity_id="ENT-A", actor="tester")
    register_entity(workspace, "ORGANIZATION", "Org B", entity_id="ENT-B", actor="tester")
    identifiers_dir = workspace / "observatory" / "entities" / "identifiers"
    identifiers_dir.mkdir(parents=True, exist_ok=True)
    for entity_id, identifier_id in (("ENT-A", "ID-A"), ("ENT-B", "ID-B")):
        atomic_write_json(
            identifiers_dir / f"{identifier_id}.json",
            {
                "identifier_id": identifier_id,
                "entity_id": entity_id,
                "scheme": "DOMAIN",
                "value": "shared.example.org",
                "status": "ACTIVE",
                "registered_at": "2026-08-01T12:00:00Z",
                "jurisdiction": None,
                "evidence_ref": None,
                "predecessor_identifier_id": None,
                "boundary": "test",
            },
        )
    proposal = propose_resolution(
        workspace,
        raw_mention="shared.example.org",
        identifier_scheme="DOMAIN",
        identifier_value="shared.example.org",
        actor="tester",
    )
    assert proposal["resolution_state"] == "AMBIGUOUS"
    assert set(proposal["candidate_entity_ids"]) == {"ENT-A", "ENT-B"}


def test_ambiguous_accept_requires_selected_entity(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_registry(workspace, actor="tester")
    register_entity(workspace, "ORGANIZATION", "Shared Name Corp", entity_id="ENT-A", actor="tester")
    register_entity(workspace, "ORGANIZATION", "Shared Name Corp", entity_id="ENT-B", actor="tester")
    proposal = propose_resolution(workspace, raw_mention="Shared Name Corp", actor="tester")
    with pytest.raises(ValueError, match="selected_entity_id"):
        record_resolution_disposition(
            workspace,
            proposal["proposal_id"],
            "ACCEPT",
            rationale="Trying to accept without choosing",
            actor="reviewer",
        )


def test_unknown_entity_id_proposes_new_entity(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Missing Entity",
        entity_id="ENT-MISSING",
        actor="tester",
    )
    assert proposal["resolution_state"] == "NEW_ENTITY"
    assert proposal["match_layer"] == "EXACT_ENTITY_ID"
    assert proposal["auto_confirmed"] is False


def test_unknown_alias_proposes_new_entity(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Missing Alias",
        alias_id="ALIAS-MISSING",
        actor="tester",
    )
    assert proposal["resolution_state"] == "NEW_ENTITY"
    assert proposal["match_layer"] == "EXACT_ALIAS_ID"


def test_unknown_identifier_proposes_new_entity(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="missing.example.org",
        identifier_scheme="DOMAIN",
        identifier_value="missing.example.org",
        actor="tester",
    )
    assert proposal["resolution_state"] == "NEW_ENTITY"
    assert proposal["match_layer"] == "EXACT_IDENTIFIER"


def test_load_unknown_proposal_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="Unknown resolution proposal"):
        load_resolution_proposal(workspace, "RES-deadbeeffeeddeadbeefdeadbeef1234")


def test_invalid_disposition_decision_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Novel Entity", actor="tester")
    with pytest.raises(ValueError, match="Unsupported disposition decision"):
        record_resolution_disposition(
            workspace,
            proposal["proposal_id"],
            "INVALID",
            rationale="Bad decision",
            actor="reviewer",
        )


def test_benchmark_invalid_case_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = seed_entity_workspace(tmp_path)

    def broken_stub() -> dict:
        return {
            "benchmark_id": "X",
            "version": "1",
            "cases": [{"case_id": "bad", "input": "not-object", "expected": {}}],
        }

    monkeypatch.setattr("neuroai_workbench.entities.benchmark.load_blinded_benchmark_stub", broken_stub)
    report = run_blinded_benchmark(workspace, actor="tester")
    assert report["passed"] is False
    assert report["counts"]["failed"] == 1


def test_disposition_rejects_invalid_selected_entity(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Synthetic Neuro Devices Inc.", actor="tester")
    with pytest.raises(ValueError, match="candidate_entity_ids"):
        record_resolution_disposition(
            workspace,
            proposal["proposal_id"],
            "ACCEPT",
            rationale="Wrong entity",
            selected_entity_id="ENT-OTHER",
            actor="reviewer",
        )
