"""Reproduce the published six-table EEG device-list extraction from exact archived XML.

This captures raw publication rows. It does not resolve identity, assess
currentness, validate device capability, or create canonical product records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

PMID = "42505450"
PMCID = "PMC13406779"
DOI = "10.3390/bios16070374"
RAW_SOURCE_SHA256 = "9b6552f265236c2c65dedde840d5cf0de0472ba607aed68d93dd61ee248d6c5f"
FORM_FACTORS = (
    "rigid_and_semi_rigid_head_mounted",
    "headband",
    "cap_based",
    "patch",
    "in_ear_headphones",
    "glasses_integrated",
)
ROW_COUNTS = (13, 15, 10, 6, 8, 5)


def _visible_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def extract_table_rows(raw: bytes, *, frozen_source: bool = True) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    if frozen_source and digest != RAW_SOURCE_SHA256:
        raise ValueError("Device table extraction requires the exact acquired source bytes")
    root = ET.fromstring(raw)
    if root.tag != "article":
        raise ValueError("Device table source must be a JATS article")
    ids = {node.get("pub-id-type"): (node.text or "").strip() for node in root.iter("article-id")}
    if ids.get("pmid") != PMID or ids.get("pmcid") != PMCID:
        raise ValueError("Archived source PMID/PMCID mismatch")
    wraps = root.findall(".//table-wrap")
    if len(wraps) < 6:
        raise ValueError("Expected six published device-comparison tables")
    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for position, form_factor in enumerate(FORM_FACTORS, start=1):
        tw = wraps[position - 1]
        label_element = tw.find("label")
        caption_element = tw.find("caption")
        if label_element is None or caption_element is None:
            raise ValueError("Device table lacks a label or caption")
        label = _visible_text(label_element)
        caption = _visible_text(caption_element)
        if label != f"Table {position}":
            raise ValueError("Source device-table order changed")
        rows = tw.findall(".//tr")
        if len(rows) < 2:
            raise ValueError("Device table has no data rows")
        header = [_visible_text(cell) for cell in rows[0] if cell.tag in {"td", "th"}]
        if len(header) != 7 or header[0] != "Device":
            raise ValueError("Device table has a nonconforming seven-column header")
        row_count = 0
        for row_number, row in enumerate(rows[1:], start=1):
            cells = [_visible_text(cell) for cell in row if cell.tag in {"td", "th"}]
            if len(cells) != 7 or not cells[0]:
                raise ValueError("Device table row has a missing or nonconforming cell")
            canonical = json.dumps(cells, sort_keys=False, ensure_ascii=False, separators=(",", ":")).encode()
            results.append(
                {
                    "source_pmid": PMID,
                    "source_pmcid": PMCID,
                    "source_raw_xml_sha256": digest,
                    "article_doi": DOI,
                    "source_locator": f"https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML",
                    "table_number": position,
                    "table_label": label,
                    "table_caption": caption,
                    "form_factor": form_factor,
                    "row_number_1_based": row_number,
                    "raw_device_designation": cells[0],
                    "raw_columns": dict(zip(header, cells, strict=True)),
                    "raw_row_content_sha256": hashlib.sha256(canonical).hexdigest(),
                    "candidate_status": "UNRESOLVED_TABLE_ROW_MENTION",
                    "canonical_offering_id": None,
                    "world_time_qualification": "NOT_ASSESSED",
                    "commercial_availability": "NOT_ASSESSED",
                }
            )
            row_count += 1
        if frozen_source and row_count != ROW_COUNTS[position - 1]:
            raise ValueError("Actual archived device-table row count drift")
        counts[str(position)] = row_count
    if frozen_source and (len(results) != 57 or len({r["raw_device_designation"] for r in results}) != 57):
        raise ValueError("Archived table designation count drift")
    return {
        "artifact_type": "R1_7_PMC42505450_DEVICE_TABLE_ROW_EXTRACTION_v0.1",
        "source_run_url": "https://github.com/fraware/neuroai-workbench/actions/runs/39543302737",
        "source_evidence_sha256": digest,
        "source_verified_jats_article_ids": {"pmid": PMID, "pmcid": PMCID},
        "raw_row_count": len(results),
        "table_counts": counts,
        "method": (
            "Extract first six article JATS tables with header Device and exactly seven columns, "
            "preserve raw row cells; no product resolution or world-time eligibility inferred"
        ),
        "identity_boundary": (
            "57 published table rows are not asserted to be 57 distinct/current/eligible/marketed products"
        ),
        "rows": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = extract_table_rows(args.input.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['raw_row_count']} raw source table rows, not canonical products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
