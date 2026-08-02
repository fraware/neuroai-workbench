from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..util import atomic_write_json, safe_join, sha256_bytes, utc_now
from .boundary import COLLECTOR_BOUNDARY
from .config import CollectorConfig
from .errors import CollectionFailureError
from .http_client import HttpClient, HttpResponse, HttpTransport, filename_from_url
from .ids import new_failure_id, new_result_id
from .quarantine import build_quarantine_record, persist_quarantine_record, write_quarantine_bytes
from .rate_limit import RateLimiter
from .schemas import FAILURE_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA, validate_or_raise


@dataclass(frozen=True)
class PriorCapture:
    etag: str | None = None
    last_modified: str | None = None
    content_sha256: str = ""
    quarantine_path: str = ""
    size_bytes: int = 0
    media_type: str = "application/octet-stream"
    original_filename: str = "index.html"


@dataclass(frozen=True)
class CollectionOutcome:
    kind: str
    record: dict[str, Any]


def _normalize_timestamp(value: str | None = None) -> str:
    raw = value or utc_now()
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include an explicit timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _quarantine_object_path(source_id: str, content_sha256: str, filename: str) -> str:
    return f"incoming/{source_id}/{content_sha256[:12]}/{filename}"


class HttpCollector:
    def __init__(
        self,
        *,
        config: CollectorConfig,
        transport: HttpTransport,
        quarantine_root: Path,
    ) -> None:
        self.config = config
        self.http_client = HttpClient(config=config, transport=transport)
        self.quarantine_root = quarantine_root
        self.rate_limiter = RateLimiter(config.requests_per_host_per_minute)

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        validate_or_raise(request, REQUEST_SCHEMA)
        try:
            self.rate_limiter.check(str(request["requested_url"]))
        except ValueError as exc:
            return CollectionOutcome(
                kind="failure",
                record=self._build_failure(
                    request,
                    CollectionFailureError("UNKNOWN", str(exc)),
                    attempt_count=attempt_count,
                ),
            )

        conditional_headers: dict[str, str] = {}
        if prior_capture is not None:
            if prior_capture.etag:
                conditional_headers["If-None-Match"] = prior_capture.etag
            if prior_capture.last_modified:
                conditional_headers["If-Modified-Since"] = prior_capture.last_modified

        try:
            response = self.http_client.fetch(
                str(request["requested_url"]),
                conditional_headers=conditional_headers or None,
            )
        except CollectionFailureError as exc:
            return CollectionOutcome(
                kind="failure",
                record=self._build_failure(request, exc, attempt_count=attempt_count),
            )
        except ValueError as exc:
            return CollectionOutcome(
                kind="failure",
                record=self._build_failure(
                    request,
                    CollectionFailureError("UNKNOWN", str(exc)),
                    attempt_count=attempt_count,
                ),
            )

        retrieved_at = _normalize_timestamp()
        if response.status == 304:
            if prior_capture is None or not prior_capture.content_sha256:
                return CollectionOutcome(
                    kind="failure",
                    record=self._build_failure(
                        request,
                        CollectionFailureError("HTTP_ERROR", "HTTP 304 received without prior capture context"),
                        attempt_count=attempt_count,
                    ),
                )
            result = self._build_not_modified_result(request, response, prior_capture, retrieved_at)
            quarantine_record = build_quarantine_record(
                result_id=result["result_id"],
                source_id=str(request["source_id"]),
                monitor_id=str(request["monitor_id"]),
                captured_at=retrieved_at,
                content_sha256=prior_capture.content_sha256,
                size_bytes=prior_capture.size_bytes,
                original_filename=prior_capture.original_filename,
                quarantine_path=prior_capture.quarantine_path,
                collector_version=self.config.collector_version,
                configuration_hash=self.config.configuration_hash,
            )
            persist_quarantine_record(self.quarantine_root, quarantine_record)
            atomic_write_json(
                safe_join(self.quarantine_root, "results", f"{result['result_id']}.json"),
                result,
            )
            return CollectionOutcome(kind="result", record=result)

        content_sha256 = sha256_bytes(response.body)
        original_filename = filename_from_url(response.url)
        quarantine_path = _quarantine_object_path(str(request["source_id"]), content_sha256, original_filename)
        write_quarantine_bytes(self.quarantine_root, quarantine_path, response.body)

        media_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
        result = {
            "result_id": new_result_id(),
            "request_id": request["request_id"],
            "source_id": request["source_id"],
            "monitor_id": request["monitor_id"],
            "requested_url": request["requested_url"],
            "final_url": response.url,
            "redirect_chain": list(response.redirect_chain),
            "retrieved_at": retrieved_at,
            "http_status": response.status,
            "media_type": media_type,
            "size_bytes": len(response.body),
            "sha256": content_sha256,
            "original_filename": original_filename,
            "quarantine_path": quarantine_path,
            "dns_resolution": {
                "resolved_at": response.dns_resolution.resolved_at,
                "addresses": response.dns_resolution.addresses,
                "rebinding_check": response.dns_resolution.rebinding_check,
            },
            "collector_version": self.config.collector_version,
            "configuration_hash": self.config.configuration_hash,
            "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            "boundary": COLLECTOR_BOUNDARY,
        }
        validate_or_raise(result, RESULT_SCHEMA)
        quarantine_record = build_quarantine_record(
            result_id=result["result_id"],
            source_id=str(request["source_id"]),
            monitor_id=str(request["monitor_id"]),
            captured_at=retrieved_at,
            content_sha256=content_sha256,
            size_bytes=len(response.body),
            original_filename=original_filename,
            quarantine_path=quarantine_path,
            collector_version=self.config.collector_version,
            configuration_hash=self.config.configuration_hash,
        )
        persist_quarantine_record(self.quarantine_root, quarantine_record)
        atomic_write_json(
            safe_join(self.quarantine_root, "results", f"{result['result_id']}.json"),
            result,
        )
        return CollectionOutcome(kind="result", record=result)

    def _build_not_modified_result(
        self,
        request: dict[str, Any],
        response: HttpResponse,
        prior_capture: PriorCapture,
        retrieved_at: str,
    ) -> dict[str, Any]:
        result = {
            "result_id": new_result_id(),
            "request_id": request["request_id"],
            "source_id": request["source_id"],
            "monitor_id": request["monitor_id"],
            "requested_url": request["requested_url"],
            "final_url": response.url,
            "redirect_chain": list(response.redirect_chain),
            "retrieved_at": retrieved_at,
            "http_status": 304,
            "media_type": prior_capture.media_type,
            "size_bytes": prior_capture.size_bytes,
            "sha256": prior_capture.content_sha256,
            "original_filename": prior_capture.original_filename,
            "quarantine_path": prior_capture.quarantine_path,
            "dns_resolution": {
                "resolved_at": response.dns_resolution.resolved_at,
                "addresses": response.dns_resolution.addresses,
                "rebinding_check": response.dns_resolution.rebinding_check,
            },
            "collector_version": self.config.collector_version,
            "configuration_hash": self.config.configuration_hash,
            "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            "boundary": COLLECTOR_BOUNDARY,
        }
        validate_or_raise(result, RESULT_SCHEMA)
        return result

    def _build_failure(
        self,
        request: dict[str, Any],
        error: CollectionFailureError,
        *,
        attempt_count: int,
    ) -> dict[str, Any]:
        failed_at = _normalize_timestamp()
        exhausted = attempt_count >= self.config.max_attempts
        next_retry_at = (
            None
            if exhausted
            else (datetime.fromisoformat(failed_at.replace("Z", "+00:00")) + timedelta(minutes=5))
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        record = {
            "failure_id": new_failure_id(),
            "request_id": request["request_id"],
            "source_id": request["source_id"],
            "monitor_id": request["monitor_id"],
            "requested_url": request["requested_url"],
            "failed_at": failed_at,
            "failure_class": error.failure_class,
            "failure_message": error.message,
            "retry_state": {
                "attempt_count": attempt_count,
                "max_attempts": self.config.max_attempts,
                "next_retry_at": next_retry_at,
                "exhausted": exhausted,
            },
            "collector_version": self.config.collector_version,
            "configuration_hash": self.config.configuration_hash,
            "boundary": COLLECTOR_BOUNDARY,
        }
        validate_or_raise(record, FAILURE_SCHEMA)
        atomic_write_json(
            safe_join(self.quarantine_root, "failures", f"{record['failure_id']}.json"),
            record,
        )
        return record
