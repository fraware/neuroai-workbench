"""Opt-in acquisition of exact, public PMC XML for the frozen R1.7 pilot.

No network activity occurs without --allow-network. Output belongs outside Git.
The importer marks paper extraction as unresolved; a human must examine the
source before assigning any zero-lead or lead-bearing completion state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neuroai_workbench.release_a_r1_literature_pilot import (
    UNRESOLVED,
    import_snapshot,
    select_distinct_pilots,
)

PMC_BY_PMID = {
    "42505450": "PMC13406779",
    "42645991": "PMC13514590",
    "42022893": "PMC13095558",
    "41939223": "PMC13044042",
}
MAX_BYTES = 5 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise ValueError("PMC acquisition refuses redirects")


def _verified_xml(data: bytes, pmid: str, pmcid: str) -> None:
    root = ET.fromstring(data)
    if root.tag != "article":
        raise ValueError("PMC response is not an article XML document")
    ids = {
        item.attrib.get("pub-id-type"): (item.text or "").strip()
        for item in root.iter("article-id")
    }
    if ids.get("pmid") != pmid or ids.get("pmc") not in {pmcid, pmcid.removeprefix("PMC")}:
        raise ValueError(f"PMC article identifiers do not match the frozen PMID/PMCID; observed={ids}")


def capture_one(row: dict[str, str], output: Path) -> dict[str, Any]:
    pmid = row["pmid"]
    pmcid = PMC_BY_PMID[pmid]
    locator = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    request = urllib.request.Request(
        locator,
        headers={
            "Accept": "application/xml, text/xml",
            "Accept-Encoding": "identity",
            "User-Agent": "NeuroAI-R1.7-Public-Literature/0.1 (+https://github.com/fraware/neuroai-workbench)",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=25) as response:
        if response.status != 200 or response.geturl() != locator:
            raise ValueError("PMC response status or final URL mismatch")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("PMC response exceeds fixed byte limit")
        content_type = response.headers.get("Content-Type", "")
        if "xml" not in content_type.lower():
            raise ValueError("PMC response does not have an XML content type")
        response_headers = {
            "date": response.headers.get("Date"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "content_length": response.headers.get("Content-Length"),
        }
    _verified_xml(data, pmid, pmcid)
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(data).hexdigest()
    decision: dict[str, Any] = {
        "capture_id": row["capture_id"],
        "source_locator": locator,
        "knowledge_observed_at": captured_at,
        "retrieval_request": {
            "method": "GET",
            "locator": locator,
            "request_context": {"query_or_seed_id": row["query_or_seed_id"]},
        },
        "response_context": {
            "retrieval_status": "RETRIEVED",
            "content_type": content_type,
            "encoding": "utf-8",
            "final_locator": locator,
            "response_metadata": {
                "status_code": 200,
                "raw_sha256": digest,
                "headers": response_headers,
            },
        },
        "completion_state": UNRESOLVED,
        "extracted_candidate_keys": [],
    }
    bundle = import_snapshot(data, decision)
    (output / f"pmid-{pmid}-fulltext.xml").write_bytes(data)
    (output / f"pmid-{pmid}-decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / f"pmid-{pmid}-evidence-bundle.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "work_item_id": row["work_item_id"],
        "capture_id": row["capture_id"],
        "source_locator": locator,
        "captured_at": captured_at,
        "raw_sha256": digest,
        "bytes": len(data),
        "status": "CAPTURED_FULL_TEXT_EXTRACTION_UNRESOLVED",
        "ledger_completed_work_item_count": bundle["derived_state"]["completed_work_item_count"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, choices=[1, 2, 3, 4], default=3)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_network:
        parser.error("Network access is opt-in: pass --allow-network explicitly")
    rows = select_distinct_pilots(args.count)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "status": "INCOMPLETE",
        "expected": len(rows),
        "results": [],
        "failures": [],
        "boundary": "RAW_PUBLIC_XML;SAVED_RESPONSE_BYTES;EXTRACTION_UNRESOLVED",
    }
    for row in rows:
        try:
            report["results"].append(capture_one(row, args.output_dir))
        except (OSError, ValueError, ET.ParseError, urllib.error.URLError) as exc:
            report["failures"].append({"pmid": row["pmid"], "error": type(exc).__name__, "detail": str(exc)[:300]})
    report["status"] = "CAPTURED_PENDING_EXTRACTION" if not report["failures"] else "INCOMPLETE"
    (args.output_dir / "acquisition-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
