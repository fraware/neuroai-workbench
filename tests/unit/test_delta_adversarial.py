from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.delta import DeltaCompileError, DeltaValidationError, compile_adjudicated_delta
from neuroai_workbench.util import load_json

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"


def _minimal_package(candidate_id: str, decision: str = "ACCEPT") -> dict[str, Any]:
    return {
        "metadata": {
            "title": "Synthetic refresh package",
            "version": "refresh-adv",
            "evidence_cutoff": "2026-08-02",
            "generated_at": "2026-08-02T10:00:00Z",
            "generated_by": "tester",
            "status": "REVIEW_CANDIDATE_NOT_CANONICAL",
        },
        "registry_reference": {"sha256": "d" * 64, "source_count": 1},
        "change_candidates": [
            {
                "candidate_id": candidate_id,
                "created_at": "2026-08-02T08:00:00Z",
                "created_by": "tester",
                "source_id": "SRC-0001",
                "source_snapshot_ids": ["SNAP-1"],
                "current_snapshot_sha256": "e" * 64,
                "detection": {},
                "summary": "Adversarial fixture.",
                "proposed_change_class": "UNCLASSIFIED",
                "proposed_materiality": "UNDETERMINED",
                "proposed_reopening_effect": "UNDETERMINED",
                "extracted_claims": [],
                "status": "PENDING_HUMAN_ADJUDICATION",
                "automatic_mutation_performed": False,
                "boundary": "Boundary.",
            }
        ],
        "adjudications": [
            {
                "adjudication_id": f"ADJ-{candidate_id.removeprefix('CAND-')}",
                "candidate_id": candidate_id,
                "candidate_sha256": "f" * 64,
                "decided_at": "2026-08-02T09:00:00Z",
                "decided_by": "reviewer",
                "decision": decision,
                "change_class": "REGULATORY_OR_MARKET_EVENT",
                "materiality": "MATERIAL",
                "reopening_effect": "NO_EFFECT",
                "rationale": "Adversarial test.",
                "canonical_observatory_mutation_performed": False,
                "boundary": "Boundary.",
            }
        ],
        "accepted_changes": [],
        "unresolved_candidates": [],
        "reopening_queue": [],
        "counts": {},
        "withheld_claims": ["Synthetic."],
        "boundary": "Boundary.",
    }


def test_tampered_predecessor_hash_differs_from_recompile() -> None:
    predecessor = load_json(FIXTURES / "synthetic_predecessor_release.json")
    package = _minimal_package("CAND-" + "1" * 32)
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    delta["predecessor"]["sha256"] = "0" * 64
    recomputed = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    assert delta["predecessor"]["sha256"] != recomputed["predecessor"]["sha256"]


def test_duplicate_operation_ids_rejected() -> None:
    with pytest.raises(DeltaValidationError, match="semantic validation"):
        compile_adjudicated_delta(
            _minimal_package("CAND-" + "2" * 32),
            load_json(FIXTURES / "synthetic_predecessor_release.json"),
            predecessor_release_id="v1.0-synthetic",
            operation_specs={
                "CAND-" + "2" * 32: [
                    {
                        "operation_id": "OP-000001",
                        "operation_type": "ADD_RECORD",
                        "target_section": "sources",
                        "record": {"source_id": "SRC-0100"},
                    },
                    {
                        "operation_id": "OP-000001",
                        "operation_type": "ADD_RECORD",
                        "target_section": "sources",
                        "record": {"source_id": "SRC-0101"},
                    },
                ]
            },
        )


def test_invalid_adjudication_decision_rejected() -> None:
    package = _minimal_package("CAND-" + "3" * 32)
    package["adjudications"][0]["decision"] = "AUTO_ACCEPT"
    with pytest.raises(DeltaCompileError, match="Unsupported adjudication decision"):
        compile_adjudicated_delta(
            package,
            load_json(FIXTURES / "synthetic_predecessor_release.json"),
            predecessor_release_id="v1.0-synthetic",
        )
