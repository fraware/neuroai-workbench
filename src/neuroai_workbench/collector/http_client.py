from __future__ import annotations

import gzip
import io
import zlib
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlparse

from .config import CollectorConfig
from .dns import DnsGuard, DnsResolutionRecord
from .errors import CollectionFailureError
from .url_policy import validate_public_url, validate_redirect_url

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    redirect_chain: tuple[str, ...]
    dns_resolution: DnsResolutionRecord


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]


class HttpTransport(Protocol):
    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        """Return status, headers, and raw body bytes."""


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def filename_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path or path.endswith("/"):
        return "index.html"
    name = path.rsplit("/", 1)[-1]
    return name or "index.html"


def _decompress_body(body: bytes, encoding: str, *, max_bytes: int, max_ratio: int) -> bytes:
    normalized = encoding.lower().strip()
    if normalized in {"", "identity"}:
        if len(body) > max_bytes:
            raise CollectionFailureError("SIZE_LIMIT_EXCEEDED", f"Response exceeds {max_bytes}-byte limit")
        return body
    if normalized == "gzip":
        compressed_size = len(body)
        if compressed_size == 0:
            return b""
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as handle:
                decompressed = handle.read(max_bytes + 1)
        except OSError as exc:
            raise CollectionFailureError("DECOMPRESSION_BOMB", "Failed to decompress gzip response") from exc
    elif normalized in {"deflate", "x-deflate"}:
        compressed_size = len(body)
        try:
            decompressor = zlib.decompressobj()
            decompressed = decompressor.decompress(body, max_bytes + 1)
        except zlib.error as exc:
            raise CollectionFailureError("DECOMPRESSION_BOMB", "Failed to decompress deflate response") from exc
    else:
        raise CollectionFailureError("CONTENT_TYPE_REJECTED", f"Unsupported content encoding {encoding!r}")

    if len(decompressed) > max_bytes:
        raise CollectionFailureError("SIZE_LIMIT_EXCEEDED", f"Decompressed response exceeds {max_bytes}-byte limit")
    if compressed_size > 0 and len(decompressed) / compressed_size > max_ratio:
        raise CollectionFailureError(
            "DECOMPRESSION_BOMB",
            f"Decompression ratio {len(decompressed) / compressed_size:.1f} exceeds limit {max_ratio}",
        )
    return decompressed


def _validate_media_type(media_type: str, allowed: frozenset[str]) -> None:
    primary = media_type.split(";", 1)[0].strip().lower()
    if primary not in allowed:
        raise CollectionFailureError("CONTENT_TYPE_REJECTED", f"Media type {primary!r} is not allowed")


class HttpClient:
    def __init__(
        self,
        *,
        config: CollectorConfig,
        transport: HttpTransport,
        dns_guard: DnsGuard | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self.dns_guard = dns_guard or DnsGuard()

    def fetch(
        self,
        url: str,
        *,
        conditional_headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        validate_public_url(url)
        # DNS-rebinding observations are meaningful inside one redirect chain.
        # A request-local session prevents concurrent independent fetches from
        # clearing or mutating each other's security state.
        dns_guard = self.dns_guard.new_session()
        redirect_chain: list[str] = []
        current_url = url
        last_dns: DnsResolutionRecord | None = None

        for _ in range(self.config.max_redirects + 1):
            last_dns = dns_guard.resolve(current_url)
            headers = {
                "User-Agent": self.config.user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
            if conditional_headers:
                headers.update(conditional_headers)

            try:
                status, response_headers, raw_body = self.transport.send(
                    HttpRequest("GET", current_url, headers),
                    connect_timeout=self.config.connect_timeout_seconds,
                    read_timeout=self.config.read_timeout_seconds,
                )
            except TimeoutError as exc:
                raise CollectionFailureError("TIMEOUT", "HTTP request timed out") from exc
            except OSError as exc:
                raise CollectionFailureError("NETWORK_ERROR", f"HTTP request failed: {exc}") from exc

            normalized_headers = _normalize_headers(response_headers)
            if status in REDIRECT_STATUSES:
                location = normalized_headers.get("location")
                if not location:
                    raise CollectionFailureError("REDIRECT_BLOCKED", "Redirect response missing Location header")
                next_url = urljoin(current_url, location)
                validate_redirect_url(next_url)
                redirect_chain.append(current_url)
                current_url = next_url
                continue

            if status == 304:
                if last_dns is None:
                    raise CollectionFailureError("NETWORK_ERROR", "Missing DNS resolution for not-modified response")
                return HttpResponse(
                    url=current_url,
                    status=304,
                    headers=normalized_headers,
                    body=b"",
                    redirect_chain=tuple(redirect_chain),
                    dns_resolution=last_dns,
                )

            if status < 200 or status >= 300:
                raise CollectionFailureError("HTTP_ERROR", f"Unexpected HTTP status {status}")

            encoding = normalized_headers.get("content-encoding", "identity")
            body = _decompress_body(
                raw_body,
                encoding,
                max_bytes=self.config.max_response_bytes,
                max_ratio=self.config.max_decompression_ratio,
            )
            media_type = normalized_headers.get("content-type", "application/octet-stream")
            _validate_media_type(media_type, self.config.allowed_content_types)
            if last_dns is None:
                raise CollectionFailureError("NETWORK_ERROR", "Missing DNS resolution for successful response")
            return HttpResponse(
                url=current_url,
                status=status,
                headers=normalized_headers,
                body=body,
                redirect_chain=tuple(redirect_chain),
                dns_resolution=last_dns,
            )

        raise CollectionFailureError("REDIRECT_BLOCKED", f"Redirect chain exceeded {self.config.max_redirects} hops")
