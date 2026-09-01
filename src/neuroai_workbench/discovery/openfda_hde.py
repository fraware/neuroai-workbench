"""Bounded openFDA HDE projection for human-gated discovery."""
from __future__ import annotations
import hashlib,json,re
from collections.abc import Mapping,Sequence
from typing import Any

MAX_LIMIT=1000;MAX_SKIP=25000;MAX_DIRECT=26000;ORIGINAL="ORIGINAL"
HDE_RE=re.compile(r"^H[A-Z0-9._-]+$",re.I)
DECISION_MAP={"APPR":"HDE_APPROVAL_RECORDED","WTDR":"WITHDRAWAL_RECORDED","DENY":"DENIAL_RECORDED","LE30":"THIRTY_DAY_NOTICE_ACCEPTANCE_RECORDED","APRL":"RECLASSIFICATION_AFTER_APPROVAL_RECORDED","APWD":"WITHDRAWAL_AFTER_APPROVAL_RECORDED","GT30":"NO_DECISION_WITHIN_30_DAYS_RECORDED","APCV":"CONVERSION_AFTER_APPROVAL_RECORDED"}
BOUNDARY=("A projected HDE record preserves exact FDA H-prefixed application/supplement decision metadata. Exact APPR supports a scoped HDE approval record for that exact original/supplement. HDE approval does not establish reasonable assurance of effectiveness, facility-specific IRB approval, global authorization, exact current commercial configuration, all-configuration conformance, automatic assessment reopening, or canonical authority.")

def _text(v:Any)->str|None:
    if v is None:return None
    s=str(v).strip();return s or None

def _safe(v:Any)->Any:
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,list):return [_safe(x) for x in v]
    if isinstance(v,Mapping):return {str(k):_safe(x) for k,x in sorted(v.items(),key=lambda p:str(p[0]))}
    return str(v)
def _sha(v:Mapping[str,Any])->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _hde_scope(v:Any)->tuple[str,str]:
    n=(_text(v) or "").upper()
    if not n:return "","UNRESOLVED"
    return (n,"HDE") if HDE_RE.fullmatch(n) else (n,"NON_H_OUT_OF_SCOPE")
def _supp(v:Any)->str:return (_text(v) or ORIGINAL).upper()
def _identity(h:str,s:str)->str:return f"HDE:{h}:{s}"
def _decision(v:Any)->dict[str,Any]:
    code=(_text(v) or "").upper();sem=DECISION_MAP.get(code,"UNRESOLVED_DECISION_CODE")
    return {"decision_code":code or None,"decision_semantics":sem,"decision_code_recognized":code in DECISION_MAP,"decision_supports_hde_approval":code=="APPR","decision_supports_reasonable_assurance_of_effectiveness":False,"decision_establishes_facility_irb_approval":False}
def _normalize(raw:Mapping[str,Any],query_id:str)->tuple[dict[str,Any]|None,str]:
    hde,scope=_hde_scope(raw.get("pma_number"))
    if scope!="HDE":return None,scope
    supp=_supp(raw.get("supplement_number"));dec=_decision(raw.get("decision_code"));record={"record_kind":"NORMALIZED_OPENFDA_HDE_DECISION","hde_number":hde,"supplement_number":supp,"record_identity":_identity(hde,supp),"record_role":"ORIGINAL_APPLICATION" if supp==ORIGINAL else "SUPPLEMENT","trade_name":_text(raw.get("trade_name")),"generic_name":_text(raw.get("generic_name")),"applicant":_text(raw.get("applicant")),"date_received":_safe(raw.get("date_received")),"decision_date":_safe(raw.get("decision_date")),"decision_code":dec["decision_code"],"decision_semantics":dec["decision_semantics"],"decision_code_recognized":dec["decision_code_recognized"],"decision_supports_hde_approval":dec["decision_supports_hde_approval"],"decision_supports_reasonable_assurance_of_effectiveness":False,"decision_establishes_facility_irb_approval":False,"product_code":_text(raw.get("product_code")),"supplement_type":_text(raw.get("supplement_type")),"supplement_reason":_text(raw.get("supplement_reason")),"ao_statement":_text(raw.get("ao_statement")),"query_memberships":[query_id],"boundary":BOUNDARY}
    core=dict(record);core.pop("query_memberships");record["normalized_record_sha256"]=_sha(core);return record,scope

def project_search_pages(*,query_id:str,search:str,pages:Sequence[Mapping[str,Any]],known_record_sources:Mapping[str,str]|None=None)->dict[str,Any]:
    if not isinstance(query_id,str) or not query_id.strip():raise ValueError("query_id must be non-empty")
    if not isinstance(search,str) or not search.strip():raise ValueError("search must be non-empty")
    if not pages:raise ValueError("At least one HDE page is required")
    known={str(k).upper():str(v) for k,v in (known_record_sources or {}).items()};totals=[];by={};raw_count=dup_count=non_h=unresolved=0;reports=[];seq=True;prev_skip=prev_limit=None
    for idx,raw_page in enumerate(pages,start=1):
        payload=raw_page.get("payload") if isinstance(raw_page,Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload,Mapping):raise ValueError(f"page {idx}: payload must be object")
        meta=payload.get("meta");mr=meta.get("results") if isinstance(meta,Mapping) else None;rows=payload.get("results")
        if not isinstance(mr,Mapping) or not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):raise ValueError(f"page {idx}: invalid openFDA HDE shape")
        total,skip,limit=mr.get("total"),mr.get("skip"),mr.get("limit")
        if not isinstance(total,int) or isinstance(total,bool) or total<0:raise ValueError(f"page {idx}: total invalid")
        if not isinstance(skip,int) or isinstance(skip,bool) or not 0<=skip<=MAX_SKIP:raise ValueError(f"page {idx}: skip invalid")
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=MAX_LIMIT:raise ValueError(f"page {idx}: limit invalid")
        if idx==1 and skip!=0:seq=False
        if prev_skip is not None and skip!=prev_skip+prev_limit:seq=False
        prev_skip,prev_limit=skip,limit;totals.append(total);raw_count+=len(rows)
        for raw in rows:
            n,scope=_normalize(raw,query_id)
            if scope=="NON_H_OUT_OF_SCOPE":non_h+=1;continue
            if scope!="HDE" or n is None:unresolved+=1;continue
            identity=n["record_identity"];prior=by.get(identity)
            if prior is None:by[identity]=n
            else:
                a,b=dict(prior),dict(n);a.pop("query_memberships",None);b.pop("query_memberships",None)
                if a!=b:raise ValueError(f"Conflicting normalized HDE representations for {identity}")
                dup_count+=1
        reports.append({"page_index":idx,"reported_total_count":total,"skip":skip,"limit":limit,"returned_record_count":len(rows)})
    distinct=sorted(set(totals));reported=distinct[0] if len(distinct)==1 else None;state="CONSISTENT" if reported is not None else "INCONSISTENT_ACROSS_PAGES";over=reported is not None and reported>MAX_DIRECT
    if reported is None:coverage="DENOMINATOR_UNAVAILABLE"
    elif over:coverage="OVER_LIMIT_SEARCH_AFTER_OR_PARTITION_REQUIRED"
    elif not seq:coverage="INVALID_SEQUENCE"
    elif len(by)+non_h+unresolved==reported:coverage="MATCH"
    else:coverage="PARTIAL_OR_MISMATCH"
    records=[];norms=[];dups=[]
    if not over:
        for identity in sorted(by):
            n=by[identity];duplicate=known.get(identity.upper());r={"record_key":identity,"title":n.get("trade_name") or n.get("generic_name") or identity,"url":f"https://api.fda.gov/device/pma.json?search=pma_number:%22{n['hde_number']}%22","publisher":"U.S. FDA","source_class":"OFFICIAL_REGULATORY_HDE_RECORD","suggested_source_id":f"SRC-OPENFDA-HDE-{n['hde_number']}-{n['supplement_number']}","classification_hint":"DUPLICATE" if duplicate else "NEW","decision_semantics":n["decision_semantics"]}
            if duplicate:r["duplicate_of_source_id"]=duplicate;dups.append({"record_identity":identity,"source_id":duplicate})
            records.append(r);norms.append(n)
    cov={"source_system":"OPENFDA_DEVICE_PMA_HDE_SUBSET","query_id":query_id,"search_sha256":hashlib.sha256(search.encode()).hexdigest(),"supplied_page_count":len(pages),"returned_record_count":raw_count,"unique_composite_record_count":len(by),"reported_total_count":reported,"reported_total_count_state":state,"skip_sequence_valid":seq,"skip_coverage_state":coverage,"over_26000_limit":over,"search_after_or_partition_required":over,"out_of_scope_non_h_prefix_count":non_h,"known_controlled_duplicate_count":len(dups),"known_controlled_duplicates":dups,"new_candidate_count":len(records)-len(dups),"duplicate_representation_count":dup_count,"unresolved_hde_number_count":unresolved,"page_reports":reports,"decision_semantics_derived_only_from_exact_decision_code":True,"record_presence_is_hde_approval_claim":False,"hde_approval_is_reasonable_assurance_effectiveness_claim":False,"hde_approval_establishes_facility_irb_approval":False,"automatic_device_or_system_entity_creation_performed":False,"automatic_applicant_entity_creation_performed":False,"automatic_original_supplement_lineage_relationship_creation_performed":False,"automatic_effectiveness_claim_creation_performed":False,"automatic_facility_irb_authorization_claim_creation_performed":False,"automatic_global_authorization_claim_creation_performed":False,"automatic_system_conformance_claim_creation_performed":False,"automatic_reopening_decision_performed":False,"automatic_assessment_mutation_performed":False,"boundary":BOUNDARY}
    return {"result_records":records,"normalized_records":norms,"coverage":cov}
