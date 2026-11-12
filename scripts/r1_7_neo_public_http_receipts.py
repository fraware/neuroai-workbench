"""Bounded independent HTTP response digest receipts for public Chinese BCI sources.

No raw third-party HTML is saved or committed. Successful responses receive
raw-byte SHA-256/length metadata, with the original URL, final host, HTTP
status and capture timestamp. Failures remain explicit, never silently
counted as absent evidence or completed R1.7 review decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
TIMEOUT_SECONDS = 12
PUBLIC_SOURCES = (
    {
        "source_id": "NEO-NMPA-20260313",
        "url": "https://www.nmpa.gov.cn/directory/web/nmpa/zhuanti/zt2023/ypgzhlfzh/shypqxgg/ggjzcx/20260313134742156.html",
        "allowed_hostname": "www.nmpa.gov.cn",
    },
    {
        "source_id": "NEO-SHANGHAI-20260313",
        "url": "https://yjj.sh.gov.cn/sjdt/20260313/274e66190b4a4fb8996b4d62334b1a6d.html",
        "allowed_hostname": "yjj.sh.gov.cn",
    },
    {
        "source_id": "NEO-NHSA-20260322",
        "url": "https://www.nhsa.gov.cn/art/2026/3/22/art_14_19989.html",
        "allowed_hostname": "www.nhsa.gov.cn",
    },
    {
        "source_id": "NEO-SHANGHAI-CLINICAL-AUG2026",
        "url": "https://www.shanghai.gov.cn/zfkfmtbd/20260811/491d88b8b2454f47972e80154a02943b.html",
        "allowed_hostname": "www.shanghai.gov.cn",
    },
    {
        "source_id": "NEO-SHANGHAI-JULY-IMPLANT",
        "url": "https://touch.shio.gov.cn/jsp/jjxw_detail.jsp?id=20260716193634365",
        "allowed_hostname": "touch.shio.gov.cn",
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Reject cross-host/scheme HTTP redirection before following it."""

    def __init__(self, allowed_hostname: str) -> None:
        self.allowed_hostname = allowed_hostname

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if urlsplit(newurl).scheme != "https" or urlsplit(newurl).hostname != self.allowed_hostname:
            raise urllib.error.URLError("Redirect outside approved HTTPS origin")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def inspect_source(source: dict[str, str], *, opener: Any = None) -> dict[str, Any]:
    """Read exactly one fixed HTTPS public source, returning metadata only."""
    url = source["url"]
    allowed_host = source["allowed_hostname"]
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname != allowed_host:
        raise ValueError("Source host mismatch before HTTP request")
    opener = urllib.request.build_opener(_SameOriginRedirect(allowed_host)).open if opener is None else opener
    receipt: dict[str, Any] = {
        "source_id": source["source_id"],
        "requested_url": url,
        "observed_at_utc": _utc_now(),
        "source_body_persisted": False,
        "product_or_source_adjudication": False,
        "http_status": None,
    }
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NeuroAI-Landscape-Research/0.1 (source-integrity inspection)"},
        method="GET",
    )
    try:
        with opener(req, timeout=TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            receipt["final_url"] = final_url
            if urlsplit(final_url).scheme != "https" or urlsplit(final_url).hostname != allowed_host:
                receipt["acquisition_state"] = "UNTRUSTED_ORIGIN_REDIRECT"
                return receipt
            status = int(response.getcode())
            receipt["http_status"] = status
            if status != 200:
                receipt["acquisition_state"] = "NON_200_HTTP_RESPONSE"
                return receipt
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                receipt["acquisition_state"] = "OVER_MAX_CAPTURE_BYTES"
                return receipt
            receipt["response_bytes"] = len(raw)
            receipt["response_sha256"] = hashlib.sha256(raw).hexdigest()
            receipt["content_type"] = response.headers.get("Content-Type")
            receipt["last_modified_header"] = response.headers.get("Last-Modified")
            receipt["acquisition_state"] = "HTTP_200_DIGEST_ONLY_RAW_BYTES_NOT_RETAINED"
    except urllib.error.HTTPError as exc:
        receipt["http_status"] = exc.code
        receipt["acquisition_state"] = "HTTP_ERROR_NOT_SOURCE_ABSENCE"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        receipt["acquisition_state"] = "NETWORK_FAILURE_NOT_SOURCE_ABSENCE"
        receipt["failure_type"] = type(exc).__name__
    return receipt


def capture_sources() -> dict[str, Any]:
    receipts = [inspect_source(source) for source in PUBLIC_SOURCES]
    return {
        "artifact_type": "RELEASE_A_R1_7_NEO_PUBLIC_HTTP_DIGEST_RECEIPTS_v0.1",
        "captured_at_utc": _utc_now(),
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "source_count": len(PUBLIC_SOURCES),
        "http_200_digest_count": sum(
            row["acquisition_state"] == "HTTP_200_DIGEST_ONLY_RAW_BYTES_NOT_RETAINED" for row in receipts
        ),
        "receipts": receipts,
        "terminal_source_decisions": 0,
        "new_canonical_products": 0,
        "license_boundary": (
            "Captures public response metadata only. Original page bytes are "
            "not retained or redistributed; hashes cannot replay absent bytes."
        ),
        "scientific_boundary": (
            "Live retrieval does not validate source assertions, original "
            "query search completeness, historical world-time availability, "
            "regulatory device-level identity or human product eligibility."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = capture_sources()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"NEO HTTP receipts: {report['http_200_digest_count']}/{report['source_count']} saved digests; no raw pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
