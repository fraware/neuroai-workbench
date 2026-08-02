from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.entities import (
    load_resolution_proposal,
    propose_resolution,
    record_resolution_disposition,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes
from tests.fixtures.entities.helpers import seed_entity_workspace


def test_path_traversal_refusal_on_proposal_load(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid proposal_id"):
        load_resolution_proposal(workspace, "../escape")


def test_double_disposition_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Synthetic Neuro",
        alias_id="ALIAS-SYNTH-001",
        actor="tester",
    )
    record_resolution_disposition(
        workspace,
        proposal["proposal_id"],
        "ACCEPT",
        rationale="Confirmed alias correspondence",
        actor="reviewer",
    )
    with pytest.raises(ValueError, match="already has a recorded disposition"):
        record_resolution_disposition(
            workspace,
            proposal["proposal_id"],
            "REJECT",
            rationale="Second attempt",
            actor="reviewer",
        )


def test_disposition_requires_rationale(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Novel Entity", actor="tester")
    with pytest.raises(ValueError, match="rationale"):
        record_resolution_disposition(workspace, proposal["proposal_id"], "DEFER", rationale="  ", actor="reviewer")


def test_tampered_proposal_schema_rejected_on_load(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(
        workspace,
        raw_mention="Synthetic Neuro",
        alias_id="ALIAS-SYNTH-001",
        actor="tester",
    )
    path = workspace / "observatory" / "entities" / "proposals" / f"{proposal['proposal_id']}.json"
    tampered = {k: v for k, v in proposal.items() if k != "boundary"}
    atomic_write_json(path, tampered)
    with pytest.raises(ValueError, match="Stored resolution proposal"):
        load_resolution_proposal(workspace, proposal["proposal_id"])


def test_duplicate_candidate_never_auto_merges_registry(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    before = list((workspace / "observatory" / "entities" / "records").glob("*.json"))
    proposal = propose_resolution(workspace, raw_mention="Synthetic Neuro Devices Inc.", actor="tester")
    after = list((workspace / "observatory" / "entities" / "records").glob("*.json"))
    assert proposal["resolution_state"] == "DUPLICATE_CANDIDATE"
    assert proposal["automatic_mutation_performed"] is False
    assert len(before) == len(after)


def test_non_exact_existing_entity_never_auto_confirms(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    for kwargs in (
        {"alias_id": "ALIAS-SYNTH-001"},
        {"identifier_scheme": "DOMAIN", "identifier_value": "synthetic-neuro.example.org"},
    ):
        proposal = propose_resolution(workspace, raw_mention="Synthetic Neuro", actor="tester", **kwargs)
        assert proposal["resolution_state"] == "EXISTING_ENTITY"
        assert proposal["auto_confirmed"] is False
        assert proposal["status"] == "PENDING_HUMAN_DISPOSITION"


def test_disposition_immutability(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    proposal = propose_resolution(workspace, raw_mention="Novel Entity", actor="tester")
    disposition = record_resolution_disposition(
        workspace,
        proposal["proposal_id"],
        "NEEDS_EVIDENCE",
        rationale="Awaiting public registry citation",
        actor="reviewer",
    )
    disposition_path = workspace / "observatory" / "entities" / "dispositions" / f"{disposition['disposition_id']}.json"
    stored = disposition_path.read_text(encoding="utf-8")
    assert disposition["proposal_sha256"] == sha256_bytes(canonical_json_bytes(proposal))
    assert "registry_mutation_performed" in stored


def test_empty_raw_mention_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="raw_mention"):
        propose_resolution(workspace, raw_mention="  ", actor="tester")


def test_multiple_selectors_refused(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="at most one"):
        propose_resolution(
            workspace,
            raw_mention="Synthetic Neuro",
            entity_id="ENT-SYNTH-ORG-001",
            alias_id="ALIAS-SYNTH-001",
            actor="tester",
        )
