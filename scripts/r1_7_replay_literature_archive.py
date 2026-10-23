"""Verify and replay four archived R1.7 literature receipts without granting completion.

This bounded utility reads the original public article snapshot ZIP *outside Git*,
verifies source bytes, the capture report and the four provisional ledger bundles,
then delegates semantic ledger validation to the repository's frozen R1.7 engine.
The output contains metadata only; it is not a publication or canonical product
record. Requires Python >=3.11 and the installed neuroai-workbench package.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from zipfile import BadZipFile, ZipFile

from neuroai_workbench.release_a_r1_route_execution_ledger import (
    canonical_sha256,
    derive_ledger_state,
    ledger_entry_id,
)

EXPECTED_ARCHIVE_SHA256 = "fed125c0f7d727c9fab5188ecc68914b2a7e18a04765d15697f33b6cb6bc6945"
EXPECTED_PMIDS = ("41939223", "42022893", "42505450", "42645991")
EXPECTED_ROUTE = "LITERATURE_RECORD_EXTRACTION"
UNRESOLVED_STATE = "RECORD_EXTRACTION_UNRESOLVED"


class ArchivedLiteratureError(ValueError):
    """An archived receipt or its frozen binding failed validation."""


def _decode_json(data: bytes, filename: str) -> dict[str, Any]:
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ArchivedLiteratureError(f"Invalid JSON in {filename}") from exc
    if not isinstance(result, dict):
        raise ArchivedLiteratureError(f"Expected a JSON object in {filename}")
    return result


def replay_archive(
    archive_path: Path,
    *,
    expected_archive_sha256: str = EXPECTED_ARCHIVE_SHA256,
    pmids: tuple[str, ...] = EXPECTED_PMIDS,
    state_builder: Callable[..., dict[str, Any]] = derive_ledger_state,
) -> dict[str, Any]:
    """Return a nonterminal digest-bound summary of exact saved literature bundles.

    ``expected_archive_sha256`` and ``pmids`` are injectable solely to permit
    independently generated, non-sensitive synthetic regression fixtures.
    Production callers must use their frozen defaults.
    """
    if len(pmids) != len(set(pmids)) or not pmids:
        raise ArchivedLiteratureError("PMID fixture scope must be nonempty and unique")
    archive_bytes = archive_path.read_bytes()
    archive_sha = hashlib.sha256(archive_bytes).hexdigest()
    if archive_sha != expected_archive_sha256:
        raise ArchivedLiteratureError("Original ZIP byte digest mismatch")

    try:
        with ZipFile(archive_path) as zf:
            damaged = zf.testzip()
            if damaged is not None:
                raise ArchivedLiteratureError(f"Archive member CRC failed: {damaged}")
            names = zf.namelist()
            if len(names) != len(set(names)):
                raise ArchivedLiteratureError("Duplicate archive member names")
            required = {"acquisition-report.json", "nonterminal-mentions.json"}
            for pmid in pmids:
                required.update(
                    {
                        f"pmid-{pmid}-fulltext.xml",
                        f"pmid-{pmid}-decision.json",
                        f"pmid-{pmid}-evidence-bundle.json",
                    }
                )
            if set(names) != required:
                raise ArchivedLiteratureError("Archived article/decision/bundle member set drift")
            report = _decode_json(zf.read("acquisition-report.json"), "acquisition-report.json")
            if report.get("expected") != len(pmids) or report.get("failures") != []:
                raise ArchivedLiteratureError("Acquisition report count or failure state mismatch")
            report_rows = report.get("results")
            if not isinstance(report_rows, list) or len(report_rows) != len(pmids):
                raise ArchivedLiteratureError("Acquisition report result coverage mismatch")
            by_pmid = {str(x.get("pmid")): x for x in report_rows if isinstance(x, dict)}
            if set(by_pmid) != set(pmids):
                raise ArchivedLiteratureError("Acquisition report PMID coverage mismatch")

            entries: list[dict[str, Any]] = []
            evidence_archive: dict[str, dict[str, Any]] = {}
            receipts: list[dict[str, Any]] = []
            for pmid in sorted(pmids):
                prefix = f"pmid-{pmid}"
                raw = zf.read(f"{prefix}-fulltext.xml")
                decision = _decode_json(zf.read(f"{prefix}-decision.json"), f"{prefix}-decision.json")
                bundle = _decode_json(zf.read(f"{prefix}-evidence-bundle.json"), f"{prefix}-evidence-bundle.json")
                acquisition = by_pmid[pmid]
                raw_sha = hashlib.sha256(raw).hexdigest()
                if (
                    acquisition.get("raw_sha256") != raw_sha
                    or acquisition.get("bytes") != len(raw)
                    or bundle.get("raw_snapshot_sha256") != raw_sha
                ):
                    raise ArchivedLiteratureError(f"Raw source hash/size mismatch for PMID {pmid}")
                if bundle.get("pmid") != pmid or bundle.get("capture_id") != acquisition.get("capture_id"):
                    raise ArchivedLiteratureError(f"Bundle PMID or capture binding mismatch for {pmid}")
                if decision.get("capture_id") != acquisition.get("capture_id"):
                    raise ArchivedLiteratureError(f"Decision capture binding mismatch for {pmid}")
                if (
                    decision.get("completion_state") != UNRESOLVED_STATE
                    or decision.get("extracted_candidate_keys") != []
                ):
                    raise ArchivedLiteratureError(f"Unexpected terminal decision for {pmid}")
                if not ("2026-09-24" <= str(decision.get("knowledge_observed_at", ""))[:10] <= "2026-10-24"):
                    raise ArchivedLiteratureError(f"Unexpected knowledge timestamp for {pmid}")
                previous_state = bundle.get("derived_state", {})
                if (
                    previous_state.get("completed_work_item_count") != 0
                    or previous_state.get("pending_work_item_count") != 192
                    or previous_state.get("unresolved_barrier_work_item_count") != 1
                ):
                    raise ArchivedLiteratureError(f"Prior per-paper ledger checkpoint is not unresolved for {pmid}")
                entry = bundle.get("ledger_entry")
                if not isinstance(entry, dict) or entry.get("ledger_entry_id") != ledger_entry_id(entry):
                    raise ArchivedLiteratureError(f"Missing/invalid content-bound ledger entry for {pmid}")
                record = entry.get("route_execution_record")
                if not isinstance(record, dict):
                    raise ArchivedLiteratureError(f"Missing ledger execution record for {pmid}")
                if record.get("execution_record_id") != (
                    "R1ROUTE-"
                    + canonical_sha256({key: value for key, value in record.items() if key != "execution_record_id"})
                ):
                    raise ArchivedLiteratureError(f"Execution record content digest mismatch for {pmid}")
                if (
                    record.get("execution_route") != EXPECTED_ROUTE
                    or record.get("completion_state") != UNRESOLVED_STATE
                    or record.get("work_item_completion_claimed") is not False
                    or record.get("work_item_id") != acquisition.get("work_item_id")
                    or record.get("covered_capture_ids") != [acquisition.get("capture_id")]
                    or record.get("extracted_leads") != []
                    or record.get("review_state") != "MACHINE_PROVISIONAL"
                ):
                    raise ArchivedLiteratureError(f"Unexpected route/completion semantics for {pmid}")
                ev = record.get("evidence")
                archives = bundle.get("evidence_archive")
                if not isinstance(ev, list) or len(ev) != 1 or not isinstance(archives, dict) or len(archives) != 1:
                    raise ArchivedLiteratureError(f"Missing or duplicate source evidence for {pmid}")
                evidence = ev[0]
                ref = evidence.get("evidence_ref")
                if set(archives) != {ref}:
                    raise ArchivedLiteratureError(f"Evidence reference mismatch for {pmid}")
                artifact = archives[ref]
                if (
                    artifact.get("capture_id") != acquisition.get("capture_id")
                    or artifact.get("query_or_seed_id")
                    != decision.get("retrieval_request", {}).get("request_context", {}).get("query_or_seed_id")
                    or artifact.get("knowledge_observed_at") != decision.get("knowledge_observed_at")
                    or artifact.get("response_context") != decision.get("response_context")
                    or artifact.get("retrieval_request") != decision.get("retrieval_request")
                    or artifact.get("content_representation") != "BASE64_BYTES"
                    or evidence.get("sha256") != canonical_sha256(artifact)
                ):
                    raise ArchivedLiteratureError(f"Evidence provenance/digest mismatch for {pmid}")
                try:
                    restored = base64.b64decode(artifact["content"], validate=True)
                except (KeyError, ValueError, binascii.Error) as exc:
                    raise ArchivedLiteratureError(f"Missing/invalid base64 source for {pmid}") from exc
                if restored != raw:
                    raise ArchivedLiteratureError(f"Embedded source bytes differ for {pmid}")
                if ref in evidence_archive:
                    raise ArchivedLiteratureError("Duplicate evidence reference across source bundles")
                evidence_archive[ref] = artifact
                entries.append(entry)
                receipts.append(
                    {
                        "pmid": pmid,
                        "capture_id": acquisition["capture_id"],
                        "work_item_id": record["work_item_id"],
                        "source_xml_sha256": raw_sha,
                        "source_xml_bytes": len(raw),
                        "ledger_entry_id": entry["ledger_entry_id"],
                        "evidence_ref": ref,
                        "acquired_at": decision["knowledge_observed_at"],
                        "completion_state": UNRESOLVED_STATE,
                    }
                )
    except (BadZipFile, EOFError) as exc:
        raise ArchivedLiteratureError("Invalid archived ZIP structure") from exc

    if len({x["capture_id"] for x in receipts}) != len(pmids):
        raise ArchivedLiteratureError("Duplicate frozen captures across original acquisitions")
    if len({x["work_item_id"] for x in receipts}) != len(pmids):
        raise ArchivedLiteratureError("Duplicate work-item receipts")
    state = state_builder(entries, evidence_archive=evidence_archive)
    if (
        state.get("frozen_work_item_count") != 192
        or state.get("frozen_capture_count") != 247
        or state.get("ledger_entry_count") != len(pmids)
        or state.get("completed_work_item_count") != 0
        or state.get("unresolved_barrier_work_item_count") != len(pmids)
        or state.get("active_extracted_lead_count") != 0
    ):
        raise ArchivedLiteratureError("Combined ledger state violates nonterminal archive scope")
    return {
        "artifact_type": "R1_7_FOUR_LITERATURE_BUNDLES_REPLAY_CHECKPOINT_NONTERMINAL_v0.1",
        "original_archive_sha256": archive_sha,
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "frozen_work_item_count": state["frozen_work_item_count"],
        "frozen_capture_count": state["frozen_capture_count"],
        "literature_record_work_items_total": 21,
        "original_source_receipts_replayed": len(receipts),
        "literature_work_items_without_direct_bundle_receipt": 21 - len(receipts),
        "completed_work_item_count": state["completed_work_item_count"],
        "pending_work_item_count": state["pending_work_item_count"],
        "unresolved_barrier_work_item_count": state["unresolved_barrier_work_item_count"],
        "active_extracted_lead_count": state["active_extracted_lead_count"],
        "receipts": receipts,
        "boundary": "Replays four previously acquired, machine-provisional unresolved literature records; remaining historical contexts are not completed. No canonical identities, final denominator, source exhaustion or A3/A4 increment.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path, help="Original saved 590503-byte GitHub artifact ZIP")
    parser.add_argument(
        "--output", required=True, type=Path, help="Metadata-only JSON destination, outside source checkout"
    )
    arguments = parser.parse_args(argv)
    report = replay_archive(arguments.archive)
    out = arguments.output
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out.with_name(out.name + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as dest:
            json.dump(report, dest, sort_keys=True, ensure_ascii=False, indent=2)
            dest.write("\n")
        os.replace(temp_path, out)
    finally:
        temp_path.unlink(missing_ok=True)
    print(f"Replayed {report['original_source_receipts_replayed']} nonterminal literature bundles; 0 completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
