from __future__ import annotations
import copy
import unittest
from neuroai_workbench.discovery import project_openfda_hde_pages


def page(rows,total=None,skip=0,limit=1000):return {"meta":{"results":{"total":len(rows) if total is None else total,"skip":skip,"limit":limit}},"results":rows}
def rec(h="H123456",supp=None,decision="APPR",trade="HUD Neural System"):
    return {"pma_number":h,"supplement_number":supp,"decision_code":decision,"trade_name":trade,"generic_name":"Neural interface","applicant":"HUD Applicant","decision_date":"20260801","product_code":"XYZ","street_1":"EXCLUDED ADDRESS","zip":"00000","openfda":{"device_name":"ANNOTATION"}}

class OpenFdaHdeProjectionTests(unittest.TestCase):
    def test_exact_hde_identity_and_appr_semantics(self):
        r=project_openfda_hde_pages(query_id="Q",search="pma_number:H*",pages=[page([rec()])]);n=r["normalized_records"][0]
        self.assertEqual(n["record_identity"],"HDE:H123456:ORIGINAL");self.assertEqual(n["decision_semantics"],"HDE_APPROVAL_RECORDED");self.assertTrue(n["decision_supports_hde_approval"]);self.assertFalse(n["decision_supports_reasonable_assurance_of_effectiveness"]);self.assertFalse(n["decision_establishes_facility_irb_approval"])
        self.assertNotIn("street_1",n);self.assertNotIn("zip",n);self.assertNotIn("openfda",n)
    def test_original_and_supplement_are_distinct(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(),rec(supp="S001")])]);self.assertEqual({n["record_identity"] for n in r["normalized_records"]},{"HDE:H123456:ORIGINAL","HDE:H123456:S001"})
    def test_non_h_records_are_out_of_scope_not_candidates(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(h="P123456"),rec(h="H123456")])]);self.assertEqual(r["coverage"]["out_of_scope_non_h_prefix_count"],1);self.assertEqual(len(r["result_records"]),1)
    def test_unknown_decision_code_never_guesses_approval(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(decision="XXXX")])]);n=r["normalized_records"][0];self.assertEqual(n["decision_semantics"],"UNRESOLVED_DECISION_CODE");self.assertFalse(n["decision_supports_hde_approval"])
    def test_exact_composite_duplicate_recognition(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(),rec(supp="S001")])],known_record_sources={"HDE:H123456:S001":"SRC-KNOWN"});self.assertEqual(r["coverage"]["known_controlled_duplicate_count"],1);d=next(x for x in r["result_records"] if x["classification_hint"]=="DUPLICATE");self.assertEqual(d["record_key"],"HDE:H123456:S001")
    def test_same_hde_different_supplement_never_duplicates_by_lineage(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(),rec(supp="S001")])],known_record_sources={"HDE:H123456:ORIGINAL":"SRC-ORIGINAL"});self.assertEqual(r["coverage"]["known_controlled_duplicate_count"],1);self.assertEqual(r["coverage"]["new_candidate_count"],1)
    def test_conflicting_same_composite_identity_fails_closed(self):
        a=rec();b=copy.deepcopy(a);b["trade_name"]="Different"
        with self.assertRaisesRegex(ValueError,"Conflicting normalized HDE"):
            project_openfda_hde_pages(query_id="Q",search="x",pages=[page([a,b])])
    def test_query_membership_does_not_change_content_digest(self):
        a=project_openfda_hde_pages(query_id="Q1",search="x",pages=[page([rec()])])["normalized_records"][0];b=project_openfda_hde_pages(query_id="Q2",search="y",pages=[page([rec()])])["normalized_records"][0];self.assertEqual(a["normalized_record_sha256"],b["normalized_record_sha256"])
    def test_over_limit_refuses_candidates(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec()],total=26001)]);self.assertTrue(r["coverage"]["over_26000_limit"]);self.assertTrue(r["coverage"]["search_after_or_partition_required"]);self.assertEqual(r["result_records"],[])
    def test_skip_gap_blocks_mechanical_match(self):
        r=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec(h="H1")],total=2,skip=0,limit=1),page([rec(h="H2")],total=2,skip=2,limit=1)]);self.assertFalse(r["coverage"]["skip_sequence_valid"]);self.assertEqual(r["coverage"]["skip_coverage_state"],"INVALID_SEQUENCE")
    def test_no_authority_escalation_flags(self):
        c=project_openfda_hde_pages(query_id="Q",search="x",pages=[page([rec()])])["coverage"]
        for k in ("record_presence_is_hde_approval_claim","hde_approval_is_reasonable_assurance_effectiveness_claim","hde_approval_establishes_facility_irb_approval","automatic_device_or_system_entity_creation_performed","automatic_applicant_entity_creation_performed","automatic_original_supplement_lineage_relationship_creation_performed","automatic_effectiveness_claim_creation_performed","automatic_facility_irb_authorization_claim_creation_performed","automatic_global_authorization_claim_creation_performed","automatic_system_conformance_claim_creation_performed","automatic_reopening_decision_performed","automatic_assessment_mutation_performed"):self.assertFalse(c[k])

if __name__=="__main__":unittest.main()
