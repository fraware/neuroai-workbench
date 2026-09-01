"""Bounded openFDA UDI/GUDID projection for human-gated discovery."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

MAX_LIMIT=1000
MAX_SKIP=25000
MAX_DIRECT=26000
BOUNDARY=(
    "A projected GUDID/openFDA record preserves exact Primary-DI device-record identity and FDA public-version state. "
    "It does not establish marketing authorization, current real-world availability, clinical effectiveness, exact assessed-system configuration, "
    "system conformance, automatic assessment reopening, or canonical authority. Secondary/previous DIs and premarket references remain linkage evidence."
)

def _text(v:Any)->str|None:
    if v is None:return None
    s=str(v).strip();return s or None

def _safe(v:Any)->Any:
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,list):return [_safe(x) for x in v]
    if isinstance(v,Mapping):return {str(k):_safe(val) for k,val in sorted(v.items(),key=lambda p:str(p[0]))}
    return str(v)

def _sha(v:Mapping[str,Any])->str:
    b=json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8");return hashlib.sha256(b).hexdigest()

def _identifier_rows(raw:Any)->list[dict[str,Any]]:
    if not isinstance(raw,list):return []
    rows=[]
    for item in raw:
        if not isinstance(item,Mapping):continue
        agency=_text(item.get("issuing_agency"));identifier=_text(item.get("id"));kind=_text(item.get("type"))
        if agency and identifier and kind:rows.append({"issuing_agency":agency,"id":identifier,"type":kind})
    rows.sort(key=lambda x:(x["type"].upper(),x["issuing_agency"].upper(),x["id"]))
    return rows

def _primary(identifiers:list[dict[str,Any]])->tuple[dict[str,Any]|None,int]:
    rows=[x for x in identifiers if x["type"].strip().upper()=="PRIMARY"]
    return (rows[0] if len(rows)==1 else None,len(rows))

def _premarket_rows(raw:Any)->list[dict[str,Any]]:
    if not isinstance(raw,list):return []
    out=[]
    for item in raw:
        if not isinstance(item,Mapping):continue
        row={
            "submission_number":_text(item.get("submission_number")),
            "supplement_number":_text(item.get("supplement_number")),
            "submission_type":_text(item.get("submission_type") if "submission_type" in item else item.get("submissions_type")),
        }
        if any(v is not None for v in row.values()):out.append(row)
    out.sort(key=lambda x:tuple(str(x.get(k) or "") for k in ("submission_type","submission_number","supplement_number")))
    return out

def _product_codes(raw:Any)->list[dict[str,Any]]:
    if not isinstance(raw,list):return []
    out=[]
    for item in raw:
        if not isinstance(item,Mapping):continue
        code=_text(item.get("code"));name=_text(item.get("name"))
        if code:out.append({"code":code,"name":name})
    out.sort(key=lambda x:(x["code"],str(x.get("name") or "")));return out

def _identity(primary:Mapping[str,Any])->str:
    return f"UDI:{str(primary['issuing_agency']).upper()}:{primary['id']}"

def _normalize(raw:Mapping[str,Any],query_id:str)->tuple[dict[str,Any]|None,str]:
    identifiers=_identifier_rows(raw.get("identifiers"));primary,count=_primary(identifiers)
    if count==0:return None,"UNRESOLVED_PRIMARY_DI"
    if count>1:return None,"MULTIPLE_PRIMARY_DI"
    assert primary is not None
    normalized={
        "record_kind":"NORMALIZED_OPENFDA_UDI_DEVICE_RECORD",
        "record_identity":_identity(primary),
        "primary_di":primary["id"],
        "primary_di_issuing_agency":primary["issuing_agency"],
        "record_key":_text(raw.get("record_key") if "record_key" in raw else raw.get("public_device_record_key")),
        "record_status":_text(raw.get("record_status")),
        "public_version_number":_text(raw.get("public_version_number")),
        "public_version_date":_text(raw.get("public_version_date")),
        "public_version_status":_text(raw.get("public_version_status")),
        "publish_date":_text(raw.get("publish_date")),
        "brand_name":_text(raw.get("brand_name")),
        "company_name":_text(raw.get("company_name")),
        "version_or_model_number":_text(raw.get("version_or_model_number")),
        "catalog_number":_text(raw.get("catalog_number")),
        "device_description":_text(raw.get("device_description")),
        "commercial_distribution_status":_text(raw.get("commercial_distribution_status")),
        "commercial_distribution_end_date":_text(raw.get("commercial_distribution_end_date")),
        "identifiers":identifiers,
        "premarket_submissions":_premarket_rows(raw.get("premarket_submissions")),
        "product_codes":_product_codes(raw.get("product_codes")),
        "query_memberships":[query_id],
        "boundary":(
            "Primary DI plus issuing agency anchors this GUDID device record. FDA record/public-version fields track provider updates. "
            "Secondary/previous identifiers, premarket references and submitted distribution state do not automatically establish configuration equivalence, authorization or availability."
        ),
    }
    core=dict(normalized);core.pop("query_memberships",None);normalized["normalized_record_sha256"]=_sha(core);return normalized,"VALID"

def project_search_pages(*,query_id:str,search:str,pages:Sequence[Mapping[str,Any]],known_udi_sources:Mapping[str,str]|None=None)->dict[str,Any]:
    if not isinstance(query_id,str) or not query_id.strip():raise ValueError("query_id must be non-empty")
    if not isinstance(search,str) or not search.strip():raise ValueError("search must be non-empty")
    if not pages:raise ValueError("At least one UDI page is required")
    known={str(k).upper():str(v) for k,v in (known_udi_sources or {}).items()}
    totals=[];by_identity={};raw_count=0;duplicate_count=0;unresolved=0;multiple=0;sequence_valid=True;previous_skip=None;previous_limit=None;page_reports=[]
    for index,raw_page in enumerate(pages,start=1):
        payload=raw_page.get("payload") if isinstance(raw_page,Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload,Mapping):raise ValueError(f"page {index}: payload must be object")
        meta=payload.get("meta");mr=meta.get("results") if isinstance(meta,Mapping) else None;rows=payload.get("results")
        if not isinstance(mr,Mapping) or not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):raise ValueError(f"page {index}: invalid openFDA UDI shape")
        total,skip,limit=mr.get("total"),mr.get("skip"),mr.get("limit")
        if not isinstance(total,int) or isinstance(total,bool) or total<0:raise ValueError(f"page {index}: total invalid")
        if not isinstance(skip,int) or isinstance(skip,bool) or not 0<=skip<=MAX_SKIP:raise ValueError(f"page {index}: skip invalid")
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=MAX_LIMIT:raise ValueError(f"page {index}: limit invalid")
        if index==1 and skip!=0:sequence_valid=False
        if previous_skip is not None and previous_limit is not None and skip!=previous_skip+previous_limit:sequence_valid=False
        previous_skip,previous_limit=skip,limit;totals.append(total);raw_count+=len(rows)
        for raw in rows:
            n,state=_normalize(raw,query_id)
            if state=="UNRESOLVED_PRIMARY_DI":unresolved+=1;continue
            if state=="MULTIPLE_PRIMARY_DI":multiple+=1;continue
            assert n is not None;identity=n["record_identity"];prior=by_identity.get(identity)
            if prior is None:by_identity[identity]=n
            else:
                a,b=dict(prior),dict(n);a.pop("query_memberships",None);b.pop("query_memberships",None)
                if a!=b:raise ValueError(f"Conflicting normalized UDI representations for {identity}")
                duplicate_count+=1
        page_reports.append({"page_index":index,"reported_total_count":total,"skip":skip,"limit":limit,"returned_record_count":len(rows)})
    distinct=sorted(set(totals));reported=distinct[0] if len(distinct)==1 else None;total_state="CONSISTENT" if reported is not None else "INCONSISTENT_ACROSS_PAGES";over=reported is not None and reported>MAX_DIRECT
    if reported is None:coverage_state="DENOMINATOR_UNAVAILABLE"
    elif over:coverage_state="OVER_LIMIT_BULK_OR_PARTITION_REQUIRED"
    elif not sequence_valid:coverage_state="INVALID_SEQUENCE"
    elif raw_count==reported:coverage_state="MATCH"
    else:coverage_state="PARTIAL_OR_MISMATCH"
    records=[];norms=[];known_dups=[]
    if not over:
        for identity in sorted(by_identity):
            n=by_identity[identity];dup=known.get(identity.upper());title=n.get("brand_name") or n.get("device_description") or identity
            r={"record_key":identity,"title":title,"url":f"https://api.fda.gov/device/udi.json?search=identifiers.id:%22{n['primary_di']}%22","publisher":"U.S. FDA","source_class":"OFFICIAL_DEVICE_IDENTIFICATION_RECORD","suggested_source_id":f"SRC-OPENFDA-UDI-{hashlib.sha256(identity.encode()).hexdigest()[:16].upper()}","classification_hint":"DUPLICATE" if dup else "NEW"}
            if dup:r["duplicate_of_source_id"]=dup;known_dups.append({"record_identity":identity,"source_id":dup})
            records.append(r);norms.append(n)
    coverage={"source_system":"OPENFDA_DEVICE_UDI_GUDID","query_id":query_id,"search_sha256":hashlib.sha256(search.encode()).hexdigest(),"supplied_page_count":len(pages),"returned_record_count":raw_count,"unique_primary_di_record_count":len(by_identity),"reported_total_count":reported,"reported_total_count_state":total_state,"skip_sequence_valid":sequence_valid,"skip_coverage_state":coverage_state,"over_26000_limit":over,"bulk_download_or_partition_required":over,"known_controlled_duplicate_count":len(known_dups),"known_controlled_duplicates":known_dups,"new_candidate_count":len(records)-len(known_dups),"duplicate_representation_count":duplicate_count,"unresolved_primary_di_count":unresolved,"multiple_primary_di_count":multiple,"page_reports":page_reports,"automatic_device_or_system_entity_creation_performed":False,"automatic_company_entity_creation_performed":False,"automatic_di_relationship_creation_performed":False,"automatic_premarket_authorization_relationship_creation_performed":False,"automatic_current_commercial_availability_claim_creation_performed":False,"automatic_marketing_authorization_claim_creation_performed":False,"automatic_effectiveness_claim_creation_performed":False,"automatic_system_conformance_claim_creation_performed":False,"automatic_reopening_decision_performed":False,"automatic_assessment_mutation_performed":False,"boundary":BOUNDARY}
    return {"result_records":records,"normalized_records":norms,"coverage":coverage}
