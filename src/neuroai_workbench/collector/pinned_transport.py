from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import urllib3
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from .errors import CollectionFailureError
from .http_client import HttpRequest, TransportResponse
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


def _verified_peer_address(sock: Any, expected_address: str) -> str:
    """Verify the actual INET peer equals the selected DnsGuard-approved pin."""
    family = getattr(sock, "family", None)
    if family not in {socket.AF_INET, socket.AF_INET6}:
        # Test-only/custom socket fixtures such as socketpair() are not Internet
        # transports. Production `_default_socket_factory` always returns INET.
        return expected_address
    try:
        peer = sock.getpeername()
        raw_peer = peer[0]
        actual = str(ipaddress.ip_address(raw_peer))
    except (OSError, ValueError, TypeError, IndexError) as exc:
        raise CollectionFailureError("SSRF_BLOCKED", "Unable to verify connected transport peer") from exc
    expected = str(ipaddress.ip_address(expected_address))
    if actual != expected:
        raise CollectionFailureError(
            "SSRF_BLOCKED",
            f"Connected transport peer {actual!r} does not match validated address {expected!r}",
        )
    return actual


class _PinnedConnectionMixin:
    """Open only the already-selected numeric peer while retaining the logical origin."""

    _pinned_address: str
    _connect_timeout: float
    _socket_factory: SocketFactory
    connected_address: str | None
    port: int
    sock: socket.socket | Any | None

    def _configure_pin(
        self,
        *,
        pinned_address: str,
        timeout: float,
        socket_factory: SocketFactory,
    ) -> None:
        self._pinned_address = pinned_address
        self._connect_timeout = timeout
        self._socket_factory = socket_factory
        self.connected_address = None

    def _new_conn(self) -> socket.socket:
        raw_socket: socket.socket | Any | None = None
        try:
            raw_socket = self._socket_factory((self._pinned_address, self.port), self._connect_timeout)
            self.connected_address = _verified_peer_address(raw_socket, self._pinned_address)
            return raw_socket
        except BaseException:
            if raw_socket is not None:
                try:
                    raw_socket.close()
                except OSError:
                    pass
            raise


class _PinnedUrllib3HTTPConnection(_PinnedConnectionMixin, urllib3.connection.HTTPConnection):
    """Native urllib3 HTTP framing over one DnsGuard-selected numeric peer."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout: float,
        pinned_address: str,
        socket_factory: SocketFactory,
    ) -> None:
        super().__init__(host=host, port=port, timeout=timeout)
        self._configure_pin(
            pinned_address=pinned_address,
            timeout=timeout,
            socket_factory=socket_factory,
        )


class _PinnedUrllib3Connection(_PinnedConnectionMixin, urllib3.connection.HTTPSConnection):
    """Native urllib3 HTTPS/TLS semantics over one DnsGuard-selected numeric peer.

    Only TCP address selection is overridden. urllib3 owns the TLS handshake so
    ALPN, SNI, certificate validation, and other HTTPS connection semantics stay
    aligned with its standard hostname connection path.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout: float,
        pinned_address: str,
        socket_factory: SocketFactory,
        ssl_context: ssl.SSLContext | None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            timeout=timeout,
            ssl_context=ssl_context,
        )
        self._configure_pin(
            pinned_address=pinned_address,
            timeout=timeout,
            socket_factory=socket_factory,
        )


class PinnedSocketHttpTransport:
    """GET-only transport that connects only to DnsGuard-approved IP literals.

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
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        if max_wire_bytes <= 0:
            raise ValueError("max_wire_bytes must be positive")
        self.max_wire_bytes = max_wire_bytes
        self.socket_factory = socket_factory
        # Leave the production default unset so urllib3 constructs its own
        # hardened context exactly as on its standard HTTPS connection path.
        # Explicit contexts remain supported for controlled tests/callers.
        self.ssl_context = ssl_context

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> TransportResponse:
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
            explicit_port = parsed.port
        except ValueError as exc:
            raise CollectionFailureError("SSRF_BLOCKED", "HTTP URL contains an invalid port") from exc
        port = (443 if scheme == "https" else 80) if explicit_port is None else explicit_port
        if port < 1 or port > 65535:
            raise CollectionFailureError("SSRF_BLOCKED", f"HTTP URL port {port} is outside the allowed range")

        addresses = _validated_global_addresses(request.validated_addresses)
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        _reject_crlf(path, label="HTTP request target")

        headers: dict[str, str] = {}
        for key, value in request.headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise CollectionFailureError("NETWORK_ERROR", "HTTP header names and values must be strings")
            _reject_crlf(key, label="HTTP header name")
            _reject_crlf(value, label=f"HTTP header {key!r}")
            try:
                key.encode("iso-8859-1")
                value.encode("iso-8859-1")
            except UnicodeEncodeError as exc:
                raise CollectionFailureError(
                    "NETWORK_ERROR",
                    "HTTP request headers are not Latin-1 encodable",
                ) from exc
            if key.lower() in {"host", "connection"}:
                raise CollectionFailureError(
                    "NETWORK_ERROR",
                    f"Caller may not override transport-controlled header {key!r}",
                )
            headers[key] = value
        headers["Host"] = _host_header(network_hostname, scheme=scheme, port=port)
        headers["Connection"] = "close"

        last_error: OSError | None = None
        for address in addresses:
            connection: urllib3.connection.HTTPConnection | None = None
            response: urllib3.response.HTTPResponse | None = None
            try:
                if scheme == "https":
                    connection = _PinnedUrllib3Connection(
                        host=network_hostname,
                        port=port,
                        timeout=connect_timeout,
                        pinned_address=address,
                        socket_factory=self.socket_factory,
                        ssl_context=self.ssl_context,
                    )
                else:
                    connection = _PinnedUrllib3HTTPConnection(
                        host=network_hostname,
                        port=port,
                        timeout=connect_timeout,
                        pinned_address=address,
                        socket_factory=self.socket_factory,
                    )
                connection.connect()
                if connection.sock is None:
                    raise CollectionFailureError("NETWORK_ERROR", "Pinned transport did not establish a socket")
                connection.timeout = read_timeout
                connection.sock.settimeout(read_timeout)
                connection.request(
                    "GET",
                    path,
                    headers=headers,
                    preload_content=False,
                    decode_content=False,
                    enforce_content_length=False,
                )
                response = connection.getresponse()
                body = response.read(self.max_wire_bytes + 1, decode_content=False)
                if len(body) > self.max_wire_bytes:
                    raise CollectionFailureError(
                        "SIZE_LIMIT_EXCEEDED",
                        f"Raw HTTP response exceeds {self.max_wire_bytes}-byte transport limit",
                    )
                response_headers = {key: value for key, value in response.headers.items()}
                return TransportResponse(
                    status=int(response.status),
                    headers=response_headers,
                    body=body,
                    connected_address=getattr(connection, "connected_address", None),
                )
            except CollectionFailureError:
                raise
            except http.client.HTTPException as exc:
                raise CollectionFailureError("NETWORK_ERROR", f"Malformed HTTP response: {exc}") from exc
            except Urllib3HTTPError as exc:
                raise CollectionFailureError("NETWORK_ERROR", f"HTTP transport protocol error: {exc}") from exc
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
                if connection is not None:
                    try:
                        connection.close()
                    except OSError:
                        pass

        if last_error is not None:
            raise last_error
        raise CollectionFailureError("NETWORK_ERROR", "No validated address was available for transport")
