"""Extra adversarial coverage for pinned HTTP transport edge paths."""

from __future__ import annotations

import http.client
from typing import Any

import pytest
import urllib3

import neuroai_workbench.collector.pinned_transport as pinned_transport
from neuroai_workbench.collector import PinnedSocketHttpTransport
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest

GLOBAL_IP = "93.184.216.34"


def test_default_socket_factory_rejects_non_ip_literal() -> None:
    with pytest.raises(OSError, match="not an IP literal"):
        pinned_transport._default_socket_factory(("example.org", 443), 1.0)


def test_validated_addresses_reject_non_ip_and_empty() -> None:
    with pytest.raises(CollectionFailureError, match="non-empty"):
        pinned_transport._validated_global_addresses(())
    with pytest.raises(CollectionFailureError, match="not an IP literal"):
        pinned_transport._validated_global_addresses(("not-an-ip",))


def test_network_hostname_accepts_ip_literal() -> None:
    assert pinned_transport._network_hostname("93.184.216.34") == "93.184.216.34"
    assert pinned_transport._network_hostname("example.org.") == "example.org"


def test_transport_rejects_unsupported_scheme_and_missing_host() -> None:
    transport = PinnedSocketHttpTransport(socket_factory=lambda *_: pytest.fail("no socket"))
    with pytest.raises(CollectionFailureError, match="http or https|hostname|scheme"):
        transport.send(
            HttpRequest("GET", "ftp://example.org/x", {}, (GLOBAL_IP,)), connect_timeout=1.0, read_timeout=1.0
        )
    with pytest.raises(CollectionFailureError, match="hostname|http or https"):
        transport.send(HttpRequest("GET", "https:///x", {}, (GLOBAL_IP,)), connect_timeout=1.0, read_timeout=1.0)


def test_transport_timeout_error_is_not_swallowed() -> None:
    def boom(address: tuple[str, int], timeout: float) -> Any:
        raise TimeoutError("connect timed out")

    transport = PinnedSocketHttpTransport(socket_factory=boom)
    with pytest.raises(TimeoutError, match="timed out"):
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )


def test_transport_rejects_nonpositive_max_wire_bytes() -> None:
    with pytest.raises(ValueError, match="positive"):
        PinnedSocketHttpTransport(max_wire_bytes=0)


def test_transport_rejects_non_string_headers_and_latin1_failure() -> None:
    transport = PinnedSocketHttpTransport(socket_factory=lambda *_: pytest.fail("no socket"))
    with pytest.raises(CollectionFailureError, match="must be strings"):
        transport.send(
            HttpRequest("GET", "https://example.org/x", {"X-A": 1}, (GLOBAL_IP,)),  # type: ignore[dict-item]
            connect_timeout=1.0,
            read_timeout=1.0,
        )

    # Force encode failure after Host is set by using a unicode header value that survives CRLF checks.
    with pytest.raises(CollectionFailureError, match="Latin-1"):
        transport.send(
            HttpRequest("GET", "https://example.org/x", {"X-Weird": "ok\u2603"}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )


def test_transport_retries_oserror_then_raises_last_error() -> None:
    calls: list[str] = []

    def failing_factory(address: tuple[str, int], timeout: float) -> Any:
        calls.append(address[0])
        raise OSError(f"down:{address[0]}")

    transport = PinnedSocketHttpTransport(socket_factory=failing_factory)
    with pytest.raises(OSError, match="down:8.8.8.8"):
        transport.send(
            HttpRequest("GET", "https://example.org/x", {}, (GLOBAL_IP, "8.8.8.8")),
            connect_timeout=1.0,
            read_timeout=1.0,
        )
    assert calls == [GLOBAL_IP, "8.8.8.8"]


def test_transport_malformed_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomResponse:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        def begin(self) -> None:
            raise http.client.HTTPException("bad response")

        def close(self) -> None:
            return None

    class FakeSock:
        def settimeout(self, value: float) -> None:
            return None

        def sendall(self, data: bytes) -> None:
            return None

        def close(self) -> None:
            return None

    transport = PinnedSocketHttpTransport(socket_factory=lambda address, timeout: FakeSock())
    monkeypatch.setattr(pinned_transport._PinnedUrllib3HTTPConnection, "response_class", BoomResponse)
    with pytest.raises(CollectionFailureError, match="Malformed HTTP"):
        transport.send(
            HttpRequest("GET", "http://example.org/x", {}, (GLOBAL_IP,)),
            connect_timeout=1.0,
            read_timeout=1.0,
        )


def test_https_connection_delegates_tls_to_native_urllib3_connect() -> None:
    assert issubclass(pinned_transport._PinnedUrllib3Connection, urllib3.connection.HTTPSConnection)
    assert pinned_transport._PinnedUrllib3Connection.connect is urllib3.connection.HTTPSConnection.connect
