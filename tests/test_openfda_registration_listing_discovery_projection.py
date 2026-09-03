from __future__ import annotations

import unittest

from neuroai_workbench.discovery import project_openfda_registration_listing_pages

QUERY = "DISCOVERY-OPENFDA-REGLIST-BCI-001"
SEARCH = 'proprietary_name:"neural+interface"'


def _product(owner="9051149", code="HQY", name="Neural interface device"):
    return {
        "created_date": "2026-01-15",
        "exempt": "N",
        "owner_operator_number": owner,
        "product_code": code,
        "openfda": {
            "device_class": "2",
            "device_name": name,
            "regulation_number": "882.1320",
        },
    }


def _row(*, names=None, products=None, registration_number="9610240"):
    return {
        "establishment_type": ["Manufacture Medical Device"],
        "k_number": "K123456",
        "pma_number": "",
        "products": products if products is not None else [_product()],
        "proprietary_name": names if names is not None else ["Neuro Alpha", "Neuro Beta"],
        "registration": {
            "registration_number": registration_number,
            "fei_number": "3002808212",
            "name": "Example Device Establishment",
            "status_code": "1",
            "reg_expiry_date_year": "2026",
            "address_line_1": "EXCLUDED ADDRESS",
            "city": "EXCLUDED CITY",
            "owner_operator": {
                "owner_operator_number": "9051149",
                "contact_address": {"address_1": "EXCLUDED CONTACT"},
                "official_correspondent": {"phone": "EXCLUDED PHONE"},
            },
            "us_agent": {"bus_phone_num": "EXCLUDED AGENT PHONE"},
        },
    }


def _page(rows, *, total=None, skip=0, limit=1000):
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


class OpenFdaRegistrationListingProjectionTests(unittest.TestCase):
    def test_provider_row_expands_products_without_changing_provider_denominator(self):
        row = _row(products=[_product(code="AAA"), _product(code="BBB")])
        result = project_openfda_registration_listing_pages(
            query_id=QUERY, search=SEARCH, pages=[_page([row], total=1)]
        )
        coverage = result["coverage"]
        self.assertEqual(coverage["returned_provider_record_count"], 1)
        self.assertEqual(coverage["expanded_representation_count"], 2)
        self.assertEqual(coverage["unique_representation_count"], 2)
        self.assertEqual(coverage["skip_coverage_state"], "MATCH")
        self.assertEqual(len(result["result_records"]), 2)

    def test_exact_representation_identity_uses_required_fields_and_name_set(self):
        result = project_openfda_registration_listing_pages(query_id=QUERY, search=SEARCH, pages=[_page([_row()])])
        row = result["normalized_records"][0]
        self.assertTrue(row["representation_identity"].startswith("REGLIST:9610240:9051149:HQY:"))
        self.assertEqual(row["registration_number"], "9610240")
        self.assertEqual(row["owner_operator_number"], "9051149")
        self.assertEqual(row["product_code"], "HQY")
        self.assertEqual(row["k_number"], "K123456")
        self.assertIsNone(row["pma_number"])

    def test_proprietary_name_order_does_not_change_identity_or_digest(self):
        a = project_openfda_registration_listing_pages(
            query_id="Q1",
            search=SEARCH,
            pages=[_page([_row(names=["Neuro Beta", "Neuro Alpha"])])],
        )["normalized_records"][0]
        b = project_openfda_registration_listing_pages(
            query_id="Q2",
            search=SEARCH,
            pages=[_page([_row(names=["Neuro Alpha", "Neuro Beta"])])],
        )["normalized_records"][0]
        self.assertEqual(a["representation_identity"], b["representation_identity"])
        self.assertEqual(a["normalized_record_sha256"], b["normalized_record_sha256"])

    def test_changed_proprietary_name_set_changes_representation_identity(self):
        a = project_openfda_registration_listing_pages(
            query_id=QUERY, search=SEARCH, pages=[_page([_row(names=["Neuro Alpha"])])]
        )["normalized_records"][0]
        b = project_openfda_registration_listing_pages(
            query_id=QUERY, search=SEARCH, pages=[_page([_row(names=["Neuro Alpha", "Neuro Beta"])])]
        )["normalized_records"][0]
        self.assertNotEqual(a["representation_identity"], b["representation_identity"])

    def test_missing_registration_number_is_unresolved_and_not_emitted(self):
        result = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row(registration_number="")])],
        )
        self.assertEqual(result["coverage"]["unresolved_registration_number_count"], 1)
        self.assertEqual(result["result_records"], [])

    def test_missing_product_owner_operator_is_unresolved_and_not_backfilled(self):
        result = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row(products=[_product(owner="")])])],
        )
        self.assertEqual(result["coverage"]["unresolved_owner_operator_number_count"], 1)
        self.assertEqual(result["result_records"], [])

    def test_missing_product_code_is_unresolved(self):
        result = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row(products=[_product(code="")])])],
        )
        self.assertEqual(result["coverage"]["unresolved_product_code_count"], 1)
        self.assertEqual(result["result_records"], [])

    def test_exact_known_representation_identity_is_only_duplicate_key(self):
        first = project_openfda_registration_listing_pages(query_id=QUERY, search=SEARCH, pages=[_page([_row()])])
        identity = first["normalized_records"][0]["representation_identity"]
        exact = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row()])],
            known_representation_sources={identity: "SRC-EXACT"},
        )
        self.assertEqual(exact["result_records"][0]["classification_hint"], "DUPLICATE")
        self.assertEqual(exact["result_records"][0]["duplicate_of_source_id"], "SRC-EXACT")
        nonexact = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row()])],
            known_representation_sources={"9610240": "SRC-WRONG"},
        )
        self.assertEqual(nonexact["result_records"][0]["classification_hint"], "NEW")

    def test_conflicting_same_representation_fails_closed(self):
        a = _row()
        b = _row()
        b["registration"]["status_code"] = "5"
        with self.assertRaisesRegex(ValueError, "Conflicting normalized registration/listing"):
            project_openfda_registration_listing_pages(
                query_id=QUERY,
                search=SEARCH,
                pages=[_page([a, b], total=2)],
            )

    def test_over_limit_refuses_candidate_emission(self):
        result = project_openfda_registration_listing_pages(
            query_id=QUERY,
            search=SEARCH,
            pages=[_page([_row()], total=26001)],
        )
        self.assertTrue(result["coverage"]["over_26000_limit"])
        self.assertTrue(result["coverage"]["bulk_download_or_partition_required"])
        self.assertEqual(result["result_records"], [])

    def test_skip_gap_is_detected(self):
        first = _page([_row(products=[_product(code="AAA")])], total=2, skip=0, limit=1)
        second = _page([_row(products=[_product(code="BBB")])], total=2, skip=2, limit=1)
        result = project_openfda_registration_listing_pages(query_id=QUERY, search=SEARCH, pages=[first, second])
        self.assertFalse(result["coverage"]["skip_sequence_valid"])
        self.assertEqual(result["coverage"]["skip_coverage_state"], "INVALID_SEQUENCE")

    def test_sensitive_registration_contact_fields_are_not_projected(self):
        result = project_openfda_registration_listing_pages(query_id=QUERY, search=SEARCH, pages=[_page([_row()])])
        serialized = str(result["normalized_records"])
        self.assertNotIn("EXCLUDED ADDRESS", serialized)
        self.assertNotIn("EXCLUDED CONTACT", serialized)
        self.assertNotIn("EXCLUDED PHONE", serialized)
        self.assertNotIn("EXCLUDED AGENT PHONE", serialized)

    def test_no_authority_escalation(self):
        coverage = project_openfda_registration_listing_pages(query_id=QUERY, search=SEARCH, pages=[_page([_row()])])[
            "coverage"
        ]
        self.assertFalse(coverage["representation_identity_is_exact_device_identity"])
        for key in (
            "registration_or_listing_is_marketing_authorization_claim",
            "registration_or_listing_is_clearance_or_approval_claim",
            "k_or_pma_reference_is_exact_configuration_authorization_claim",
            "product_code_is_exact_device_identity_claim",
            "automatic_establishment_entity_creation_performed",
            "automatic_owner_operator_entity_creation_performed",
            "automatic_device_or_system_entity_creation_performed",
            "automatic_registration_relationship_creation_performed",
            "automatic_premarket_authorization_relationship_creation_performed",
            "automatic_marketing_authorization_claim_creation_performed",
            "automatic_clearance_or_approval_claim_creation_performed",
            "automatic_current_commercial_availability_claim_creation_performed",
            "automatic_system_conformance_claim_creation_performed",
            "automatic_reopening_decision_performed",
            "automatic_assessment_mutation_performed",
        ):
            self.assertFalse(coverage[key])


if __name__ == "__main__":
    unittest.main()
