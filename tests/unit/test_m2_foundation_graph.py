from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.delta import validate_delta_operation
from neuroai_workbench.delta.apply import _apply_operation
from neuroai_workbench.discovery import (
    DiscoveryError,
    list_programme_ids,
    load_first_wave_programmes,
    load_programme,
    programme_maturity,
    run_source_universe,
)
from neuroai_workbench.entities import (
    IDENTITY_RELATION_DISPOSITIONS,
    identity_relation_for,
    initialize_registry,
    propose_resolution,
    record_resolution_disposition,
)
from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    assert_non_authoritative,
    build_assertion,
    build_entity,
    build_observation,
    build_source,
    compile_temporal_graph,
    materialize_derived_projection,
    state_as_of_release,
    state_valid_at,
)
from neuroai_workbench.release import ReleaseCompiler
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _resolved(entity_id: str) -> dict[str, str]:
    return {"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": entity_id, "boundary": GRAPH_BOUNDARY}


def _date(value: str = "2026-08-01") -> dict[str, str | None]:
    return {"value": value, "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}


class FirstWaveProgrammesTests(unittest.TestCase):
    def test_five_programmes_with_su_trial_executable(self) -> None:
        ids = list_programme_ids()
        self.assertEqual(ids, ["SU-GRANTS", "SU-MODEL", "SU-PUBS", "SU-REG", "SU-TRIAL"])
        programmes = load_first_wave_programmes()
        self.assertEqual(len(programmes), 5)
        self.assertEqual(programme_maturity(load_programme("SU-TRIAL")), "EXECUTABLE_REFERENCE")
        self.assertEqual(programme_maturity(load_programme("SU-PUBS")), "OFFLINE_EXECUTABLE")
        result = run_source_universe(
            programme=load_programme("SU-PUBS"),
            execution_mode="OFFLINE_FIXTURE",
            pages=[
                {
                    "payload": {
                        "records": [
                            {
                                "identity": "10.1000/neuroai.m2.1",
                                "title": "M2 pubs",
                                "url": "https://doi.org/10.1000/neuroai.m2.1",
                            }
                        ],
                        "next_page_token": None,
                        "total_count": 1,
                    }
                }
            ],
        )
        self.assertGreaterEqual(result["coverage"]["included_candidate_count"], 1)
        with self.assertRaises(DiscoveryError):
            load_programme("SU-TRIALS")


class EntityIdentityDispositionTests(unittest.TestCase):
    def test_identity_relation_vocabulary_and_legacy_map(self) -> None:
        self.assertEqual(identity_relation_for("ACCEPT"), "SAME_ENTITY")
        self.assertEqual(identity_relation_for("REJECT"), "NOT_SAME_ENTITY")
        self.assertEqual(identity_relation_for("SAME_ENTITY"), "SAME_ENTITY")
        self.assertTrue({"SUCCESSOR_OF", "ACQUIRED_BY", "ALIAS_OF"} <= IDENTITY_RELATION_DISPOSITIONS)

    def test_record_disposition_stores_identity_relation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_registry(workspace)
            proposal = propose_resolution(workspace, raw_mention="Acme Neuro", actor="tester")
            disposition = record_resolution_disposition(
                workspace,
                proposal["proposal_id"],
                "NOT_SAME_ENTITY",
                rationale="Distinct organizations.",
                actor="tester",
            )
            self.assertEqual(disposition["decision"], "NOT_SAME_ENTITY")
            self.assertEqual(disposition["identity_relation"], "NOT_SAME_ENTITY")
            self.assertFalse(disposition["registry_mutation_performed"])


class TypedDeltaExpansionTests(unittest.TestCase):
    def test_new_operation_types_validate(self) -> None:
        cases = [
            ("ADD_ENTITY", {"record": {"entity_id": "ENT-1"}}),
            ("ADD_SOURCE", {"record": {"source_id": "SRC-1"}}),
            ("ADD_OBSERVATION", {"record": {"observation_id": "OBS-1"}}),
            ("ADD_ASSERTION", {"record": {"assertion_id": "ASR-1"}}),
            (
                "SUPERSEDE_ASSERTION",
                {
                    "record_id_field": "assertion_id",
                    "record_id": "ASR-1",
                    "superseded_by": "ASR-2",
                    "tombstone": {"assertion_id": "ASR-1"},
                },
            ),
            (
                "SUPERSEDE_ENTITY",
                {
                    "record_id_field": "entity_id",
                    "record_id": "ENT-1",
                    "superseded_by": "ENT-2",
                    "tombstone": {"entity_id": "ENT-1"},
                },
            ),
            (
                "RECORD_SOURCE_SUCCESSOR_ROUTE",
                {
                    "predecessor_source_id": "SRC-1",
                    "successor_source_id": "SRC-2",
                    "route_id": "ROUTE-1",
                    "rationale": "URL moved.",
                },
            ),
            ("RECORD_REOPENING_DECISION", {"reopening_decision": {"decision": "NO_REOPENING"}}),
            (
                "RECORD_NO_CHANGE_COMPARISON",
                {
                    "source_id": "SRC-1",
                    "comparison_scope": "bytes_digest",
                    "comparison_result": "NO_CHANGE",
                    "rationale": "Identical digest.",
                },
            ),
        ]
        for operation_type, fields in cases:
            errors = validate_delta_operation(
                {
                    "operation_id": "OP-000001",
                    "operation_type": operation_type,
                    "target_section": "sources",
                    **fields,
                }
            )
            self.assertEqual(errors, [], msg=operation_type)

    def test_apply_preserves_predecessor_on_supersede_entity(self) -> None:
        predecessor = {"entities": [{"entity_id": "ENT-1", "label": "A"}]}
        successor = {"entities": [{"entity_id": "ENT-1", "label": "A"}]}
        _apply_operation(
            successor,
            {
                "operation_type": "SUPERSEDE_ENTITY",
                "target_section": "entities",
                "record_id_field": "entity_id",
                "record_id": "ENT-1",
                "superseded_by": "ENT-2",
                "tombstone": {"entity_id": "ENT-1", "superseded": True},
            },
            predecessor,
        )
        self.assertEqual(successor["entities"][0]["entity_id"], "ENT-1")
        self.assertEqual(successor["entities"][0]["superseded_by"], "ENT-2")
        self.assertEqual(predecessor["entities"][0].get("superseded_by"), None)


class TemporalGraphCompilerTests(unittest.TestCase):
    def test_compile_and_derived_loader_non_authoritative(self) -> None:
        entity = build_entity(entity_id="ENT-GRAPH-1", entity_type="ORGANIZATION", canonical_label="Org")
        source = build_source(
            source_id="SRC-GRAPH-1",
            source_class="REGISTRY",
            title="Source",
            publisher="Pub",
            canonical_url_or_reference="https://example.test/s",
        )
        observation = build_observation(
            observation_id="OBS-GRAPH-1",
            source_id="SRC-GRAPH-1",
            observed_at=_date("2026-08-01"),
            retrieval_method="HTTPS_GET",
            retrieval_outcome="RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            requested_locator="https://example.test/s",
            content_sha256="a" * 64,
        )
        assertion = build_assertion(
            assertion_id="ASR-GRAPH-1",
            subject=_resolved("ENT-GRAPH-1"),
            predicate="listed_in",
            value="SRC-GRAPH-1",
            source_ids=["SRC-GRAPH-1"],
            observation_ids=["OBS-GRAPH-1"],
            evidence_state="OBSERVED",
            verification_state="UNVERIFIED",
            review_state="NOT_REVIEWED",
            claim_boundary="claim",
            prohibited_inferences=[],
            valid_from=_date("2026-01-01"),
            valid_until=_date("2026-12-31"),
        )
        objects = [entity, source, observation, assertion]
        compiled = compile_temporal_graph(objects)
        self.assertTrue(compiled["mechanical_pass"])
        self.assertFalse(compiled["release_authorized"])
        as_of = state_as_of_release(objects)
        self.assertEqual(as_of["projection"], "STATE_AS_OF_RELEASE")
        valid = state_valid_at(objects, as_of=_date("2026-06-15"))
        self.assertEqual(valid["projection"], "STATE_VALID_AT")
        self.assertFalse(valid["authoritative"])

        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "cand"
            ReleaseCompiler().build(objects, output, candidate_id="CAND-M2-TEST")
            projection = materialize_derived_projection(output, loader="duckdb", target="memory")
            assert_non_authoritative(projection)
            self.assertFalse(projection["authoritative"])
            with self.assertRaises(ValueError):
                assert_non_authoritative({**projection, "authoritative": True})
