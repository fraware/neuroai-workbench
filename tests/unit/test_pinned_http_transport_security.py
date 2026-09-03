from __future__ import annotations

import socket
from typing import Any

import pytest

import neuroai_workbench.collector.pinned_transport as pinned_transport
from neuroai_workbench.collector import PinnedSocketHttpTransport
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest

GLOBAL_IP = "93.184.216.34"
SECOND_GLOBAL_IP = "8.8.8.8"


class FakeDirectSocket:
    def __init__(self) -> None:
        self.timeouts: list[float] = []
        self.targets: list[Any] = []
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def connect(self, target: Any) -> None:
        self.targets.append(target)

    def close(self) -> None:
        self.closed = True


def test_default_socket_factory_uses_direct_numeric_socket_without_getaddrinfo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[tuple[int, int, FakeDirectSocket]] = []

    def fail_getaddrinfo(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("default pinned transport socket factory must not call getaddrinfo")

    def fake_socket(family: int, socktype: int) -> FakeDirectSocket:
        sock = FakeDirectSocket()
        created.append((family, socktype, sock))
        return sock

    monkeypatch.setattr(pinned_transport.socket, "getaddrinfo", fail_getaddrinfo)
    monkeypatch.setattr(pinned_transport.socket, "socket", fake_socket)

    sock = pinned_transport._default_socket_factory((GLOBAL_IP, 443), 1.25)
    assert sock is created[0][2]
    assert created[0][:2] == (socket.AF_INET, socket.SOCK_STREAM)
    assert sock.timeouts == [1.25]
    assert sock.targets == [(GLOBAL_IP, 443)]
    assert sock.closed is False


def test_default_socket_factory_closes_socket_when_direct_connect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSocket(FakeDirectSocket):
        def connect(self, target: Any) -> None:
            self.targets.append(target)
            raise OSError("connect failed")

    broken = BrokenSocket()
    monkeypatch.setattr(pinned_transport.socket, "socket", lambda family, socktype: broken)
    with pytest.raises(OSError, match="connect failed"):
        pinned_transport._default_socket_factory((GLOBAL_IP, 443), 1.0)
    assert broken.closed is True


@pytest.mark.parametrize("url", ["https://example.org:0/x", "http://example.org:0/x"])
def test_transport_rejects_explicit_zero_port_before_opening_socket(url: str) -> None:
    def fail_socket(target: tuple[str, int], timeout: float) -> Any:
        pytest.fail("invalid port must be rejected before socket creation")

    transport = PinnedSocketHttpTransport(socket_factory=fail_socket)
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", url, {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert exc.value.failure_class == "SSRF_BLOCKED"
    assert "outside the allowed range" in str(exc.value)


def test_transport_rejects_invalid_textual_port_before_socket_creation() -> None:
    def fail_socket(target: tuple[str, int], timeout: float) -> Any:
        pytest.fail("invalid port must be rejected before socket creation")

    transport = PinnedSocketHttpTransport(socket_factory=fail_socket)
    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org:not-a-port/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_transport_rejects_mismatched_actual_inet_peer() -> None:
    class MismatchedPeerSocket:
        family = socket.AF_INET

        def __init__(self) -> None:
            self.closed = False

        def getpeername(self) -> tuple[str, int]:
            return (SECOND_GLOBAL_IP, 443)

        def close(self) -> None:
            self.closed = True

    peer_socket = MismatchedPeerSocket()
    transport = PinnedSocketHttpTransport(socket_factory=lambda target, timeout: peer_socket)

    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )

    assert exc.value.failure_class == "SSRF_BLOCKED"
    assert "does not match validated address" in str(exc.value)
    assert peer_socket.closed is True


def test_transport_rejects_unverifiable_actual_inet_peer() -> None:
    class UnverifiablePeerSocket:
        family = socket.AF_INET

        def __init__(self) -> None:
            self.closed = False

        def getpeername(self) -> tuple[str, int]:
            raise OSError("peer unavailable")

        def close(self) -> None:
            self.closed = True

    peer_socket = UnverifiablePeerSocket()
    transport = PinnedSocketHttpTransport(socket_factory=lambda target, timeout: peer_socket)

    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )

    assert exc.value.failure_class == "SSRF_BLOCKED"
    assert "Unable to verify connected transport peer" in str(exc.value)
    assert peer_socket.closed is True


def test_transport_rejects_loopback_inet_peer_against_global_pin() -> None:
    class LoopbackPeerSocket:
        family = socket.AF_INET

        def __init__(self) -> None:
            self.closed = False

        def getpeername(self) -> tuple[str, int]:
            return ("127.0.0.1", 443)

        def close(self) -> None:
            self.closed = True

    peer_socket = LoopbackPeerSocket()
    transport = PinnedSocketHttpTransport(socket_factory=lambda target, timeout: peer_socket)

    with pytest.raises(CollectionFailureError) as exc:
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )

    assert exc.value.failure_class == "SSRF_BLOCKED"
    assert "does not match validated address" in str(exc.value)
    assert peer_socket.closed is True
