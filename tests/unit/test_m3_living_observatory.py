from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.api import PublicObservatoryApiError, load_authorized_release, refuse_write
from neuroai_workbench.monitoring_lifecycle import advance_onboarding, initial_onboarding_record
from neuroai_workbench.monitoring_service import MonitoringService
from neuroai_workbench.observatory_graph import build_entity
from neuroai_workbench.release import ReleaseCompiler
from neuroai_workbench.reopening_service import ReopeningService


class OnboardingLifecycleTests(unittest.TestCase):
    def test_source_acceptance_does_not_create_monitor(self) -> None:
        service = MonitoringService()
        record = service.open_onboarding(source_candidate_id="CAND-1", actor="tester")
        for stage, note in [
            ("REPLAY_PROJECTION", "replay"),
            ("CURRENT_SOURCE_IDENTITY_CHECK", "identity"),
            ("PENDING_HUMAN_ACCEPTANCE", "pending"),
            ("HUMAN_DISPOSITION_RECORDED", "accepted source"),
        ]:
            record = service.advance_onboarding(record, next_stage=stage, actor="tester", note=note)
        self.assertFalse(record["monitor_created"])
        self.assertFalse(record["live_monitor_authorized"])
        disappeared = service.record_disappearance(record, actor="tester", note="404")
        self.assertTrue(disappeared["historical_evidence_retained"])
        self.assertEqual(disappeared["stage"], "SOURCE_DISAPPEARED_HISTORY_RETAINED")

    def test_illegal_skip_to_monitor_registry_blocked(self) -> None:
        record = initial_onboarding_record(source_candidate_id="CAND-2", actor="tester")
        with self.assertRaises(ValueError):
            advance_onboarding(record, next_stage="DRAFT_MONITOR_REGISTRY_SUCCESSOR", actor="t", note="skip")


class TypedChangeClassificationTests(unittest.TestCase):
    def test_no_change_requires_explicit_scope(self) -> None:
        service = MonitoringService()
        typed = service.classify(
            {
                "classification": "NO_CHANGE",
                "candidate_required": False,
                "source_id": "SRC-1",
            },
            comparison_scope="bytes_digest",
        )
        self.assertTrue(typed["no_change_explicit"])
        self.assertEqual(typed["typed_change_class"], "NO_CHANGE")
        insufficient = service.classify(
            {"classification": "NO_CHANGE", "candidate_required": False},
            comparison_scope="  ",
        )
        self.assertEqual(insufficient["typed_change_class"], "COMPARISON_SCOPE_INSUFFICIENT")


class PublicV1ApiTests(unittest.TestCase):
    def test_compiler_candidate_is_not_public_release(self) -> None:
        entity = build_entity(entity_id="ENT-API-1", entity_type="ORGANIZATION", canonical_label="Org")
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "compiler-candidate"
            ReleaseCompiler().build([entity], output, candidate_id="CAND-API-1")
            with self.assertRaises(PublicObservatoryApiError):
                load_authorized_release(output)
            with self.assertRaises(PublicObservatoryApiError):
                refuse_write("POST")


class ReopeningServiceTests(unittest.TestCase):
    def test_analyze_never_mutates_assessment(self) -> None:
        service = ReopeningService()
        payload = {
            "operations": [],
            "metadata": {"delta_id": "DELTA-" + "a" * 32},
        }
        first = service.analyze(payload, manifests={})
        second = service.analyze(payload, manifests={})
        self.assertFalse(first["assessment_mutated"])
        self.assertTrue(first["empty_basis_no_reopening_is_not_nothing_changed"])
        self.assertTrue(first["executed_reopening_requires_ordinary_assessment_save"])
        self.assertEqual(
            [item["recommendation_id"] for item in first["recommendations"]],
            [item["recommendation_id"] for item in second["recommendations"]],
        )
