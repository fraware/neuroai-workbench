from __future__ import annotations
import copy,unittest
from neuroai_workbench.discovery import project_openfda_device_classification_pages
QUERY="DISCOVERY-OPENFDA-CLASS-DBS-NEUROSTIM-001";SEARCH="device_name:neurostimulator"
def _row(code="ABC",reg="882.9999",device_class="2"):
    return {"product_code":code,"device_name":"Neurostimulator","definition":"Electrical neural stimulation device","device_class":device_class,"regulation_number":reg,"medical_specialty":"NE","medical_specialty_description":"Neurology","review_code":"N","implant_flag":"Y","life_sustain_support_flag":"N","gmp_exempt_flag":"N","openfda":{"device_name":"SHOULD NOT DRIVE IDENTITY","k_number":["K123456"]}}
def _page(rows,total=None,skip=0,limit=1000):return {"meta":{"results":{"total":len(rows) if total is None else total,"skip":skip,"limit":limit}},"results":rows}
class DeviceClassificationProjectionTests(unittest.TestCase):
    def test_product_code_is_generic_category_identity(self):
        r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);n=r["normalized_records"][0];self.assertEqual(n["record_identity"],"OPENFDA_CLASS:ABC");self.assertFalse(n["product_code_is_exact_device_identity"]);self.assertNotIn("openfda",n)
    def test_regulation_number_present_is_regulation_referenced(self):self.assertEqual(project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])])["normalized_records"][0]["classification_finality"],"REGULATION_REFERENCED_CLASSIFICATION")
    def test_missing_regulation_number_is_proposed_not_final(self):
        r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row(reg=None)])]);n=r["normalized_records"][0];self.assertEqual(n["classification_finality"],"PROPOSED_CLASS_NOT_FINAL");self.assertEqual(r["coverage"]["proposed_not_final_classification_count"],1)
    def test_invalid_product_code_is_unresolved(self):
        r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row(code="AB12")])]);self.assertEqual(r["coverage"]["unresolved_product_code_count"],1);self.assertEqual(r["result_records"],[])
    def test_query_membership_does_not_change_digest(self):
        a=project_openfda_device_classification_pages(query_id="Q1",search=SEARCH,pages=[_page([_row()])])["normalized_records"][0];b=project_openfda_device_classification_pages(query_id="Q2",search=SEARCH,pages=[_page([_row()])])["normalized_records"][0];self.assertEqual(a["normalized_record_sha256"],b["normalized_record_sha256"])
    def test_exact_product_code_duplicate(self):
        r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])],known_product_code_sources={"OPENFDA_CLASS:ABC":"SRC-EXACT"});self.assertEqual(r["result_records"][0]["classification_hint"],"DUPLICATE");self.assertEqual(r["result_records"][0]["duplicate_of_source_id"],"SRC-EXACT")
    def test_conflicting_same_product_code_fails_closed(self):
        a=_row();b=copy.deepcopy(a);b["device_class"]="3"
        with self.assertRaisesRegex(ValueError,"Conflicting normalized classification"):project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([a,b],total=2)])
    def test_over_limit_refuses_candidates(self):
        r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()],total=26001)]);self.assertTrue(r["coverage"]["bulk_download_or_partition_required"]);self.assertEqual(r["result_records"],[])
    def test_skip_gap_detected(self):
        a=_page([_row("ABC")],total=2,skip=0,limit=1);b=_page([_row("XYZ")],total=2,skip=2,limit=1);r=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[a,b]);self.assertFalse(r["coverage"]["skip_sequence_valid"]);self.assertEqual(r["coverage"]["skip_coverage_state"],"INVALID_SEQUENCE")
    def test_no_authority_escalation(self):
        c=project_openfda_device_classification_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])])["coverage"]
        for k in ("product_code_is_exact_device_identity","classification_record_is_marketing_authorization","classification_record_is_clearance_or_approval","device_class_is_system_conformance","automatic_device_or_system_entity_creation_performed","automatic_product_code_relationship_creation_performed","automatic_regulation_relationship_creation_performed","automatic_reopening_decision_performed","automatic_assessment_mutation_performed"):self.assertFalse(c[k])
if __name__=="__main__":unittest.main()
