from __future__ import annotations

import copy
import unittest

from neuroai_workbench.discovery import project_openfda_device_event_pages


def _record(key: str = "12345", **overrides: object) -> dict:
    row = {
        "mdr_report_key": key,
        "report_number": "RPT-1",
        "date_received": "20260801",
        "report_date": "20260731",
        "event_type": "Malfunction",
        "product_problems": ["Device problem"],
        "source_type": ["Manufacturer report"],
        "remedial_action": ["Other"],
        "removal_correction_number": None,
        "device": [{
            "brand_name": "Fixture Device",
            "generic_name": "neural interface",
            "udi_di": "UDI-FIXTURE",
            "device_report_product_code": "FIX",
            "model_number": "M1",
            "manufacturer_d_name": "Fixture Manufacturer",
            "implant_flag": "Y",
            "serial_number": "MUST-NOT-PROJECT",
        }],
        "patient": [{"patient_age": "PRIVATE-MUST-NOT-PROJECT"}],
        "mdr_text": [{"text": "Narrative MUST NOT be projected"}],
    }
    row.update(overrides)
    return row


def _page(records: list[dict], *, total: int | None = None, skip: int = 0, limit: int = 1000) -> dict:
    return {
        "meta": {"results": {"total": len(records) if total is None else total, "skip": skip, "limit": limit}},
        "results": records,
    }


class OpenFdaDeviceEventProjectionTests(unittest.TestCase):
    def test_exact_mdr_identity_and_minimized_metadata_projection(self) -> None:
        result = project_openfda_device_event_pages(
            query_id="Q1",
            search='device.generic_name:"neural+interface"',
            pages=[_page([_record()])],
        )
        self.assertEqual(result["coverage"]["unique_mdr_report_key_count"], 1)
        self.assertEqual(result["coverage"]["skip_coverage_state"], "MATCH")
        normalized = result["normalized_records"][0]
        self.assertEqual(normalized["mdr_report_key"], "12345")
        self.assertEqual(normalized["devices"][0]["generic_name"], "neural interface")
        self.assertNotIn("patient", normalized)
        self.assertNotIn("mdr_text", normalized)
        self.assertNotIn("serial_number", normalized["devices"][0])
        self.assertFalse(normalized["patient_level_fields_included"])
        self.assertFalse(normalized["mdr_text_narrative_included"])
        self.assertFalse(result["coverage"]["causality_claim"])
        self.assertFalse(result["coverage"]["incidence_or_rate_claim"])
        self.assertFalse(result["coverage"]["comparative_safety_claim"])

    def test_exact_known_mdr_duplicate_recognition(self) -> None:
        result = project_openfda_device_event_pages(
            query_id="Q1",
            search="fixture",
            pages=[_page([_record("777")])],
            known_mdr_sources={"777": "SRC-MAUDE-777"},
        )
        self.assertEqual(result["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(result["result_records"][0]["duplicate_of_source_id"], "SRC-MAUDE-777")
        self.assertEqual(result["coverage"]["known_controlled_duplicate_count"], 1)

    def test_query_membership_does_not_change_content_digest(self) -> None:
        row = _record("888")
        a = project_openfda_device_event_pages(query_id="A", search="a", pages=[_page([row])])
        b = project_openfda_device_event_pages(query_id="B", search="b", pages=[_page([row])])
        self.assertEqual(
            a["normalized_records"][0]["normalized_record_sha256"],
            b["normalized_records"][0]["normalized_record_sha256"],
        )

    def test_same_mdr_conflicting_state_fails_closed(self) -> None:
        first = _record("999")
        second = copy.deepcopy(first)
        second["event_type"] = "Death"
        with self.assertRaisesRegex(ValueError, "Conflicting normalized openFDA representations"):
            project_openfda_device_event_pages(
                query_id="Q1",
                search="fixture",
                pages=[_page([first, second], total=2)],
            )

    def test_over_26000_refuses_candidate_emission(self) -> None:
        result = project_openfda_device_event_pages(
            query_id="Q1",
            search="fixture",
            pages=[_page([_record()], total=26001)],
        )
        self.assertTrue(result["coverage"]["over_26000_limit"])
        self.assertTrue(result["coverage"]["search_after_or_partition_required"])
        self.assertTrue(result["coverage"]["candidate_emission_refused_due_to_over_limit"])
        self.assertEqual(result["result_records"], [])
        self.assertEqual(result["normalized_records"], [])

    def test_noncontiguous_skip_sequence_is_detected(self) -> None:
        pages = [
            _page([_record("1")], total=2, skip=0, limit=1),
            _page([_record("2")], total=2, skip=2, limit=1),
        ]
        result = project_openfda_device_event_pages(query_id="Q1", search="fixture", pages=pages)
        self.assertFalse(result["coverage"]["skip_sequence_valid"])
        self.assertEqual(result["coverage"]["skip_coverage_state"], "INVALID_SEQUENCE")

    def test_report_key_not_brand_or_manufacturer_is_identity(self) -> None:
        rows = [
            _record("100", report_number="A"),
            _record("101", report_number="B"),
        ]
        result = project_openfda_device_event_pages(query_id="Q1", search="fixture", pages=[_page(rows)])
        self.assertEqual(result["coverage"]["unique_mdr_report_key_count"], 2)
        self.assertEqual(len(result["result_records"]), 2)
        self.assertFalse(result["coverage"]["automatic_system_or_device_entity_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_manufacturer_entity_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_safety_signal_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_regulatory_action_creation_performed"])
        self.assertFalse(result["coverage"]["automatic_assessment_mutation_performed"])

    def test_invalid_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mdr_report_key"):
            project_openfda_device_event_pages(query_id="Q1", search="fixture", pages=[_page([_record("")])])


if __name__ == "__main__":
    unittest.main()
