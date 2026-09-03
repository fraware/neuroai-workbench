from __future__ import annotations

import unittest

from neuroai_workbench.discovery import project_openfda_pma_pages


def page(total=1, skip=0, limit=1000, rows=None):
    return {"meta": {"results": {"total": total, "skip": skip, "limit": limit}}, "results": rows or []}


def row(pma="P123456", supp=None, code="APPR", **extra):
    r = {
        "pma_number": pma,
        "supplement_number": supp,
        "trade_name": "Neural Device",
        "generic_name": "Neurostimulator",
        "applicant": "Example Applicant",
        "decision_code": code,
        "decision_date": "20260901",
        "date_received": "20260801",
        "product_code": "NHL",
        "supplement_type": "Panel Track",
        "supplement_reason": "Design change",
        "ao_statement": "Bounded approval-order statement",
        "expedited_review_flag": "N",
        "street_1": "must disappear",
        "zip": "must disappear",
    }
    r.update(extra)
    return r


class OpenFdaPmaProjectionTests(unittest.TestCase):
    def test_original_identity_and_appr_semantics(self):
        out = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(rows=[row()])])
        n = out["normalized_records"][0]
        self.assertEqual(n["record_identity"], "PMA:P123456:ORIGINAL")
        self.assertEqual(n["record_role"], "ORIGINAL_APPLICATION")
        self.assertEqual(n["decision_semantics"], "APPROVAL_RECORDED")
        self.assertTrue(n["decision_supports_approval"])
        self.assertNotIn("street_1", n)
        self.assertNotIn("zip", n)

    def test_original_and_supplement_are_distinct(self):
        out = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(total=2, rows=[row(), row(supp="S001")])])
        ids = {n["record_identity"] for n in out["normalized_records"]}
        self.assertEqual(ids, {"PMA:P123456:ORIGINAL", "PMA:P123456:S001"})

    def test_all_exact_decision_states(self):
        mapping = {
            "APPR": "APPROVAL_RECORDED",
            "WTDR": "WITHDRAWAL_RECORDED",
            "DENY": "DENIAL_RECORDED",
            "LE30": "THIRTY_DAY_NOTICE_ACCEPTANCE_RECORDED",
            "APRL": "RECLASSIFICATION_AFTER_APPROVAL_RECORDED",
            "APWD": "WITHDRAWAL_AFTER_APPROVAL_RECORDED",
            "GT30": "NO_DECISION_WITHIN_30_DAYS_RECORDED",
            "APCV": "CONVERSION_AFTER_APPROVAL_RECORDED",
        }
        for code, state in mapping.items():
            n = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(rows=[row(code=code)])])[
                "normalized_records"
            ][0]
            self.assertEqual(n["decision_semantics"], state)
            self.assertEqual(n["decision_supports_approval"], code == "APPR")

    def test_unknown_decision_unresolved(self):
        n = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(rows=[row(code="XXXX")])])[
            "normalized_records"
        ][0]
        self.assertEqual(n["decision_semantics"], "UNRESOLVED_DECISION_CODE")
        self.assertFalse(n["decision_supports_approval"])

    def test_hde_and_legacy_nda_are_out_of_scope(self):
        out = project_openfda_pma_pages(
            query_id="Q", search="x", pages=[page(total=2, rows=[row(pma="H123456"), row(pma="N123456")])]
        )
        self.assertEqual(out["coverage"]["out_of_scope_hde_count"], 1)
        self.assertEqual(out["coverage"]["out_of_scope_legacy_nda_count"], 1)
        self.assertEqual(out["result_records"], [])

    def test_known_duplicate_requires_exact_composite_identity(self):
        out = project_openfda_pma_pages(
            query_id="Q",
            search="x",
            pages=[page(rows=[row(supp="S001")])],
            known_record_sources={"PMA:P123456:S001": "SRC-PMA-S1", "PMA:P123456:ORIGINAL": "SRC-PMA-ORIG"},
        )
        self.assertEqual(out["result_records"][0]["duplicate_of_source_id"], "SRC-PMA-S1")

    def test_same_pma_different_supplement_not_duplicate(self):
        out = project_openfda_pma_pages(
            query_id="Q",
            search="x",
            pages=[page(rows=[row(supp="S002")])],
            known_record_sources={"PMA:P123456:S001": "SRC-PMA-S1"},
        )
        self.assertEqual(out["result_records"][0]["classification_hint"], "NEW")

    def test_query_independent_digest(self):
        a = project_openfda_pma_pages(query_id="A", search="a", pages=[page(rows=[row()])])["normalized_records"][0][
            "normalized_record_sha256"
        ]
        b = project_openfda_pma_pages(query_id="B", search="b", pages=[page(rows=[row()])])["normalized_records"][0][
            "normalized_record_sha256"
        ]
        self.assertEqual(a, b)

    def test_conflicting_same_composite_identity_fails(self):
        with self.assertRaisesRegex(ValueError, "Conflicting normalized PMA"):
            project_openfda_pma_pages(
                query_id="Q",
                search="x",
                pages=[page(total=2, rows=[row(supp="S001"), row(supp="S001", supplement_reason="Different")])],
            )

    def test_over_limit_refuses_candidates(self):
        out = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(total=26001, rows=[row()])])
        self.assertTrue(out["coverage"]["search_after_or_partition_required"])
        self.assertEqual(out["result_records"], [])

    def test_invalid_skip_sequence(self):
        out = project_openfda_pma_pages(
            query_id="Q",
            search="x",
            pages=[
                page(total=2, skip=0, limit=1, rows=[row(pma="P1")]),
                page(total=2, skip=2, limit=1, rows=[row(pma="P2")]),
            ],
        )
        self.assertFalse(out["coverage"]["skip_sequence_valid"])

    def test_no_authority_escalation(self):
        c = project_openfda_pma_pages(query_id="Q", search="x", pages=[page(rows=[row()])])["coverage"]
        self.assertFalse(c["record_presence_is_approval_claim"])
        self.assertFalse(c["automatic_current_commercial_configuration_claim_creation_performed"])
        self.assertFalse(c["automatic_global_authorization_claim_creation_performed"])
        self.assertFalse(c["automatic_system_conformance_claim_creation_performed"])
        self.assertFalse(c["automatic_reopening_decision_performed"])


if __name__ == "__main__":
    unittest.main()
