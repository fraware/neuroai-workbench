"""Verify saved F8 HTTP responses and extract bounded source HTML metadata.

Requires the original artifact 12325963314 ZIP, stored outside public Git.
No HTTP requests, source adjudications, historical rewrites or product credits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZipFile

EXPECTED_ARCHIVE_SHA256 = "9d32393e10ef1f7ab2991b72a04e2ba2e6d415837750d3b639dd48332fc08dd2"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.language: str | None = None
        self.title: list[str] = []
        self.heading: list[str] = []
        self._active: str | None = None
        self.dates: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.language = a.get("lang")
        if tag in {"title", "h1"}:
            self._active = tag
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and key.lower() in {"pubdate", "article:published_time", "article:modified_time"}:
                self.dates[key] = a.get("content")

    def handle_endtag(self, tag: str) -> None:
        if self._active == tag:
            self._active = None

    def handle_data(self, content: str) -> None:
        if self._active == "title":
            self.title.append(content)
        elif self._active == "h1":
            self.heading.append(content)


def _compact(parts: list[str]) -> str | None:
    value = " ".join(" ".join(parts).split())
    return value[:180] if value else None


def audit_archive(path: Path) -> dict[str, object]:
    archive_bytes = path.read_bytes()
    if digest(archive_bytes) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("F8 acquisition archive raw-byte SHA-256 mismatch")
    records: list[dict[str, object]] = []
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("F8 archive ZIP integrity failure")
        manifest = json.loads(archive.read("attempt-report.json"))
        if manifest["attempts"] != 10 or len(manifest["items"]) != 10:
            raise ValueError("Original ten F8 URL attempts changed")
        for source in manifest["items"]:
            if source["original_frozen_outcome"] != "FAILED_INACCESSIBLE":
                raise ValueError("Historical frozen F8 outcome changed")
            if source["historical_product_claim_adjudicated"] is not False:
                raise ValueError("Unsupported historical product adjudication")
            if source["r1_7_terminal_extraction"] is not None:
                raise ValueError("Unsupported terminal source decision")
            item: dict[str, object] = {
                "frozen_query_id": source["frozen_query_id"],
                "capture_id": source["capture_id"],
                "alternative_locator": source["attempted_alternative_locator"],
                "attempted_at_utc": source["attempted_at_utc"],
                "source_locator_type": source["source_locator_type"],
                "reported_http_status": source.get("http_status"),
                "original_frozen_outcome": source["original_frozen_outcome"],
            }
            if source.get("http_status") == 200:
                body = archive.read(source["saved_file"])
                if len(body) != source["raw_bytes"] or digest(body) != source["raw_sha256"]:
                    raise ValueError("Saved F8 response digest or length mismatch")
                parser = _MetadataParser()
                parser.feed(body.decode("utf-8", errors="replace"))
                item.update(
                    {
                        "saved_file": source["saved_file"],
                        "raw_response_bytes": len(body),
                        "raw_sha256": digest(body),
                        "unverified_declared_html_lang": parser.language,
                        "unverified_html_title": _compact(parser.title),
                        "unverified_first_h1": _compact(parser.heading),
                        "unverified_date_meta": parser.dates,
                    }
                )
            else:
                if (
                    source.get("failure_type") != "HTTPError"
                    or source.get("failure_detail") != "HTTP Error 403: Forbidden"
                    or source.get("saved_file") is not None
                ):
                    raise ValueError("Unexpected F8 acquisition failure outcome")
                item["http_403_derived_from_exception_text"] = True
            records.append(item)

    successes = [row for row in records if row["reported_http_status"] == 200]
    failures = [row for row in records if row["reported_http_status"] is None]
    if len(successes) != 8 or len(failures) != 2:
        raise ValueError("Historical F8 retrieval-success counts changed")
    if len({row["raw_sha256"] for row in successes}) != 7:
        raise ValueError("Historical F8 unique-source-content count changed")
    if len({row["capture_id"] for row in records}) != 5:
        raise ValueError("Frozen F8 capture-context population changed")
    return {
        "report_id": "RELEASE_A_R1_7_F8_SAVED_HTML_METADATA_AUDIT_v0.1",
        "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "attempted_urls": len(records),
        "saved_successful_http_200": len(successes),
        "http_403_errors_in_recorded_exception_text": len(failures),
        "unique_saved_response_sha256": 7,
        "distinct_original_capture_contexts": 5,
        "source_metadata": records,
        "scientific_disposition": "NONTERMINAL_OFFLINE_METADATA_EXTRACTION",
        "authority_boundary": (
            "Exact archive/source bytes and unverified HTML metadata only. "
            "HTML lang or date meta is not validated language, historical "
            "product distribution, regulatory approval, device inclusion, "
            "complete search results or terminal R1.7 decision."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("F8: 10 alternatives, 8 saved HTTP 200, 2 HTTPError 403; 0 terminal decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
