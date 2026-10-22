"""Pure synthetic checks for source digest receipts without live network."""

from __future__ import annotations

import hashlib
import urllib.error
from unittest.mock import MagicMock

import pytest

from scripts import r1_7_neo_public_http_receipts as receipt


class FakeResponse:
    def __init__(self, *, url: str, body: bytes, status: int = 200) -> None:
        self.url = url
        self.body = body
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        return self.body[:size] if size >= 0 else self.body


def test_three_original_source_hosts_are_explicit_and_https() -> None:
    assert {s["source_id"] for s in receipt.PUBLIC_SOURCES} == {
        "NEO-NMPA-20260313",
        "NEO-SHANGHAI-20260313",
        "NEO-NHSA-20260322",
    }
    assert all(s["url"].startswith("https://") for s in receipt.PUBLIC_SOURCES)


def test_digest_receipt_has_exact_bytes_and_no_public_html_body() -> None:
    source = receipt.PUBLIC_SOURCES[0]
    body = b"<html><body>synthetic BCI response only</body></html>"
    opener = lambda _request, timeout: FakeResponse(url=source["url"], body=body)
    result = receipt.inspect_source(source, opener=opener)
    assert result["acquisition_state"] == "HTTP_200_DIGEST_ONLY_RAW_BYTES_NOT_RETAINED"
    assert result["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert result["response_bytes"] == len(body)
    assert result["product_or_source_adjudication"] is False
    assert result["source_body_persisted"] is False
    assert body.decode() not in str(result)


def test_different_final_origin_is_not_credited() -> None:
    source = receipt.PUBLIC_SOURCES[0]
    opener = lambda _request, timeout: FakeResponse(url="https://untrusted.example/redirect", body=b"bad")
    result = receipt.inspect_source(source, opener=opener)
    assert result["acquisition_state"] == "UNTRUSTED_ORIGIN_REDIRECT"
    assert "response_sha256" not in result


def test_oversized_body_does_not_publish_truncated_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    source = receipt.PUBLIC_SOURCES[0]
    monkeypatch.setattr(receipt, "MAX_BYTES", 64)
    opener = lambda _request, timeout: FakeResponse(url=source["url"], body=b"x" * 80)
    result = receipt.inspect_source(source, opener=opener)
    assert result["acquisition_state"] == "OVER_MAX_CAPTURE_BYTES"
    assert "response_sha256" not in result


def test_http403_and_dns_failures_are_not_empty_source_claims() -> None:
    source = receipt.PUBLIC_SOURCES[0]

    def forbidden(_request: object, timeout: int) -> None:
        raise urllib.error.HTTPError(source["url"], 403, "Forbidden", None, None)

    def offline(_request: object, timeout: int) -> None:
        raise urllib.error.URLError("unavailable")

    assert receipt.inspect_source(source, opener=forbidden)["acquisition_state"] == (
        "HTTP_ERROR_NOT_SOURCE_ABSENCE"
    )
    assert receipt.inspect_source(source, opener=offline)["acquisition_state"] == (
        "NETWORK_FAILURE_NOT_SOURCE_ABSENCE"
    )


def test_unapproved_request_hostname_refused_before_fetch() -> None:
    source = {**receipt.PUBLIC_SOURCES[0], "url": "https://different.example/document"}
    opener = MagicMock()
    with pytest.raises(ValueError, match="host mismatch"):
        receipt.inspect_source(source, opener=opener)
    opener.assert_not_called()
