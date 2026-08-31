from __future__ import annotations

import socket
import threading
from dataclasses import dataclass, field
from typing import Any

import pytest

from neuroai_workbench.collector import CollectorConfig, PinnedSocketHttpTransport
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpClient, HttpRequest

GLOBAL_IP = "93.184.216.34"
SECOND_GLOBAL_IP = "8.8.8.8"


def global_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
    if host == "example.org":
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (SECOND_GLOBAL_IP, 0)),
        ]
    if host == "redirect.example.org":
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]
    raise socket.gaierror("unknown host")


@dataclass
class RecordingTransport:
    calls: list[HttpRequest] = field(default_factory=list)

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append(request)
        return 200, {"Content-Type": "application/json"}, b"{}"


def test_http_client_passes_exact_dns_validated_addresses_to_transport() -> None:
    transport = RecordingTransport()
    client = HttpClient(
        config=CollectorConfig(collector_version="test", configuration_hash="a" * 64),
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )
    response = client.fetch("https://example.org/source")
    assert response.status == 200
    assert len(transport.calls) == 1
    assert transport.calls[0].validated_addresses == (SECOND_GLOBAL_IP, GLOBAL_IP)
    assert tuple(response.dns_resolution.addresses) == (SECOND_GLOBAL_IP, GLOBAL_IP)


def test_http_client_refreshes_validated_addresses_for_redirect_hop() -> None:
    class RedirectTransport(RecordingTransport):
        def send(
            self,
            request: HttpRequest,
            *,
            connect_timeout: float,
            read_timeout: float,
        ) -> tuple[int, dict[str, str], bytes]:
            self.calls.append(request)
            if request.url == "https://example.org/start":
                return 302, {"Location": "https://redirect.example.org/final"}, b""
            return 200, {"Content-Type": "application/json"}, b"{}"

    transport = RedirectTransport()
    client = HttpClient(
        config=CollectorConfig(collector_version="test", configuration_hash="a" * 64),
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )
    client.fetch("https://example.org/start")
    assert [call.url for call in transport.calls] == [
        "https://example.org/start",
        "https://redirect.example.org/final",
    ]
    assert transport.calls[0].validated_addresses == (SECOND_GLOBAL_IP, GLOBAL_IP)
    assert transport.calls[1].validated_addresses == (GLOBAL_IP,)


class SocketPairServer:
    def __init__(self, response: bytes) -> None:
        self.client, self.server = socket.socketpair()
        self.response = response
        self.received = b""
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        chunks: list[bytes] = []
        self.server.settimeout(2.0)
        try:
            while True:
                chunk = self.server.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\r\n\r\n" in b"".join(chunks):
                    break
            self.received = b"".join(chunks)
            self.server.sendall(self.response)
        finally:
            self.server.close()

    def finish(self) -> bytes:
        self._thread.join(timeout=3.0)
        assert not self._thread.is_alive()
        return self.received


def _response(status: str = "200 OK", headers: tuple[tuple[str, str], ...] = (), body: bytes = b"ok") -> bytes:
    rows = [f"HTTP/1.1 {status}", f"Content-Length: {len(body)}"]
    rows.extend(f"{key}: {value}" for key, value in headers)
    return ("\r\n".join(rows) + "\r\n\r\n").encode("ascii") + body


def test_pinned_transport_refuses_missing_or_private_pins() -> None:
    transport = PinnedSocketHttpTransport()
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert exc.value.failure_class == "SSRF_BLOCKED"

    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, ("127.0.0.1",)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_http_transport_connects_to_pinned_ip_and_preserves_original_host_header() -> None:
    server = SocketPairServer(_response(headers=(("Content-Type", "text/plain"),), body=b"hello"))
    targets: list[tuple[str, int]] = []

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        targets.append(target)
        assert timeout == 1.5
        return server.client

    transport = PinnedSocketHttpTransport(socket_factory=socket_factory)
    status, headers, body = transport.send(
        HttpRequest(
            "GET",
            "http://example.org:8080/a/path?x=1",
            {"User-Agent": "test-agent"},
            (GLOBAL_IP,),
        ),
        connect_timeout=1.5,
        read_timeout=2.0,
    )
    received = server.finish().decode("iso-8859-1")
    assert targets == [(GLOBAL_IP, 8080)]
    assert "GET /a/path?x=1 HTTP/1.1\r\n" in received
    assert "Host: example.org:8080\r\n" in received
    assert "Connection: close\r\n" in received
    assert status == 200
    assert headers["Content-Type"] == "text/plain"
    assert body == b"hello"


def test_transport_retries_only_within_supplied_validated_address_set() -> None:
    server = SocketPairServer(_response(headers=(("Content-Type", "text/plain"),), body=b"retry-ok"))
    targets: list[tuple[str, int]] = []

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        targets.append(target)
        if target[0] == GLOBAL_IP:
            raise OSError("simulated first pinned address failure")
        assert target[0] == SECOND_GLOBAL_IP
        return server.client

    transport = PinnedSocketHttpTransport(socket_factory=socket_factory)
    status, _, body = transport.send(
        HttpRequest("GET", "http://example.org/retry", {}, (GLOBAL_IP, SECOND_GLOBAL_IP)),
        connect_timeout=1.0,
        read_timeout=1.0,
    )
    server.finish()
    assert targets == [(GLOBAL_IP, 80), (SECOND_GLOBAL_IP, 80)]
    assert status == 200
    assert body == b"retry-ok"


class RecordingSslContext:
    def __init__(self) -> None:
        self.server_names: list[str] = []

    def wrap_socket(self, sock: socket.socket, *, server_hostname: str) -> socket.socket:
        self.server_names.append(server_hostname)
        return sock


def test_https_transport_uses_original_hostname_for_sni() -> None:
    server = SocketPairServer(_response(headers=(("Content-Type", "application/json"),), body=b"{}"))
    targets: list[tuple[str, int]] = []
    ssl_context = RecordingSslContext()

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        targets.append(target)
        return server.client

    transport = PinnedSocketHttpTransport(socket_factory=socket_factory, ssl_context=ssl_context)
    status, _, body = transport.send(
        HttpRequest("GET", "https://example.org/study", {}, (GLOBAL_IP,)),
        connect_timeout=1.0,
        read_timeout=1.0,
    )
    received = server.finish().decode("iso-8859-1")
    assert targets == [(GLOBAL_IP, 443)]
    assert ssl_context.server_names == ["example.org"]
    assert "Host: example.org\r\n" in received
    assert status == 200
    assert body == b"{}"


def test_transport_returns_redirect_without_following_it() -> None:
    server = SocketPairServer(
        _response(
            status="302 Found",
            headers=(("Location", "https://other.example.org/next"),),
            body=b"",
        )
    )
    calls: list[tuple[str, int]] = []

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        calls.append(target)
        return server.client

    transport = PinnedSocketHttpTransport(socket_factory=socket_factory)
    status, headers, body = transport.send(
        HttpRequest("GET", "http://example.org/start", {}, (GLOBAL_IP,)),
        connect_timeout=1.0,
        read_timeout=1.0,
    )
    server.finish()
    assert calls == [(GLOBAL_IP, 80)]
    assert status == 302
    assert headers["Location"] == "https://other.example.org/next"
    assert body == b""


def test_transport_enforces_wire_size_before_returning_body() -> None:
    server = SocketPairServer(_response(body=b"123456"))

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        return server.client

    transport = PinnedSocketHttpTransport(max_wire_bytes=5, socket_factory=socket_factory)
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "http://example.org/large", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    server.finish()
    assert exc.value.failure_class == "SIZE_LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    ("request", "expected"),
    [
        (HttpRequest("GET", "http://example.org/a", {"X-Test": "ok\r\nInjected: yes"}, (GLOBAL_IP,)), "CR/LF"),
        (HttpRequest("GET\r\nBAD", "http://example.org/a", {}, (GLOBAL_IP,)), "CR/LF"),
        (HttpRequest("GET", "http://example.org/a", {"Host": "evil.example"}, (GLOBAL_IP,)), "override"),
    ],
)
def test_transport_rejects_header_method_injection_and_host_override(request: HttpRequest, expected: str) -> None:
    transport = PinnedSocketHttpTransport(socket_factory=lambda target, timeout: pytest.fail("socket must not be opened"))
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(request, connect_timeout=1.0, read_timeout=1.0)
    assert exc.value.failure_class == "NETWORK_ERROR"
    assert expected.lower() in str(exc.value).lower()
