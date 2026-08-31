from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .errors import CollectionFailureError
from .http_client import HttpRequest
from .url_policy import validate_public_url

SocketFactory = Callable[[tuple[str, int], float], socket.socket]


def _default_socket_factory(address: tuple[str, int], timeout: float) -> socket.socket:
    """Connect directly to one numeric IP literal without invoking a resolver path."""
    host, port = address
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise OSError(f"Pinned socket target is not an IP literal: {host!r}") from exc
    family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        target: Any = (str(ip), port, 0, 0) if ip.version == 6 else (str(ip), port)
        sock.connect(target)
        return sock
    except BaseException:
        sock.close()
        raise


def _reject_crlf(value: str, *, label: str) -> None:
    if "\r" in value or "\n" in value:
        raise CollectionFailureError("NETWORK_ERROR", f"{label} contains prohibited CR/LF characters")


def _validated_global_addresses(values: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        raise CollectionFailureError(
            "SSRF_BLOCKED",
            "Production HTTP transport requires a non-empty DNS-validated address set",
        )
    normalized: list[str] = []
    for raw in values:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise CollectionFailureError("SSRF_BLOCKED", f"Validated address is not an IP literal: {raw!r}") from exc
        if not ip.is_global:
            raise CollectionFailureError(
                "SSRF_BLOCKED",
                f"Validated transport address {raw!r} is not globally routable",
            )
        normalized.append(str(ip))
    return tuple(dict.fromkeys(normalized))


def _network_hostname(hostname: str) -> str:
    """Return the ASCII identity used for HTTP Host and TLS SNI/certificate validation."""
    normalized = hostname.rstrip(".")
    try:
        return str(ipaddress.ip_address(normalized))
    except ValueError:
        try:
            return normalized.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise CollectionFailureError("SSRF_BLOCKED", "HTTP hostname cannot be normalized with IDNA") from exc


def _host_header(hostname: str, *, scheme: str, port: int) -> str:
    host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    return host if port == default_port else f"{host}:{port}"


class PinnedSocketHttpTransport:
    """GET-only HTTP/1.1 transport that connects only to DnsGuard-approved IP literals.

    The URL hostname is normalized and retained for the HTTP Host header and HTTPS
    SNI/certificate hostname validation. Redirects are deliberately not followed;
    `HttpClient` owns redirect validation and performs a fresh DNS-guard step for
    each accepted redirect hop.
    """

    def __init__(
        self,
        *,
        max_wire_bytes: int = 10 * 1024 * 1024,
        socket_factory: SocketFactory = _default_socket_factory,
        ssl_context: Any | None = None,
    ) -> None:
        if max_wire_bytes <= 0:
            raise ValueError("max_wire_bytes must be positive")
        self.max_wire_bytes = max_wire_bytes
        self.socket_factory = socket_factory
        self.ssl_context = ssl_context or ssl.create_default_context()

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        validate_public_url(request.url)
        _reject_crlf(request.method, label="HTTP method")
        if request.method != "GET":
            raise CollectionFailureError("NETWORK_ERROR", "Production collector transport permits GET only")

        parsed = urlsplit(request.url)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            raise CollectionFailureError("SSRF_BLOCKED", f"Unsupported HTTP scheme {scheme!r}")
        hostname = parsed.hostname
        if not hostname:
            raise CollectionFailureError("SSRF_BLOCKED", "HTTP URL is missing a hostname")
        network_hostname = _network_hostname(hostname)
        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise CollectionFailureError("SSRF_BLOCKED", "HTTP URL contains an invalid port") from exc

        addresses = _validated_global_addresses(request.validated_addresses)
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        _reject_crlf(path, label="HTTP request target")

        headers: dict[str, str] = {}
        for key, value in request.headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise CollectionFailureError("NETWORK_ERROR", "HTTP header names and values must be strings")
            _reject_crlf(key, label="HTTP header name")
            _reject_crlf(value, label=f"HTTP header {key!r}")
            if key.lower() in {"host", "connection"}:
                raise CollectionFailureError(
                    "NETWORK_ERROR",
                    f"Caller may not override transport-controlled header {key!r}",
                )
            headers[key] = value
        headers["Host"] = _host_header(network_hostname, scheme=scheme, port=port)
        headers["Connection"] = "close"

        request_lines = [f"GET {path} HTTP/1.1"]
        request_lines.extend(f"{key}: {value}" for key, value in headers.items())
        request_text = "\r\n".join(request_lines) + "\r\n\r\n"
        try:
            request_bytes = request_text.encode("iso-8859-1")
        except UnicodeEncodeError as exc:
            raise CollectionFailureError("NETWORK_ERROR", "HTTP request headers are not Latin-1 encodable") from exc

        last_error: OSError | None = None
        for address in addresses:
            raw_socket: socket.socket | Any | None = None
            stream: socket.socket | Any | None = None
            response: http.client.HTTPResponse | None = None
            try:
                raw_socket = self.socket_factory((address, port), connect_timeout)
                raw_socket.settimeout(read_timeout)
                stream = raw_socket
                if scheme == "https":
                    stream = self.ssl_context.wrap_socket(raw_socket, server_hostname=network_hostname)
                    stream.settimeout(read_timeout)
                stream.sendall(request_bytes)
                response = http.client.HTTPResponse(stream)
                response.begin()
                body = response.read(self.max_wire_bytes + 1)
                if len(body) > self.max_wire_bytes:
                    raise CollectionFailureError(
                        "SIZE_LIMIT_EXCEEDED",
                        f"Raw HTTP response exceeds {self.max_wire_bytes}-byte transport limit",
                    )
                response_headers = {key: value for key, value in response.getheaders()}
                return int(response.status), response_headers, body
            except CollectionFailureError:
                raise
            except http.client.HTTPException as exc:
                raise CollectionFailureError("NETWORK_ERROR", f"Malformed HTTP response: {exc}") from exc
            except TimeoutError:
                raise
            except OSError as exc:
                last_error = exc
                continue
            finally:
                if response is not None:
                    try:
                        response.close()
                    except OSError:
                        pass
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
                elif raw_socket is not None:
                    try:
                        raw_socket.close()
                    except OSError:
                        pass

        if last_error is not None:
            raise last_error
        raise CollectionFailureError("NETWORK_ERROR", "No validated address was available for transport")
