from __future__ import annotations

import socket
import threading

import pytest

from neuroai_workbench.collector import PinnedSocketHttpTransport
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest
from tests.unit.pinned_transport_fixtures import as_transport_fixture_socket

GLOBAL_IP = "93.184.216.34"


def test_malformed_http_response_becomes_network_error() -> None:
    client, server = socket.socketpair()
    client = as_transport_fixture_socket(client)

    def serve() -> None:
        server.settimeout(2.0)
        try:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = server.recv(4096)
                if not chunk:
                    break
                request += chunk
            server.sendall(b"THIS IS NOT HTTP\r\n\r\n")
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    transport = PinnedSocketHttpTransport(socket_factory=lambda target, timeout: client)
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "http://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    thread.join(timeout=3.0)
    assert not thread.is_alive()
    assert exc.value.failure_class == "NETWORK_ERROR"
    assert "Malformed HTTP response" in str(exc.value)
