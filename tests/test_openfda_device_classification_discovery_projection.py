from __future__ import annotations

import copy
import unittest

from neuroai_workbench.discovery import project_openfda_device_classification_pages

QUERY = "DISCOVERY-OPENFDA-CLASS-BCI-001"
SEARCH = 'device_name:"neural+interface"'


def _record() -> dict:
    return {
        "product_code": "ABC",
        "device_name": "Neural interface device",
        "definition": "Generic neural interface category",
        "device_class": "2",
        "regulation_number": "882.9999",
        "medical_specialty": "NE",
        "medical_specialty_description": "Neurology",
        "review_code": "N",
        "implant_flag": "Y",
        "life_sustain_support_flag": "N",
        "gmp_exempt_flag": "N",
        "openfda": {
            "device_name": "HARMONIZED FIELD MUST NOT DEFINE IDENTITY",
            "k_number": ["K123456"],
            "pma_number": ["P123456"],
        },
    }


def _page(
    rows: list[dict],
    *,
    total: int | None = None,
    skip: int = 0,
    limit: int = 1000,
) -> dict:
    return {
        "meta": {
            "results": {
                "total": len(rows) if total is None else total,
                "skip": skip,
                "limit": limit,
            }
        },
        "results": rows,
    }


class DeviceClassificationProjectionTests(unittest.TestCase):
    def test_exact_product_code_is_category_identity_not_device_identity(self) -> None:
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_record()])],
        )
        row = result["normalized_records"][0]
        self.assertEqual(row["record_identity"], "ABC")
        self.assertEqual(row["product_code"], "ABC")
        self.assertFalse(result["coverage"]["product_code_is_exact_device_identity_claim"])
        self.assertNotIn("openfda", row)

    def test_regulation_number_present_is_regulation_referenced(self) -> None:
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_record()])],
        )
        row = result["normalized_records"][0]
        self.assertEqual(
            row["classification_finality"],
            "REGULATION_REFERENCED_CLASSIFICATION",
        )
        self.assertEqual(
            result["coverage"]["regulation_referenced_classification_count"],
            1,
        )
        self.assertEqual(
            result["coverage"]["proposed_not_final_classification_count"],
            0,
        )

    def test_missing_regulation_number_makes_listed_class_proposed_not_final(self) -> None:
        record = _record()
        record.pop("regulation_number")
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([record])],
        )
        row = result["normalized_records"][0]
        self.assertEqual(row["device_class"], "2")
        self.assertEqual(row["classification_finality"], "PROPOSED_CLASS_NOT_FINAL")
        self.assertEqual(
            result["coverage"]["proposed_not_final_classification_count"],
            1,
        )

    def test_query_membership_does_not_change_content_digest(self) -> None:
        left = project_openfda_device_classification_pages(
            query_id="Q-A",
            search=SEARCH,
            pages=[_page([_record()])],
        )["normalized_records"][0]
        right = project_openfda_device_classification_pages(
            query_id="Q-B",
            search=SEARCH,
            pages=[_page([_record()])],
        )["normalized_records"][0]
        self.assertEqual(
            left["normalized_record_sha256"],
            right["normalized_record_sha256"],
        )

    def test_exact_known_product_code_only_marks_duplicate(self) -> None:
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_record()])],
            known_product_code_sources={"ABC": "SRC-EXACT"},
        )
        self.assertEqual(result["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(
            result["result_records"][0]["duplicate_of_source_id"],
            "SRC-EXACT",
        )

    def test_same_product_code_conflicting_content_fails_closed(self) -> None:
        changed = _record()
        changed["device_name"] = "Different category description"
        with self.assertRaisesRegex(ValueError, "Conflicting normalized"):
            project_openfda_device_classification_pages(
                query_id=QUERY,
                search=SEARCH,
                pages=[_page([_record(), changed])],
            )

    def test_missing_product_code_stays_unresolved_and_emits_no_candidate(self) -> None:
        record = _record()
        record.pop("product_code")
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([record])],
        )
        self.assertEqual(result["coverage"]["unresolved_product_code_count"], 1)
        self.assertEqual(result["coverage"]["unique_product_code_count"], 0)
        self.assertEqual(result["result_records"], [])

    def test_malformed_product_codes_fail_closed_as_unresolved(self) -> None:
        for malformed in ("A12", "ABCD", "AB", "A-C"):
            with self.subTest(product_code=malformed):
                record = _record()
                record["product_code"] = malformed
                result = project_openfda_device_classification_pages(
                    query_id=QUERY,
                    search=SEARCH,
                    pages=[_page([record])],
                )
                self.assertEqual(result["coverage"]["unresolved_product_code_count"], 1)
                self.assertEqual(result["coverage"]["unique_product_code_count"], 0)
                self.assertEqual(result["result_records"], [])

    def test_lowercase_three_letter_product_code_is_normalized(self) -> None:
        record = _record()
        record["product_code"] = "abc"
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([record])],
        )
        self.assertEqual(result["normalized_records"][0]["product_code"], "ABC")

    def test_over_direct_result_bound_refuses_candidate_emission(self) -> None:
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_record()], total=26001)],
        )
        self.assertTrue(result["coverage"]["over_26000_limit"])
        self.assertTrue(result["coverage"]["bulk_download_or_partition_required"])
        self.assertEqual(result["result_records"], [])

    def test_skip_gap_is_not_mechanically_complete(self) -> None:
        first = _record()
        second = copy.deepcopy(_record())
        second["product_code"] = "XYZ"
        result = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[
                _page([first], total=2, skip=0, limit=1),
                _page([second], total=2, skip=2, limit=1),
            ],
        )
        self.assertFalse(result["coverage"]["skip_sequence_valid"])
        self.assertEqual(result["coverage"]["skip_coverage_state"], "INVALID_SEQUENCE")

    def test_no_authority_escalation(self) -> None:
        coverage = project_openfda_device_classification_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_record()])],
        )["coverage"]
        for key in (
            "product_code_is_exact_device_identity_claim",
            "classification_record_is_marketing_authorization_claim",
            "classification_record_is_clearance_or_approval_claim",
            "device_class_is_system_conformance_claim",
            "automatic_source_admission_performed",
            "automatic_device_or_system_entity_creation_performed",
            "automatic_product_code_relationship_creation_performed",
            "automatic_regulation_relationship_creation_performed",
            "automatic_marketing_authorization_claim_creation_performed",
            "automatic_clearance_or_approval_claim_creation_performed",
            "automatic_exact_device_identity_claim_creation_performed",
            "automatic_system_conformance_claim_creation_performed",
            "automatic_reopening_decision_performed",
            "automatic_assessment_mutation_performed",
        ):
            self.assertFalse(coverage[key], key)


if __name__ == "__main__":
    unittest.main()
