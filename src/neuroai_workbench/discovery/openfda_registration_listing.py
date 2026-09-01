"""Bounded openFDA registration/listing projection for human-gated discovery."""
from __future__ import annotations
import hashlib,json
from collections.abc import Mapping,Sequence
from typing import Any

MAX_LIMIT=1000;MAX_SKIP=25000;MAX_DIRECT=26000
BOUNDARY=("FDA registration/listing data describes establishment-product representations. Registration or listing does not denote approval, clearance or authorization. "
          "The v0.1 representation identity is not exact device identity; product codes, proprietary names and K/PMA references remain linkage evidence requiring human resolution.")

def _text(v:Any)->str|None:
    if v is None:return None
    s=str(v).strip();return s or None

def _safe(v:Any)->Any:
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,list):return [_safe(x) for x in v]
    if isinstance(v,Mapping):return {str(k):_safe(val) for k,val in sorted(v.items(),key=lambda p:str(p[0]))}
    return str(v)

def _sha(v:Any)->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _names(raw:Any)->list[str]:
    if not isinstance(raw,list):return []
    return sorted({s for x in raw if (s:=_text(x))},key=str.casefold)
def _est_types(raw:Any)->list[str]:
    if isinstance(raw,list):return sorted({s for x in raw if (s:=_text(x))},key=str.casefold)
    s=_text(raw);return [s] if s else []
def _owner(reg:Mapping[str,Any],product:Mapping[str,Any])->str|None:
    direct=_text(product.get("owner_operator_number"))
    if direct:return direct
    oo=reg.get("owner_operator");return _text(oo.get("owner_operator_number")) if isinstance(oo,Mapping) else None

def _representation_identity(registration_number:str,owner_operator_number:str,product_code:str,names:list[str])->str:
    names_digest=_sha([n.casefold() for n in names])[:16].upper();return f"REGLIST:{registration_number}:{owner_operator_number}:{product_code.upper()}:{names_digest}"

def _expand(raw:Mapping[str,Any],query_id:str)->tuple[list[dict[str,Any]],dict[str,int]]:
    reg=raw.get("registration");reg=reg if isinstance(reg,Mapping) else {}
    registration_number=_text(reg.get("registration_number"));names=_names(raw.get("proprietary_name"));products=raw.get("products")
    if not isinstance(products,list):products=[]
    out=[];unreg=0;unowner=0;unproduct=0
    for product in products:
        if not isinstance(product,Mapping):continue
        owner=_owner(reg,product);code=_text(product.get("product_code"))
        if not registration_number:unreg+=1;continue
        if not owner:unowner+=1;continue
        if not code:unproduct+=1;continue
        ofda=product.get("openfda");ofda=ofda if isinstance(ofda,Mapping) else {}
        identity=_representation_identity(registration_number,owner,code,names)
        n={"record_kind":"NORMALIZED_OPENFDA_REGISTRATION_LISTING_REPRESENTATION","representation_identity":identity,"registration_number":registration_number,
           "fei_number":_text(reg.get("fei_number")),"registration_name":_text(reg.get("name")),"registration_status_code":_text(reg.get("status_code")),"registration_expiry_year":_text(reg.get("reg_expiry_date_year")),
           "owner_operator_number":owner,"establishment_type":_est_types(raw.get("establishment_type")),"product_code":code.upper(),"product_created_date":_text(product.get("created_date")),"product_exempt":_safe(product.get("exempt")),
           "device_class":_text(ofda.get("device_class")),"device_name":_text(ofda.get("device_name")),"regulation_number":_text(ofda.get("regulation_number")),"proprietary_names":names,
           "k_number":_text(raw.get("k_number")),"pma_number":_text(raw.get("pma_number")),"query_memberships":[query_id],
           "representation_is_exact_device_identity":False,"registration_or_listing_establishes_authorization":False,
           "boundary":"This is an establishment-product provider representation, not an exact device identity or FDA authorization record."}
        core=dict(n);core.pop("query_memberships",None);n["normalized_record_sha256"]=_sha(core);out.append(n)
    return out,{"unresolved_registration_number_count":unreg,"unresolved_owner_operator_number_count":unowner,"unresolved_product_code_count":unproduct}

def project_search_pages(*,query_id:str,search:str,pages:Sequence[Mapping[str,Any]],known_representation_sources:Mapping[str,str]|None=None)->dict[str,Any]:
    if not isinstance(query_id,str) or not query_id.strip():raise ValueError("query_id must be non-empty")
    if not isinstance(search,str) or not search.strip():raise ValueError("search must be non-empty")
    if not pages:raise ValueError("At least one registration/listing page is required")
    known={str(k).upper():str(v) for k,v in (known_representation_sources or {}).items()};totals=[];raw_count=0;expanded_count=0;by_identity={};dup_repr=0;unreg=unowner=unproduct=0;seq=True;prev_skip=prev_limit=None;page_reports=[]
    for index,raw_page in enumerate(pages,start=1):
        payload=raw_page.get("payload") if isinstance(raw_page,Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload,Mapping):raise ValueError(f"page {index}: payload must be object")
        meta=payload.get("meta");mr=meta.get("results") if isinstance(meta,Mapping) else None;rows=payload.get("results")
        if not isinstance(mr,Mapping) or not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):raise ValueError(f"page {index}: invalid registration/listing shape")
        total,skip,limit=mr.get("total"),mr.get("skip"),mr.get("limit")
        if not isinstance(total,int) or isinstance(total,bool) or total<0:raise ValueError(f"page {index}: total invalid")
        if not isinstance(skip,int) or isinstance(skip,bool) or not 0<=skip<=MAX_SKIP:raise ValueError(f"page {index}: skip invalid")
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=MAX_LIMIT:raise ValueError(f"page {index}: limit invalid")
        if index==1 and skip!=0:seq=False
        if prev_skip is not None and prev_limit is not None and skip!=prev_skip+prev_limit:seq=False
        prev_skip,prev_limit=skip,limit;totals.append(total);raw_count+=len(rows)
        page_expanded=0
        for raw in rows:
            representations,counts=_expand(raw,query_id);page_expanded+=len(representations);expanded_count+=len(representations);unreg+=counts["unresolved_registration_number_count"];unowner+=counts["unresolved_owner_operator_number_count"];unproduct+=counts["unresolved_product_code_count"]
            for n in representations:
                identity=n["representation_identity"];prior=by_identity.get(identity)
                if prior is None:by_identity[identity]=n
                else:
                    a,b=dict(prior),dict(n);a.pop("query_memberships",None);b.pop("query_memberships",None)
                    if a!=b:raise ValueError(f"Conflicting normalized registration/listing representations for {identity}")
                    dup_repr+=1
        page_reports.append({"page_index":index,"reported_total_count":total,"skip":skip,"limit":limit,"returned_provider_record_count":len(rows),"expanded_representation_count":page_expanded})
    distinct=sorted(set(totals));reported=distinct[0] if len(distinct)==1 else None;total_state="CONSISTENT" if reported is not None else "INCONSISTENT_ACROSS_PAGES";over=reported is not None and reported>MAX_DIRECT
    if reported is None:coverage_state="DENOMINATOR_UNAVAILABLE"
    elif over:coverage_state="OVER_LIMIT_BULK_OR_PARTITION_REQUIRED"
    elif not seq:coverage_state="INVALID_SEQUENCE"
    elif raw_count==reported:coverage_state="MATCH"
    else:coverage_state="PARTIAL_OR_MISMATCH"
    records=[];norms=[];known_dups=[]
    if not over:
        for identity in sorted(by_identity):
            n=by_identity[identity];dup=known.get(identity.upper());title=(n["proprietary_names"][0] if n["proprietary_names"] else n.get("device_name")) or identity
            r={"record_key":identity,"title":title,"url":f"https://api.fda.gov/device/registrationlisting.json?search=registration.registration_number:%22{n['registration_number']}%22","publisher":"U.S. FDA","source_class":"OFFICIAL_REGULATORY_LISTING_REPRESENTATION","suggested_source_id":f"SRC-OPENFDA-REGLIST-{hashlib.sha256(identity.encode()).hexdigest()[:16].upper()}","classification_hint":"DUPLICATE" if dup else "NEW","exact_device_identity":False}
            if dup:r["duplicate_of_source_id"]=dup;known_dups.append({"representation_identity":identity,"source_id":dup})
            records.append(r);norms.append(n)
    coverage={"source_system":"OPENFDA_DEVICE_REGISTRATION_LISTING","query_id":query_id,"search_sha256":hashlib.sha256(search.encode()).hexdigest(),"supplied_page_count":len(pages),"returned_provider_record_count":raw_count,"expanded_representation_count":expanded_count,"unique_representation_count":len(by_identity),"reported_total_count":reported,"reported_total_count_state":total_state,"skip_sequence_valid":seq,"skip_coverage_state":coverage_state,"over_26000_limit":over,"bulk_download_or_partition_required":over,"known_controlled_duplicate_count":len(known_dups),"known_controlled_duplicates":known_dups,"new_candidate_count":len(records)-len(known_dups),"duplicate_representation_count":dup_repr,"unresolved_registration_number_count":unreg,"unresolved_owner_operator_number_count":unowner,"unresolved_product_code_count":unproduct,"page_reports":page_reports,
        "representation_is_exact_device_identity":False,"registration_or_listing_is_marketing_authorization":False,"registration_or_listing_is_clearance_or_approval":False,"k_or_pma_reference_establishes_exact_configuration_authorization":False,"product_code_establishes_exact_device_identity":False,"automatic_establishment_entity_creation_performed":False,"automatic_device_or_system_entity_creation_performed":False,"automatic_registration_relationship_creation_performed":False,"automatic_premarket_authorization_relationship_creation_performed":False,"automatic_reopening_decision_performed":False,"automatic_assessment_mutation_performed":False,"boundary":BOUNDARY}
    return {"result_records":records,"normalized_records":norms,"coverage":coverage}
