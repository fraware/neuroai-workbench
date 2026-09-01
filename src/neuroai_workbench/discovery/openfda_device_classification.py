"""Bounded openFDA Device Classification projection for human-gated discovery."""
from __future__ import annotations
import hashlib,json,re
from collections.abc import Mapping,Sequence
from typing import Any
MAX_LIMIT=1000;MAX_SKIP=25000;MAX_DIRECT=26000;CODE_RE=re.compile(r"^[A-Z]{3}$")
BOUNDARY=("FDA product-code classification records identify generic device categories, not exact devices. "
          "A missing regulation number means the listed class is proposed/not final. Classification does not establish marketing authorization, clearance/approval, conformance or assessment effect.")
def _text(v:Any)->str|None:
    if v is None:return None
    s=str(v).strip();return s or None
def _safe(v:Any)->Any:
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,list):return [_safe(x) for x in v]
    if isinstance(v,Mapping):return {str(k):_safe(val) for k,val in sorted(v.items(),key=lambda p:str(p[0]))}
    return str(v)
def _sha(v:Mapping[str,Any])->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _normalize(raw:Mapping[str,Any],query_id:str)->dict[str,Any]|None:
    code=(_text(raw.get("product_code")) or "").upper()
    if not CODE_RE.fullmatch(code):return None
    reg=_text(raw.get("regulation_number"));finality="REGULATION_REFERENCED_CLASSIFICATION" if reg else "PROPOSED_CLASS_NOT_FINAL"
    n={"record_kind":"NORMALIZED_OPENFDA_DEVICE_CLASSIFICATION","product_code":code,"record_identity":f"OPENFDA_CLASS:{code}","device_name":_text(raw.get("device_name")),"definition":_text(raw.get("definition")),"device_class":_text(raw.get("device_class")),"classification_finality":finality,"regulation_number":reg,"medical_specialty":_text(raw.get("medical_specialty")),"medical_specialty_description":_text(raw.get("medical_specialty_description")),"review_code":_text(raw.get("review_code")),"implant_flag":_safe(raw.get("implant_flag")),"life_sustain_support_flag":_safe(raw.get("life_sustain_support_flag")),"gmp_exempt_flag":_safe(raw.get("gmp_exempt_flag")),"query_memberships":[query_id],"product_code_is_exact_device_identity":False,"classification_establishes_authorization":False,"boundary":("Product code identifies a generic FDA device category. Regulation-number absence makes the listed class proposed/not final; category classification does not establish exact device identity or authorization.")}
    core=dict(n);core.pop("query_memberships",None);n["normalized_record_sha256"]=_sha(core);return n
def project_search_pages(*,query_id:str,search:str,pages:Sequence[Mapping[str,Any]],known_product_code_sources:Mapping[str,str]|None=None)->dict[str,Any]:
    if not isinstance(query_id,str) or not query_id.strip():raise ValueError("query_id must be non-empty")
    if not isinstance(search,str) or not search.strip():raise ValueError("search must be non-empty")
    if not pages:raise ValueError("At least one classification page is required")
    known={str(k).upper():str(v) for k,v in (known_product_code_sources or {}).items()};totals=[];by_code={};raw_count=dup_count=unresolved=reg_count=proposed_count=0;seq=True;prev_skip=prev_limit=None;page_reports=[]
    for index,raw_page in enumerate(pages,start=1):
        payload=raw_page.get("payload") if isinstance(raw_page,Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload,Mapping):raise ValueError(f"page {index}: payload must be object")
        meta=payload.get("meta");mr=meta.get("results") if isinstance(meta,Mapping) else None;rows=payload.get("results")
        if not isinstance(mr,Mapping) or not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):raise ValueError(f"page {index}: invalid classification shape")
        total,skip,limit=mr.get("total"),mr.get("skip"),mr.get("limit")
        if not isinstance(total,int) or isinstance(total,bool) or total<0:raise ValueError(f"page {index}: total invalid")
        if not isinstance(skip,int) or isinstance(skip,bool) or not 0<=skip<=MAX_SKIP:raise ValueError(f"page {index}: skip invalid")
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=MAX_LIMIT:raise ValueError(f"page {index}: limit invalid")
        if index==1 and skip!=0:seq=False
        if prev_skip is not None and prev_limit is not None and skip!=prev_skip+prev_limit:seq=False
        prev_skip,prev_limit=skip,limit;totals.append(total);raw_count+=len(rows)
        for raw in rows:
            n=_normalize(raw,query_id)
            if n is None:unresolved+=1;continue
            if n["classification_finality"]=="REGULATION_REFERENCED_CLASSIFICATION":reg_count+=1
            else:proposed_count+=1
            code=n["product_code"];prior=by_code.get(code)
            if prior is None:by_code[code]=n
            else:
                a,b=dict(prior),dict(n);a.pop("query_memberships",None);b.pop("query_memberships",None)
                if a!=b:raise ValueError(f"Conflicting normalized classification representations for product code {code}")
                dup_count+=1
        page_reports.append({"page_index":index,"reported_total_count":total,"skip":skip,"limit":limit,"returned_record_count":len(rows)})
    distinct=sorted(set(totals));reported=distinct[0] if len(distinct)==1 else None;total_state="CONSISTENT" if reported is not None else "INCONSISTENT_ACROSS_PAGES";over=reported is not None and reported>MAX_DIRECT
    if reported is None:coverage_state="DENOMINATOR_UNAVAILABLE"
    elif over:coverage_state="OVER_LIMIT_BULK_OR_PARTITION_REQUIRED"
    elif not seq:coverage_state="INVALID_SEQUENCE"
    elif raw_count==reported:coverage_state="MATCH"
    else:coverage_state="PARTIAL_OR_MISMATCH"
    records=[];norms=[];known_dups=[]
    if not over:
        for code in sorted(by_code):
            n=by_code[code];identity=n["record_identity"];dup=known.get(identity.upper()) or known.get(code.upper());title=n.get("device_name") or code;r={"record_key":identity,"title":title,"url":f"https://api.fda.gov/device/classification.json?search=product_code:{code}","publisher":"U.S. FDA","source_class":"OFFICIAL_REGULATORY_CLASSIFICATION_RECORD","suggested_source_id":f"SRC-OPENFDA-CLASS-{code}","classification_hint":"DUPLICATE" if dup else "NEW","exact_device_identity":False,"classification_finality":n["classification_finality"]}
            if dup:r["duplicate_of_source_id"]=dup;known_dups.append({"product_code":code,"source_id":dup})
            records.append(r);norms.append(n)
    cov={"source_system":"OPENFDA_DEVICE_CLASSIFICATION","query_id":query_id,"search_sha256":hashlib.sha256(search.encode()).hexdigest(),"supplied_page_count":len(pages),"returned_record_count":raw_count,"unique_product_code_count":len(by_code),"reported_total_count":reported,"reported_total_count_state":total_state,"skip_sequence_valid":seq,"skip_coverage_state":coverage_state,"over_26000_limit":over,"bulk_download_or_partition_required":over,"known_controlled_duplicate_count":len(known_dups),"known_controlled_duplicates":known_dups,"new_candidate_count":len(records)-len(known_dups),"duplicate_representation_count":dup_count,"unresolved_product_code_count":unresolved,"regulation_referenced_classification_count":reg_count,"proposed_not_final_classification_count":proposed_count,"page_reports":page_reports,"product_code_is_exact_device_identity":False,"classification_record_is_marketing_authorization":False,"classification_record_is_clearance_or_approval":False,"device_class_is_system_conformance":False,"automatic_device_or_system_entity_creation_performed":False,"automatic_product_code_relationship_creation_performed":False,"automatic_regulation_relationship_creation_performed":False,"automatic_reopening_decision_performed":False,"automatic_assessment_mutation_performed":False,"boundary":BOUNDARY}
    return {"result_records":records,"normalized_records":norms,"coverage":cov}
