"""Opt-in, bounded, nonterminal capture of public R1.7 temporal/source URLs."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_TARGETS: tuple[tuple[str, str, str], ...] = (
    (
        "flow-fda-pma",
        "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P230024",
        "P230024",
    ),
    (
        "flow-september-launch",
        "https://www.globenewswire.com/news-release/2026/09/16/3363570/0/en/flow-neuroscience-launches-fl-100-in-the-us-the-first-fda-approved-at-home-tdcs-treatment-for-depression.html",
        "FL-100",
    ),
    (
        "modius-fda-denovo",
        "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?id=DEN250013",
        "DEN250013",
    ),
    (
        "neu-2025-discontinuation",
        "https://neu-brains.co.jp/information/press/2025/06/04/4258.html",
        "HOT-2000-BIOSIGNALS",
    ),
    (
        "bitbrain-spanish-diadem",
        "https://www.bitbrain.com/es/productos-neurotecnologia/dry-eeg/diadem",
        "Diadem",
    ),
    (
        "bitbrain-english-diadem",
        "https://www.bitbrain.com/neurotechnology-products/dry-eeg/diadem",
        "Diadem",
    ),
)
MAX_BYTES = 3 * 1024 * 1024


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> urllib.request.Request | None:
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if new.scheme != "https" or old.hostname != new.hostname:
            raise ValueError("External or non-HTTPS redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def capture_target(slug: str, locator: str, marker: str, output: Path) -> dict[str, Any]:
    if slug not in {target[0] for target in SOURCE_TARGETS}:
        raise ValueError("Unknown source target")
    if not any((slug, locator, marker) == target for target in SOURCE_TARGETS):
        raise ValueError("Source URL or expected marker differs from the explicit allowlist")
    request = urllib.request.Request(
        locator,
        method="GET",
        headers={
            "User-Agent": "NeuroAI-R17-Public-Source-Capture/0.1",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        },
    )
    opener = urllib.request.build_opener(SameOriginRedirect)
    with opener.open(request, timeout=22) as response:
        raw = response.read(MAX_BYTES + 1)
        status = response.status
        final_locator = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        headers = {
            "date": response.headers.get("Date"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }
    if status != 200 or len(raw) < 500 or len(raw) > MAX_BYTES:
        raise ValueError("HTTP status or response byte count outside acceptable bounds")
    if "html" not in content_type.lower():
        raise ValueError("Response is not HTML")
    if marker.casefold().encode("utf-8") not in raw.lower():
        raise ValueError("Returned HTML omits source-specific identifying text marker")
    observed = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(raw).hexdigest()
    output.joinpath(f"{slug}.html").write_bytes(raw)
    return {
        "slug": slug,
        "requested_url": locator,
        "final_url": final_locator,
        "http_status": status,
        "content_type": content_type,
        "headers": headers,
        "raw_file_name": f"{slug}.html",
        "raw_sha256": digest,
        "raw_bytes": len(raw),
        "knowledge_observed_at": observed,
        "retrieval_status": "RAW_PUBLIC_HTML_SAVED_PENDING_CLAIM_VALIDATION",
        "source_claims_adjudicated": False,
        "product_identity_or_currentness_resolved": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_network:
        parser.error("Network use requires --allow-network")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "artifact_type": "R1_7_TEMPORAL_EXTERNAL_HTTP_CAPTURE_v0.1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "target_count": len(SOURCE_TARGETS),
        "captured": [],
        "failures": [],
        "boundary": "Saved public HTTP bytes only; no terminal science or product status assigned",
    }
    for slug, locator, marker in SOURCE_TARGETS:
        try:
            report["captured"].append(capture_target(slug, locator, marker, args.output_dir))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            report["failures"].append({"slug": slug, "error_type": type(exc).__name__, "error": str(exc)[:240]})
    report["status"] = "COMPLETE_CAPTURE" if not report["failures"] else "PARTIAL_CAPTURE"
    args.output_dir.joinpath("capture-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
