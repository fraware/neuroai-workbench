from __future__ import annotations
import unittest
from neuroai_workbench.discovery import project_openfda_udi_pages

QUERY="DISCOVERY-OPENFDA-UDI-BCI-001"
SEARCH='device_description:"neural+interface"'

def _row(di="00887517567062",agency="GS1",version="1",status="New"):
    return {
        "record_status":"Published","commercial_distribution_status":"In Commercial Distribution","device_description":"Neural interface test device",
        "identifiers":[{"issuing_agency":agency,"id":di,"type":"Primary"},{"issuing_agency":agency,"id":"SECONDARY-1","type":"Secondary"}],
        "version_or_model_number":"MODEL-1","brand_name":"Neuro Device","company_name":"Example Co","catalog_number":"CAT-1",
        "record_key":"RK-1","public_version_number":version,"public_version_date":"2026-08-31","public_version_status":status,"publish_date":"2026-01-01",
        "commercial_distribution_end_date":None,
        "premarket_submissions":[{"submission_number":"K123456","supplement_number":None,"submissions_type":"510(k)"}],
        "product_codes":[{"code":"ABC","name":"Example code","openfda":{"device_class":"2"}}],
        "customer_contacts":[{"phone":"555-0100","email":"person@example.com"}],"labeler_duns_number":"123456789"
    }

def _page(rows,total=None,skip=0,limit=1000):
    return {"meta":{"results":{"total":len(rows) if total is None else total,"skip":skip,"limit":limit}},"results":rows}

class OpenFdaUdiProjectionTests(unittest.TestCase):
    def test_exact_primary_di_identity_and_minimized_projection(self):
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);n=r["normalized_records"][0]
        self.assertEqual(n["record_identity"],"UDI:GS1:00887517567062");self.assertEqual(n["primary_di"],"00887517567062");self.assertEqual(n["primary_di_issuing_agency"],"GS1")
        self.assertEqual(n["record_key"],"RK-1");self.assertEqual(n["public_version_number"],"1");self.assertEqual(n["identifiers"][1]["type"],"Secondary")
        self.assertNotIn("customer_contacts",n);self.assertNotIn("labeler_duns_number",n)
        self.assertEqual(n["premarket_submissions"][0]["submission_number"],"K123456")
    def test_query_membership_does_not_change_digest(self):
        a=project_openfda_udi_pages(query_id="Q1",search=SEARCH,pages=[_page([_row()])])["normalized_records"][0]
        b=project_openfda_udi_pages(query_id="Q2",search=SEARCH,pages=[_page([_row()])])["normalized_records"][0]
        self.assertEqual(a["normalized_record_sha256"],b["normalized_record_sha256"])
    def test_no_primary_di_is_unresolved_and_not_emitted(self):
        row=_row();row["identifiers"]=[{"issuing_agency":"GS1","id":"X","type":"Secondary"}]
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([row])]);self.assertEqual(r["coverage"]["unresolved_primary_di_count"],1);self.assertEqual(r["result_records"],[])
    def test_multiple_primary_di_fails_candidate_identity(self):
        row=_row();row["identifiers"].append({"issuing_agency":"HIBCC","id":"OTHER","type":"Primary"})
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([row])]);self.assertEqual(r["coverage"]["multiple_primary_di_count"],1);self.assertEqual(r["result_records"],[])
    def test_exact_known_identity_duplicate(self):
        key="UDI:GS1:00887517567062";r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])],known_udi_sources={key:"SRC-EXISTING"})
        self.assertEqual(r["result_records"][0]["classification_hint"],"DUPLICATE");self.assertEqual(r["result_records"][0]["duplicate_of_source_id"],"SRC-EXISTING")
    def test_secondary_di_never_drives_duplicate_identity(self):
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])],known_udi_sources={"UDI:GS1:SECONDARY-1":"SRC-WRONG"})
        self.assertEqual(r["result_records"][0]["classification_hint"],"NEW")
    def test_conflicting_same_primary_di_state_refuses(self):
        a=_row();b=_row(version="2",status="Update")
        with self.assertRaisesRegex(ValueError,"Conflicting normalized UDI representations"):project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([a,b],total=2)])
    def test_over_limit_refuses_candidate_emission(self):
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()],total=26001)]);self.assertTrue(r["coverage"]["over_26000_limit"]);self.assertTrue(r["coverage"]["bulk_download_or_partition_required"]);self.assertEqual(r["result_records"],[])
    def test_skip_gap_detected(self):
        a=_page([_row("A")],total=2,skip=0,limit=1);b=_page([_row("B")],total=2,skip=2,limit=1)
        r=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[a,b]);self.assertFalse(r["coverage"]["skip_sequence_valid"]);self.assertEqual(r["coverage"]["skip_coverage_state"],"INVALID_SEQUENCE")
    def test_no_authority_escalation(self):
        c=project_openfda_udi_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])])["coverage"]
        for k in ("automatic_device_or_system_entity_creation_performed","automatic_company_entity_creation_performed","automatic_di_relationship_creation_performed","automatic_premarket_authorization_relationship_creation_performed","automatic_current_commercial_availability_claim_creation_performed","automatic_marketing_authorization_claim_creation_performed","automatic_effectiveness_claim_creation_performed","automatic_system_conformance_claim_creation_performed","automatic_reopening_decision_performed","automatic_assessment_mutation_performed"):self.assertFalse(c[k])

if __name__=="__main__":unittest.main()
