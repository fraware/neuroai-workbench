from __future__ import annotations

import socket
import threading

import pytest

from neuroai_workbench.collector import PinnedSocketHttpTransport
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest

GLOBAL_IP = "93.184.216.34"


class RecordingSslContext:
    def __init__(self) -> None:
        self.server_names: list[str] = []

    def wrap_socket(self, sock: socket.socket, *, server_hostname: str) -> socket.socket:
        self.server_names.append(server_hostname)
        return sock


def _socket_server(response: bytes) -> tuple[socket.socket, threading.Thread, dict[str, bytes]]:
    client, server = socket.socketpair()
    state: dict[str, bytes] = {"request": b""}

    def serve() -> None:
        chunks: list[bytes] = []
        server.settimeout(2.0)
        try:
            while True:
                chunk = server.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\r\n\r\n" in b"".join(chunks):
                    break
            state["request"] = b"".join(chunks)
            server.sendall(response)
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return client, thread, state


def test_production_transport_is_get_only() -> None:
    transport = PinnedSocketHttpTransport(
        socket_factory=lambda target, timeout: pytest.fail("non-GET request must not open a socket")
    )
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("POST", "https://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert exc.value.failure_class == "NETWORK_ERROR"
    assert "GET only" in str(exc.value)


def test_unicode_hostname_is_idna_normalized_for_host_and_tls_sni() -> None:
    response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"
    client, thread, state = _socket_server(response)
    ssl_context = RecordingSslContext()
    targets: list[tuple[str, int]] = []

    def socket_factory(target: tuple[str, int], timeout: float) -> socket.socket:
        targets.append(target)
        return client

    transport = PinnedSocketHttpTransport(socket_factory=socket_factory, ssl_context=ssl_context)
    status, _, body = transport.send(
        HttpRequest("GET", "https://bücher.example/study", {}, (GLOBAL_IP,)),
        connect_timeout=1.0,
        read_timeout=1.0,
    )
    thread.join(timeout=3.0)
    assert not thread.is_alive()
    request_text = state["request"].decode("iso-8859-1")
    assert targets == [(GLOBAL_IP, 443)]
    assert ssl_context.server_names == ["xn--bcher-kva.example"]
    assert "Host: xn--bcher-kva.example\r\n" in request_text
    assert status == 200
    assert body == b"{}"
