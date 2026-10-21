"""Offline R1.7 literature pilot: frozen capture selection and evidence-bound imports.

No network retrieval, product identity assignment, or scientific screening is performed
by this module. A human-supplied extraction decision and independently saved response
bytes are prerequisites for materializing any R1.7 ledger entry.
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import ProductDiscoveryError
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    LITERATURE_RECORD_EXTRACTION,
    extracted_lead_id,
    route_execution_record_id,
)
from neuroai_workbench.release_a_r1_execution_unit_routing_refinement import load_routing_refinement
from neuroai_workbench.release_a_r1_resolution import (
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)
from neuroai_workbench.release_a_r1_route_execution_ledger import (
    EVIDENCE_ARTIFACT_SCHEMA_ID,
    canonical_sha256,
    derive_ledger_state,
    ledger_entry_id,
)

BUNDLE_ID = "R1_7_OFFLINE_LITERATURE_EVIDENCE_BUNDLE_v0.1"
ZERO = "RECORD_EXTRACTED_ZERO_OFFERING_LEADS"
WITH_LEADS = "RECORD_EXTRACTED_WITH_OFFERING_LEADS"
UNRESOLVED = "RECORD_EXTRACTION_UNRESOLVED"


def literature_worklist() -> list[dict[str, str]]:
    """Bind each literature route to its exact frozen capture and PMID."""
    routing = load_routing_refinement()
    sources = compile_r1_source_records(load_r1_candidate_resolution_manifest())
    by_capture = {str(item["capture_id"]): item for item in sources}
    if len(by_capture) != len(sources):
        raise ProductDiscoveryError("Frozen source capture IDs are duplicated")
    result: list[dict[str, str]] = []
    for item in routing["route_table"]:
        if item["execution_route"] != LITERATURE_RECORD_EXTRACTION:
            continue
        captures = item["capture_ids"]
        if len(captures) != 1:
            raise ProductDiscoveryError("R1.7 actual literature work item must cover one frozen capture")
        capture_id = str(captures[0])
        source = by_capture[capture_id]
        match = re.fullmatch(r"lit-([0-9]+)", str(source["normalized_candidate_label"]))
        if match is None:
            raise ProductDiscoveryError("R1.7 literature capture has no unambiguous frozen PMID label")
        result.append(
            {
                "work_item_id": str(item["work_item_id"]),
                "capture_id": capture_id,
                "pmid": match.group(1),
                "query_or_seed_id": str(source["query_or_seed_id"]),
                "source_observation_ref": str(source["source_observation_ref"]),
                "source_packet_id": str(source["source_packet_id"]),
                "frame_id": str(source["frame_id"]),
                "round_id": str(source["round_id"]),
                "historical_capture_outcome": str(source["outcome"]),
                "suggested_public_locator": f"https://pubmed.ncbi.nlm.nih.gov/{match.group(1)}/",
                "execution_status": "PENDING_NEW_SOURCE_EVIDENCE",
            }
        )
    result.sort(key=lambda row: row["work_item_id"])
    if len(result) != 21 or len({item["capture_id"] for item in result}) != 21:
        raise ProductDiscoveryError("R1.7 literature execution population drift")
    return result


def select_distinct_pilots(count: int = 3) -> list[dict[str, str]]:
    """Pick distinct papers in frozen work-item order, retaining original captures."""
    if count < 1:
        raise ValueError("Pilot count must be positive")
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in literature_worklist():
        if row["pmid"] in seen:
            continue
        seen.add(row["pmid"])
        selected.append(row)
        if len(selected) == count:
            return selected
    raise ValueError("Pilot count exceeds the number of distinct frozen literature identifiers")


def import_snapshot(snapshot: bytes, decision: Mapping[str, Any]) -> dict[str, Any]:
    """Validate operator-described saved bytes and an explicit extraction decision.

    This transforms supplied bytes, but makes no independent assertion that the
    operator's HTTP metadata, publication identity or extracted leads are true.
    """
    allowed = {
        "capture_id",
        "source_locator",
        "knowledge_observed_at",
        "retrieval_request",
        "response_context",
        "completion_state",
        "extracted_candidate_keys",
    }
    if set(decision) != allowed:
        raise ProductDiscoveryError("Offline literature decision requires exact fields")
    capture_id = decision["capture_id"]
    if not isinstance(capture_id, str):
        raise ProductDiscoveryError("Offline literature capture_id must be text")
    row = next((r for r in literature_worklist() if r["capture_id"] == capture_id), None)
    if row is None:
        raise ProductDiscoveryError("Offline literature capture is outside the frozen R1.7 population")
    if not snapshot:
        raise ProductDiscoveryError("Offline literature snapshot must contain actual saved bytes")
    locator = decision["source_locator"]
    if not isinstance(locator, str) or not locator.startswith("https://"):
        raise ProductDiscoveryError("Offline literature source locator must be HTTPS")
    request = decision["retrieval_request"]
    response = decision["response_context"]
    if not isinstance(request, Mapping) or not isinstance(response, Mapping):
        raise ProductDiscoveryError("Offline literature request and response metadata must be objects")
    if request.get("locator") != locator or request.get("method") != "GET":
        raise ProductDiscoveryError("Offline literature request must describe the supplied GET locator")
    if request.get("request_context") != {"query_or_seed_id": row["query_or_seed_id"]}:
        raise ProductDiscoveryError("Offline literature request must bind its frozen query identity")
    response_metadata = response.get("response_metadata")
    if not isinstance(response_metadata, Mapping):
        raise ProductDiscoveryError("Offline literature response metadata must be an object")
    content_sha256 = hashlib.sha256(snapshot).hexdigest()
    if response_metadata.get("raw_sha256") != content_sha256:
        raise ProductDiscoveryError("Offline literature response raw_sha256 differs from saved bytes")
    state = decision["completion_state"]
    if state not in {ZERO, WITH_LEADS, UNRESOLVED}:
        raise ProductDiscoveryError("Offline literature decision has no explicit allowed completion state")
    keys = decision["extracted_candidate_keys"]
    if not isinstance(keys, list) or any(not isinstance(k, str) or not k.strip() for k in keys):
        raise ProductDiscoveryError("Offline literature candidate keys must be nonblank strings")
    if (state == WITH_LEADS) != bool(keys):
        raise ProductDiscoveryError("Lead-bearing completion must list leads; other states must leave leads empty")
    artifact = {
        "artifact_schema_id": EVIDENCE_ARTIFACT_SCHEMA_ID,
        "evidence_ref": "",
        "capture_id": capture_id,
        "query_or_seed_id": row["query_or_seed_id"],
        "source_locator": locator,
        "knowledge_observed_at": decision["knowledge_observed_at"],
        "retrieval_request": dict(request),
        "response_context": dict(response),
        "content_representation": "BASE64_BYTES",
        "content": base64.b64encode(snapshot).decode("ascii"),
    }
    artifact["evidence_ref"] = "R1EVID-" + canonical_sha256(
        {
            "capture_id": capture_id,
            "source_locator": locator,
            "observed_at": decision["knowledge_observed_at"],
            "raw_sha256": content_sha256,
        }
    )
    evidence_ref = str(artifact["evidence_ref"])
    proposition = {
        ZERO: "RECORD_ZERO_OFFERING_LEADS",
        WITH_LEADS: "RECORD_WITH_OFFERING_LEADS",
        UNRESOLVED: "RECORD_EXTRACTION_UNRESOLVED",
    }[state]
    evidence = {
        "evidence_ref": evidence_ref,
        "capture_id": capture_id,
        "query_or_seed_id": row["query_or_seed_id"],
        "source_locator": locator,
        "knowledge_observed_at": decision["knowledge_observed_at"],
        "sha256": canonical_sha256(artifact),
        "evidence_role": "RECORD_EXTRACTION",
        "supported_propositions": [proposition],
    }
    source_observation_ref = "OBS-R17-" + content_sha256
    leads = [
        {
            "lead_id": extracted_lead_id(row["work_item_id"], key, source_observation_ref),
            "candidate_key": key,
            "source_observation_ref": source_observation_ref,
            "evidence_ref": evidence_ref,
            "canonical_offering_id": None,
        }
        for key in keys
    ]
    leads.sort(key=lambda item: item["lead_id"])
    record: dict[str, Any] = {
        "execution_record_id": "",
        "work_item_id": row["work_item_id"],
        "execution_route": LITERATURE_RECORD_EXTRACTION,
        "completion_state": state,
        "review_state": "MACHINE_PROVISIONAL",
        "reviewer_id": None,
        "evidence": [evidence],
        "extracted_leads": leads,
        "source_scope_exhausted": False,
        "finite_cardinality_upper_bound": None,
        "global_source_exhaustion_claimed": False,
        "covered_capture_ids": [capture_id],
        "work_item_completion_claimed": state != UNRESOLVED,
    }
    record["execution_record_id"] = route_execution_record_id(record)
    entry: dict[str, Any] = {
        "ledger_entry_id": "",
        "route_execution_record": record,
        "supersedes_ledger_entry_ids": [],
    }
    entry["ledger_entry_id"] = ledger_entry_id(entry)
    archive = {evidence_ref: artifact}
    state_report = derive_ledger_state([entry], evidence_archive=archive)
    return {
        "bundle_id": BUNDLE_ID,
        "capture_id": capture_id,
        "pmid": row["pmid"],
        "raw_snapshot_sha256": content_sha256,
        "ledger_entry": entry,
        "evidence_archive": archive,
        "derived_state": state_report,
        "boundary": "OPERATOR_SUPPLIED_SOURCE_AND_EXTRACTION_CLAIMS;NONCANONICAL",
    }


def combine_bundles(bundles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate independent captures under the existing R1.7 validator."""
    if not bundles:
        raise ProductDiscoveryError("At least one saved literature bundle is required")
    entries: list[Mapping[str, Any]] = []
    archive: dict[str, Mapping[str, Any]] = {}
    for bundle in bundles:
        if bundle.get("bundle_id") != BUNDLE_ID:
            raise ProductDiscoveryError("Input is not a literature evidence bundle")
        entry = bundle.get("ledger_entry")
        captured = bundle.get("evidence_archive")
        if not isinstance(entry, Mapping) or not isinstance(captured, Mapping):
            raise ProductDiscoveryError("Literature bundle has invalid record or evidence archive")
        entries.append(entry)
        for ref, artifact in captured.items():
            if ref in archive:
                raise ProductDiscoveryError("Duplicate literature evidence reference")
            archive[str(ref)] = cast(Mapping[str, Any], artifact)
    return {
        "bundle_id": "R1_7_OFFLINE_LITERATURE_AGGREGATE_v0.1",
        "ledger_entries": entries,
        "evidence_archive": archive,
        "derived_state": derive_ledger_state(entries, evidence_archive=archive),
        "boundary": "NONCANONICAL_RESEARCH_EVIDENCE;NO_PRODUCT_IDENTITY_ALLOCATION",
    }
