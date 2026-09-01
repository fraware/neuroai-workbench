from __future__ import annotations
import copy, unittest
from neuroai_workbench.discovery import project_openfda_device_recall_pages

def page(total=1, skip=0, limit=1000, rows=None):
    return {"meta":{"results":{"total":total,"skip":skip,"limit":limit}},"results":rows or []}

def recall(cfres="R1", **extra):
    row={"cfres_id":cfres,"res_event_number":"E100","product_res_number":"P100","recall_status":"Ongoing","recalling_firm":"Example Firm","reason_for_recall":"Example bounded reason","product_description":"Deep brain stimulator","product_code":"NHL","k_numbers":["K123456"],"pma_numbers":["P123456"],"address_1":"PRIVATE ADDRESS","code_info":"LOT 123 SERIAL 456","distribution_pattern":"US nationwide"}
    row.update(extra); return row

class OpenFdaDeviceRecallProjectionTests(unittest.TestCase):
    def test_exact_identity_and_minimization(self):
        out=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(rows=[recall()])])
        n=out["normalized_records"][0]
        self.assertEqual(n["cfres_id"],"R1"); self.assertEqual(n["res_event_number"],"E100")
        self.assertNotIn("address_1",n); self.assertNotIn("code_info",n); self.assertNotIn("distribution_pattern",n)
        c=out["coverage"]
        self.assertFalse(c["address_or_contact_fields_projected"]); self.assertFalse(c["code_info_lot_serial_text_projected"]); self.assertFalse(c["distribution_pattern_projected"])

    def test_known_duplicate_by_exact_cfres_only(self):
        out=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(rows=[recall()])],known_cfres_sources={"R1":"SRC-R1"})
        self.assertEqual(out["result_records"][0]["classification_hint"],"DUPLICATE"); self.assertEqual(out["result_records"][0]["duplicate_of_source_id"],"SRC-R1")

    def test_same_event_number_does_not_merge_distinct_recall_records(self):
        out=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(total=2,rows=[recall("R1"),recall("R2")])])
        self.assertEqual(out["coverage"]["unique_cfres_id_count"],2)

    def test_query_independent_digest(self):
        a=project_openfda_device_recall_pages(query_id="A",search="x",pages=[page(rows=[recall()])])["normalized_records"][0]["normalized_record_sha256"]
        b=project_openfda_device_recall_pages(query_id="B",search="y",pages=[page(rows=[recall()])])["normalized_records"][0]["normalized_record_sha256"]
        self.assertEqual(a,b)

    def test_conflicting_same_cfres_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Conflicting normalized recall"):
            project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(total=2,rows=[recall(),recall(reason_for_recall="Changed")])])

    def test_over_limit_refuses_candidates(self):
        out=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(total=26001,rows=[recall()])])
        self.assertTrue(out["coverage"]["search_after_or_partition_required"]); self.assertEqual(out["result_records"],[])

    def test_invalid_skip_sequence_detected(self):
        out=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(total=2,skip=0,limit=1,rows=[recall("R1")]),page(total=2,skip=2,limit=1,rows=[recall("R2")])])
        self.assertFalse(out["coverage"]["skip_sequence_valid"]); self.assertEqual(out["coverage"]["skip_coverage_state"],"INVALID_SEQUENCE")

    def test_no_auto_nonconformance_or_reopening(self):
        c=project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(rows=[recall()])])["coverage"]
        self.assertFalse(c["recall_status_is_complete_lifecycle_tracker"]); self.assertFalse(c["automatic_system_nonconformance_claim_creation_performed"]); self.assertFalse(c["automatic_reopening_decision_performed"]); self.assertFalse(c["automatic_assessment_mutation_performed"])

    def test_empty_cfres_fails(self):
        with self.assertRaisesRegex(ValueError,"cfres_id"):
            project_openfda_device_recall_pages(query_id="Q",search="x",pages=[page(rows=[recall("")])])

if __name__ == "__main__": unittest.main()
