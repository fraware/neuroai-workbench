from __future__ import annotations
import unittest
from neuroai_workbench.discovery import project_openfda_510k_pages

def page(total=1,skip=0,limit=1000,rows=None):
    return {"meta":{"results":{"total":total,"skip":skip,"limit":limit}},"results":rows or []}

def row(k="K123456",code="SESE",**extra):
    r={"k_number":k,"device_name":"Neural interface device","applicant":"Example Applicant","decision_code":code,"decision_description":"Substantially Equivalent" if code=="SESE" else "Example","decision_date":"20260901","date_received":"20260801","clearance_type":"traditional","product_code":"NHL","address_1":"must disappear","contact":"must disappear"};r.update(extra);return r

class OpenFda510kProjectionTests(unittest.TestCase):
    def test_recognized_se_code_is_exactly_classified(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row()])])
        n=out["normalized_records"][0]
        self.assertEqual(n["k_number"],"K123456");self.assertEqual(n["decision_semantics"],"SUBSTANTIALLY_EQUIVALENT_RECORDED");self.assertTrue(n["decision_supports_substantial_equivalence"])
        self.assertNotIn("address_1",n);self.assertNotIn("contact",n)
    def test_all_documented_se_codes_recognized(self):
        for code in ("SEKD","SESD","SESE","SESK","SESP","SESU","SESR"):
            n=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row(code=code)])])["normalized_records"][0]
            self.assertTrue(n["decision_code_recognized"],code)
    def test_unknown_decision_code_remains_unresolved(self):
        n=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row(code="XXXX")])])["normalized_records"][0]
        self.assertEqual(n["decision_semantics"],"UNRESOLVED_DECISION_CODE");self.assertFalse(n["decision_supports_substantial_equivalence"])
    def test_den_is_out_of_scope_and_not_emitted(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row(k="DEN250013")])])
        self.assertEqual(out["coverage"]["out_of_scope_den_count"],1);self.assertEqual(out["result_records"],[]);self.assertEqual(out["normalized_records"],[])
    def test_unresolved_prefix_is_not_emitted(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row(k="P12345")])])
        self.assertEqual(out["coverage"]["unresolved_k_number_count"],1);self.assertEqual(out["result_records"],[])
    def test_known_duplicate_uses_exact_k_only(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row()])],known_k_sources={"K123456":"SRC-K"})
        self.assertEqual(out["result_records"][0]["classification_hint"],"DUPLICATE");self.assertEqual(out["result_records"][0]["duplicate_of_source_id"],"SRC-K")
    def test_query_independent_digest(self):
        a=project_openfda_510k_pages(query_id="A",search="a",pages=[page(rows=[row()])])["normalized_records"][0]["normalized_record_sha256"]
        b=project_openfda_510k_pages(query_id="B",search="b",pages=[page(rows=[row()])])["normalized_records"][0]["normalized_record_sha256"]
        self.assertEqual(a,b)
    def test_conflicting_same_k_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Conflicting normalized 510\(k\)"):
            project_openfda_510k_pages(query_id="Q",search="x",pages=[page(total=2,rows=[row(),row(device_name="Different")])])
    def test_over_limit_refuses_candidates(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(total=26001,rows=[row()])]);self.assertTrue(out["coverage"]["search_after_or_partition_required"]);self.assertEqual(out["result_records"],[])
    def test_invalid_skip_sequence_detected(self):
        out=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(total=2,skip=0,limit=1,rows=[row("K1")]),page(total=2,skip=2,limit=1,rows=[row("K2")])]);self.assertFalse(out["coverage"]["skip_sequence_valid"])
    def test_no_authority_escalation(self):
        c=project_openfda_510k_pages(query_id="Q",search="x",pages=[page(rows=[row()])])["coverage"]
        self.assertFalse(c["record_presence_is_clearance_claim"]);self.assertFalse(c["automatic_global_authorization_claim_creation_performed"]);self.assertFalse(c["automatic_system_conformance_claim_creation_performed"]);self.assertFalse(c["automatic_reopening_decision_performed"])
if __name__=="__main__":unittest.main()
