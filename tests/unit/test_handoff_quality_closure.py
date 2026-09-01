from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.delta.apply import DeltaApplyError, _apply_operation
from neuroai_workbench.discovery import (
    DiscoveryError,
    initialize_discovery_workspace,
    list_programme_ids,
    load_programme,
    programme_maturity,
    run_source_universe,
    seed_fixture_queries,
)
from neuroai_workbench.entities import (
    DIRECTED_IDENTITY_RELATIONS,
    IDENTITY_RELATION_DISPOSITIONS,
    initialize_registry,
    propose_resolution,
    record_resolution_disposition,
    refuse_fuzzy_merge,
    register_entity,
    report_batch_collisions,
)
from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    build_assertion,
    build_entity,
    build_observation,
    build_source,
    compile_temporal_graph,
    predecessor_successor_diff,
    validate_temporal_integrity,
)
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _pages(records: list[dict], *, total: int | None = None, next_token: str | None = None) -> list[dict]:
    payload: dict = {"records": records, "next_page_token": next_token}
    if total is not None:
        payload["total_count"] = total
    return [{"payload": payload}]


def _date(value: str = "2026-08-01") -> dict[str, str | None]:
    return {"value": value, "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}


class OfflineProgrammeProjectionTests(unittest.TestCase):
    def test_five_programmes_offline_executable(self) -> None:
        self.assertEqual(list_programme_ids(), ["SU-GRANTS", "SU-MODEL", "SU-PUBS", "SU-REG", "SU-TRIAL"])
        self.assertEqual(programme_maturity(load_programme("SU-TRIAL")), "EXECUTABLE_REFERENCE")
        for universe_id, pages in {
            "SU-PUBS": _pages(
                [
                    {
                        "identity": "10.1000/neuroai.pubs.1",
                        "title": "Pub fixture",
                        "url": "https://doi.org/10.1000/neuroai.pubs.1",
                    },
                    {
                        "identity": "PMID:12345678",
                        "title": "PMID fixture",
                        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    },
                ],
                total=2,
            ),
            "SU-REG": _pages(
                [
                    {
                        "identity": "K123456",
                        "title": "Device fixture",
                        "url": "https://api.fda.gov/device/510k.json?search=K123456",
                    }
                ],
                total=1,
            ),
            "SU-GRANTS": _pages(
                [
                    {
                        "identity": "R01NS999999",
                        "title": "Grant fixture",
                        "url": "https://reporter.nih.gov/project-details/R01NS999999",
                    }
                ],
                total=1,
            ),
            "SU-MODEL": _pages(
                [
                    {
                        "identity": "org/model-v1",
                        "title": "Model fixture",
                        "url": "https://example.test/models/org/model-v1",
                        "checkpoint": "abc",
                        "license": "Apache-2.0",
                        "lineage": "synthetic",
                    }
                ],
                total=1,
            ),
        }.items():
            with self.subTest(universe_id=universe_id):
                programme = load_programme(universe_id)
                self.assertEqual(programme_maturity(programme), "OFFLINE_EXECUTABLE")
                result = run_source_universe(
                    programme=programme,
                    execution_mode="OFFLINE_FIXTURE",
                    pages=pages,
                )
                self.assertTrue(result["candidates_only"])
                self.assertGreaterEqual(result["coverage"]["included_candidate_count"], 1)
                self.assertFalse(result["coverage"]["corpus_completeness_claim"])
                self.assertIn("failure_taxonomy_classes", result["coverage"])
                self.assertFalse(result["coverage"]["automatic_registry_mutation_performed"])

    def test_conflicting_identity_fails_closed(self) -> None:
        pages = [
            {
                "payload": {
                    "records": [
                        {"identity": "K123456", "title": "A", "url": "https://example.test/a"},
                        {"identity": "K123456", "title": "B", "url": "https://example.test/b"},
                    ],
                    "next_page_token": None,
                    "total_count": 2,
                }
            }
        ]
        with self.assertRaises(DiscoveryError):
            run_source_universe(programme=load_programme("SU-REG"), execution_mode="OFFLINE_REPLAY", pages=pages)

    def test_authorized_network_refused_for_offline_universes(self) -> None:
        with self.assertRaises(DiscoveryError):
            run_source_universe(
                programme=load_programme("SU-PUBS"),
                execution_mode="AUTHORIZED_NETWORK",
                pages=_pages([{"identity": "PMID:1", "title": "x", "url": "https://example.test/x"}]),
            )

    def test_offline_universe_with_workspace_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_discovery_workspace(workspace)
            seed_fixture_queries(workspace)
            result = run_source_universe(
                programme=load_programme("SU-PUBS"),
                execution_mode="OFFLINE_FIXTURE",
                pages=_pages(
                    [
                        {
                            "identity": "10.1000/neuroai.ws.1",
                            "title": "WS",
                            "url": "https://doi.org/10.1000/neuroai.ws.1",
                        }
                    ],
                    total=1,
                ),
                workspace=workspace,
            )
            self.assertIsNotNone(result["workflow"])
            self.assertFalse(result["workflow"]["run"]["automatic_registry_mutation_performed"])


class EntityIdentityRelationTests(unittest.TestCase):
    def test_directed_relations_require_related_and_never_fuzzy_merge(self) -> None:
        self.assertTrue({"SUCCESSOR_OF", "ACQUIRED_BY", "SUBSIDIARY_OF", "ALIAS_OF"} <= DIRECTED_IDENTITY_RELATIONS)
        self.assertTrue(IDENTITY_RELATION_DISPOSITIONS >= DIRECTED_IDENTITY_RELATIONS)
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_registry(workspace)
            register_entity(
                workspace,
                "ORGANIZATION",
                "Acme Neuro",
                entity_id="ENT-ACME-1",
                actor="tester",
            )
            register_entity(
                workspace,
                "ORGANIZATION",
                "Beta Acquired",
                entity_id="ENT-ACME-2",
                actor="tester",
            )
            proposal = propose_resolution(workspace, raw_mention="Acme Neuro", actor="tester")
            self.assertIn("ENT-ACME-1", proposal.get("candidate_entity_ids", []))
            with self.assertRaises(ValueError):
                record_resolution_disposition(
                    workspace,
                    proposal["proposal_id"],
                    "SUCCESSOR_OF",
                    rationale="Missing related entity.",
                    selected_entity_id="ENT-ACME-1",
                    actor="tester",
                )
            disposition = record_resolution_disposition(
                workspace,
                proposal["proposal_id"],
                "ACQUIRED_BY",
                rationale="Acquisition recorded; predecessor retained.",
                selected_entity_id="ENT-ACME-1",
                related_entity_id="ENT-ACME-2",
                actor="tester",
            )
            self.assertEqual(disposition["identity_relation"], "ACQUIRED_BY")
            self.assertEqual(disposition["related_entity_id"], "ENT-ACME-2")
            self.assertFalse(disposition["registry_mutation_performed"])
            self.assertFalse(disposition["fuzzy_auto_merge_performed"])
            with self.assertRaises(Exception):
                refuse_fuzzy_merge(workspace, reason="Names look similar; auto-merge forbidden")

    def test_not_same_and_unresolved_no_registry_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            initialize_registry(workspace)
            proposal = propose_resolution(workspace, raw_mention="Unique Mentions Corp", actor="tester")
            disposition = record_resolution_disposition(
                workspace,
                proposal["proposal_id"],
                "NOT_SAME_ENTITY",
                rationale="Distinct organizations.",
                actor="tester",
            )
            self.assertEqual(disposition["identity_relation"], "NOT_SAME_ENTITY")
            self.assertFalse(disposition["registry_mutation_performed"])

    def test_batch_collision_report_no_auto_merge(self) -> None:
        report = report_batch_collisions(
            [
                {"proposal_id": "RES-a", "candidate_entity_ids": ["ENT-1", "ENT-2"]},
                {"proposal_id": "RES-b", "candidate_entity_ids": ["ENT-1"]},
            ]
        )
        self.assertEqual(report["collision_count"], 1)
        self.assertFalse(report["fuzzy_auto_merge_performed"])


class GraphIntegrityAdversarialTests(unittest.TestCase):
    def test_dangling_duplicate_and_temporal_errors(self) -> None:
        entity = build_entity(entity_id="ENT-G-1", entity_type="ORGANIZATION", canonical_label="Org")
        source = build_source(
            source_id="SRC-G-1",
            source_class="REGISTRY",
            title="Source",
            publisher="Pub",
            canonical_url_or_reference="https://example.test/s",
        )
        observation = build_observation(
            observation_id="OBS-G-1",
            source_id="SRC-MISSING",
            observed_at=_date(),
            retrieval_method="HTTPS_GET",
            retrieval_outcome="RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            requested_locator="https://example.test/s",
            content_sha256="a" * 64,
        )
        assertion = build_assertion(
            assertion_id="ASR-G-1",
            subject={"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": "ENT-G-1", "boundary": GRAPH_BOUNDARY},
            predicate="listed_in",
            value="SRC-G-1",
            source_ids=["SRC-G-1"],
            observation_ids=["OBS-G-1"],
            evidence_state="OBSERVED",
            verification_state="UNVERIFIED",
            review_state="NOT_REVIEWED",
            claim_boundary="claim",
            prohibited_inferences=[],
            valid_from=_date("2026-12-01"),
            valid_until=_date("2026-01-01"),
        )
        errors = validate_temporal_integrity([entity, source, observation, assertion, entity])
        self.assertTrue(any("dangling" in item for item in errors))
        self.assertTrue(any("Duplicate id" in item for item in errors))
        self.assertTrue(any("valid_until definitely precedes valid_from" in item for item in errors))

    def test_idempotent_apply_and_predecessor_mismatch(self) -> None:
        predecessor = {"entities": [{"entity_id": "ENT-1", "label": "A"}], "metadata": {}}
        successor = {"entities": [{"entity_id": "ENT-1", "label": "A"}], "metadata": {}}
        _apply_operation(
            successor,
            {
                "operation_type": "ADD_ENTITY",
                "target_section": "entities",
                "record_id_field": "entity_id",
                "record_id": "ENT-2",
                "record": {"entity_id": "ENT-2", "label": "B"},
            },
            predecessor,
        )
        with self.assertRaises(DeltaApplyError):
            _apply_operation(
                successor,
                {
                    "operation_type": "ADD_ENTITY",
                    "target_section": "entities",
                    "record_id_field": "entity_id",
                    "record_id": "ENT-2",
                    "record": {"entity_id": "ENT-2", "label": "B"},
                },
                predecessor,
            )
        with self.assertRaises(DeltaApplyError):
            _apply_operation(
                successor,
                {
                    "operation_type": "RECORD_NO_CHANGE_COMPARISON",
                    "target_section": "no_change_comparisons",
                    "source_id": "SRC-1",
                    "comparison_scope": "   ",
                    "comparison_result": "NO_CHANGE",
                    "rationale": "scope missing",
                },
                predecessor,
            )
        compiled = compile_temporal_graph(
            [
                build_entity(entity_id="ENT-D-1", entity_type="ORGANIZATION", canonical_label="A"),
                build_entity(entity_id="ENT-D-2", entity_type="ORGANIZATION", canonical_label="B"),
            ]
        )
        diff = predecessor_successor_diff(compiled["objects"][:1], compiled["objects"])
        self.assertEqual(diff["added_ids"], ["ENT-D-2"])


if __name__ == "__main__":
    unittest.main()