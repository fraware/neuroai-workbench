"""Replay three bounded temporal claims against the saved October source bytes.

This read-only verifier accepts only the archived six-source acquisition
artifact captured on 2026-10-21. It checks raw archive and page hashes,
original HTTP status and source attribution, then matches narrow source
statements. It does not verify clinical outcomes, product availability,
independent sales, temporal eligibility, or an A-P1 human review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ARCHIVE_SHA256 = "4d3ef4f60a9c14c381eb5554d903497be0dab44cf6f987dadfd29a768bfba885"
REQUIRED = {
    "flow-fda-pma.html": {
        "source_category": "REGULATOR_PMA",
        "expected_sha256": "398d6e3dd7bd1fee79460de54afa293d8578fbeb8920fa895ca850469138ea4d",
        "expected_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P230024",
        "pattern": r"PMA Number\s+P230024.*?Decision Date\s+12/08/2025",
        "bounded_assertion": "PMA P230024 lists decision date 2025-12-08",
    },
    "flow-september-launch.html": {
        "source_category": "ISSUER_DISTRIBUTED_ANNOUNCEMENT",
        "expected_sha256": "2fdcf54c247b5c5a4232c6a5ea8beda8f38bcbc7c6197d18f44580e83193ff75",
        "expected_url": "https://www.globenewswire.com/news-release/2026/09/16/3363570/0/en/flow-neuroscience-launches-fl-100-in-the-us-the-first-fda-approved-at-home-tdcs-treatment-for-depression.html",
        "pattern": r"FL-100 is available in the United States from September 1, 2026",
        "bounded_assertion": "Manufacturer announcement asserts US availability from 2026-09-01",
    },
    "modius-fda-denovo.html": {
        "source_category": "REGULATOR_DE_NOVO",
        "expected_sha256": "d1f91d82897269ab1e17c93f4fc034152743a16792287c9e48706189587f80a4",
        "expected_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?id=DEN250013",
        "pattern": r"De Novo Number\s+DEN250013.*?Decision Date\s+05/08/2026\s+Decision granted\s+\(DENG\)",
        "bounded_assertion": "DEN250013 shows FDA decision granted 2026-05-08",
    },
}


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.ignored.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()

    def handle_data(self, text: str) -> None:
        if not self.ignored:
            self.parts.append(text)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_saved_temporal_statements(archive_path: Path) -> dict[str, Any]:
    """Fail on changed bytes, source misattribution or missing exact text claims."""
    source_bytes = archive_path.read_bytes()
    if _digest(source_bytes) != ARCHIVE_SHA256:
        raise ValueError("Original temporal archive digest does not match")
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Temporal artifact ZIP CRC mismatch")
        report = json.loads(archive.read("capture-report.json"))
        if len(report["captured"]) != 6 or report["failures"] or report["target_count"] != 6:
            raise ValueError("Unexpected bounded acquisition population")
        if report["world_time_cutoff"] != "2026-09-24" or report["knowledge_time_cutoff"] != "2026-10-24T23:59:59Z":
            raise ValueError("Frozen temporal research contract mismatch")
        by_file = {entry["raw_file_name"]: entry for entry in report["captured"]}
        if len(by_file) != 6:
            raise ValueError("Duplicate saved source response filename")
        for filename, metadata in by_file.items():
            if metadata["http_status"] != 200 or metadata["source_claims_adjudicated"] is not False:
                raise ValueError("Unsupported original response/adjudication status")
            if metadata["product_identity_or_currentness_resolved"] is not False:
                raise ValueError("Unreviewed source cannot assert product currentness")
            body = archive.read(filename)
            if _digest(body) != metadata["raw_sha256"] or len(body) != metadata["raw_bytes"]:
                raise ValueError("Saved source bytes differ from capture manifest")
        findings = []
        for filename, expected in REQUIRED.items():
            metadata = by_file[filename]
            if metadata["raw_sha256"] != expected["expected_sha256"] or metadata["final_url"] != expected["expected_url"]:
                raise ValueError(f"Required source identity/hash drift: {filename}")
            parser = _PlainText()
            parser.feed(archive.read(filename).decode("utf-8", errors="replace"))
            text = " ".join(" ".join(parser.parts).split())
            if re.search(expected["pattern"], text, flags=re.IGNORECASE | re.DOTALL) is None:
                raise ValueError(f"Expected original source statement absent: {filename}")
            findings.append(
                {
                    "original_saved_file": filename,
                    "source_category": expected["source_category"],
                    "source_sha256": metadata["raw_sha256"],
                    "captured_at_utc": metadata["knowledge_observed_at"],
                    "bounded_assertion": expected["bounded_assertion"],
                    "assertion_text_present_in_original_archive": True,
                    "historical_product_eligibility_adjudicated": False,
                }
            )
    return {
        "artifact_type": "RELEASE_A_TEMPORAL_ORIGINAL_BYTE_STATEMENT_REPLAY_v0.1",
        "status": "PASS_SAVED_BYTE_INTEGRITY_AND_NARROW_STATEMENT_PRESENCE",
        "original_archive_sha256": ARCHIVE_SHA256,
        "original_captured_sources_verified": 6,
        "narrow_source_statements_verified": findings,
        "terminal_temporal_reviews_approved": 0,
        "canonical_product_changes": 0,
        "boundary": (
            "An original FDA decision record and an issuer-distributed availability "
            "claim are different forms of evidence. None independently proves actual "
            "dispensing, Modius distribution, world-time product eligibility, "
            "a human temporal decision, or Release-A completion."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_saved_temporal_statements(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
