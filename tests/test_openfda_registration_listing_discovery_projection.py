from __future__ import annotations
import copy,unittest
from neuroai_workbench.discovery import project_openfda_registration_listing_pages

QUERY="DISCOVERY-OPENFDA-REGLIST-BCI-001";SEARCH='proprietary_name:"neural+interface"'
def _row():
    return {"establishment_type":["Manufacture Medical Device"],"k_number":"K123456","pma_number":"P123456","proprietary_name":["Neural Interface X","Neural Interface X"],
      "products":[{"created_date":"2026-01-01","exempt":"N","owner_operator_number":"9051149","product_code":"ABC","openfda":{"device_class":"2","device_name":"Neural interface device","regulation_number":"882.9999"}},
                  {"created_date":"2026-01-02","exempt":"N","owner_operator_number":"9051149","product_code":"XYZ","openfda":{"device_class":"3","device_name":"Implanted neural device","regulation_number":"882.9998"}}],
      "registration":{"registration_number":"9610240","fei_number":"3002808212","name":"Example Establishment","status_code":"1","reg_expiry_date_year":"2027",
        "address_line_1":"EXCLUDED ADDRESS","city":"EXCLUDED CITY","owner_operator":{"owner_operator_number":"9051149","contact_address":{"address1":"EXCLUDED OWNER ADDRESS"},"official_correspondent":{"email":"EXCLUDED CORRESPONDENT"}},"us_agent":{"email":"EXCLUDED AGENT"}}}
def _page(rows,total=None,skip=0,limit=1000):return {"meta":{"results":{"total":len(rows) if total is None else total,"skip":skip,"limit":limit}},"results":rows}

class RegistrationListingProjectionTests(unittest.TestCase):
    def test_one_provider_row_expands_to_two_product_representations(self):
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);self.assertEqual(r["coverage"]["returned_provider_record_count"],1);self.assertEqual(r["coverage"]["expanded_representation_count"],2);self.assertEqual(len(r["normalized_records"]),2);self.assertNotEqual(r["normalized_records"][0]["representation_identity"],r["normalized_records"][1]["representation_identity"])
    def test_representation_is_not_device_identity_and_pii_is_excluded(self):
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);text=str(r);n=r["normalized_records"][0]
        self.assertFalse(n["representation_is_exact_device_identity"]);self.assertFalse(n["registration_or_listing_establishes_authorization"])
        for secret in ("EXCLUDED ADDRESS","EXCLUDED CITY","EXCLUDED OWNER ADDRESS","EXCLUDED CORRESPONDENT","EXCLUDED AGENT"):self.assertNotIn(secret,text)
    def test_k_pma_and_product_code_are_metadata_not_authority(self):
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);n=r["normalized_records"][0];c=r["coverage"]
        self.assertEqual(n["k_number"],"K123456");self.assertEqual(n["pma_number"],"P123456");self.assertFalse(c["k_or_pma_reference_establishes_exact_configuration_authorization"]);self.assertFalse(c["product_code_establishes_exact_device_identity"])
    def test_query_membership_does_not_change_digest(self):
        a=project_openfda_registration_listing_pages(query_id="Q1",search=SEARCH,pages=[_page([_row()])])["normalized_records"]
        b=project_openfda_registration_listing_pages(query_id="Q2",search=SEARCH,pages=[_page([_row()])])["normalized_records"]
        self.assertEqual([x["normalized_record_sha256"] for x in a],[x["normalized_record_sha256"] for x in b])
    def test_exact_representation_duplicate_only(self):
        first=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])]);key=first["normalized_records"][0]["representation_identity"]
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])],known_representation_sources={key:"SRC-EXACT"});dups=[x for x in r["result_records"] if x["classification_hint"]=="DUPLICATE"];self.assertEqual(len(dups),1);self.assertEqual(dups[0]["duplicate_of_source_id"],"SRC-EXACT")
    def test_changed_proprietary_name_set_changes_representation_identity(self):
        a=_row();b=_row();b["proprietary_name"]=["Neural Interface X","Neural Interface Y"]
        ra=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([a])]);rb=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([b])]);self.assertNotEqual(ra["normalized_records"][0]["representation_identity"],rb["normalized_records"][0]["representation_identity"])
    def test_missing_required_identity_parts_are_unresolved(self):
        row=_row();row["registration"].pop("registration_number")
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([row])]);self.assertEqual(r["coverage"]["unresolved_registration_number_count"],2);self.assertEqual(r["result_records"],[])
    def test_conflicting_same_representation_fails_closed(self):
        a=_row();b=copy.deepcopy(a);b["registration"]["status_code"]="9"
        with self.assertRaisesRegex(ValueError,"Conflicting normalized registration/listing representations"):project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([a,b],total=2)])
    def test_over_limit_refuses_candidates(self):
        r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()],total=26001)]);self.assertTrue(r["coverage"]["over_26000_limit"]);self.assertEqual(r["result_records"],[])
    def test_skip_gap_detected(self):
        a=_page([_row()],total=2,skip=0,limit=1);b=_page([_row()],total=2,skip=2,limit=1);r=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[a,b]);self.assertFalse(r["coverage"]["skip_sequence_valid"]);self.assertEqual(r["coverage"]["skip_coverage_state"],"INVALID_SEQUENCE")
    def test_no_authority_escalation(self):
        c=project_openfda_registration_listing_pages(query_id=QUERY,search=SEARCH,pages=[_page([_row()])])["coverage"]
        for k in ("representation_is_exact_device_identity","registration_or_listing_is_marketing_authorization","registration_or_listing_is_clearance_or_approval","k_or_pma_reference_establishes_exact_configuration_authorization","product_code_establishes_exact_device_identity","automatic_establishment_entity_creation_performed","automatic_device_or_system_entity_creation_performed","automatic_registration_relationship_creation_performed","automatic_premarket_authorization_relationship_creation_performed","automatic_reopening_decision_performed","automatic_assessment_mutation_performed"):self.assertFalse(c[k])
if __name__=="__main__":unittest.main()
