from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.transport import StdlibHttpTransport


@dataclass
class FakeSocket:
    timeouts: list[float] = field(default_factory=list)

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)


@dataclass
class FakeResponse:
    status: int = 200
    headers: list[tuple[str, str]] = field(default_factory=lambda: [("Content-Type", "application/json")])
    body: bytes = b'{"ok":true}'

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self.headers)

    def read(self) -> bytes:
        return self.body


class FakeConnection:
    def __init__(self, *, sock: FakeSocket | None = None, response: FakeResponse | None = None) -> None:
        self.sock = sock
        self.response = response or FakeResponse()
        self.connected = False
        self.closed = False
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.raise_on_getresponse: Exception | None = None

    def connect(self) -> None:
        self.connected = True

    def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
        self.requests.append((method, path, dict(headers)))

    def getresponse(self) -> FakeResponse:
        if self.raise_on_getresponse is not None:
            raise self.raise_on_getresponse
        return self.response

    def close(self) -> None:
        self.closed = True


def test_https_uses_python_secure_default_context_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[tuple[str, int, dict[str, Any], FakeConnection]] = []

    def https_factory(host: str, port: int, **kwargs: Any) -> FakeConnection:
        connection = FakeConnection(sock=FakeSocket())
        created.append((host, port, kwargs, connection))
        return connection

    monkeypatch.setattr("neuroai_workbench.collector.transport.http.client.HTTPSConnection", https_factory)
    transport = StdlibHttpTransport()
    status, headers, body = transport.send(
        HttpRequest(
            "GET",
            "https://example.org/api/v2/studies/NCT04676854?format=json",
            {"Accept": "application/json"},
        ),
        connect_timeout=7.0,
        read_timeout=13.0,
    )

    host, port, kwargs, connection = created[0]
    assert (host, port) == ("example.org", 443)
    assert kwargs == {"timeout": 7.0}
    assert "context" not in kwargs
    assert connection.connected is True
    assert connection.sock is not None
    assert connection.sock.timeouts == [13.0]
    assert connection.requests == [("GET", "/api/v2/studies/NCT04676854?format=json", {"Accept": "application/json"})]
    assert connection.closed is True
    assert status == 200
    assert headers == {"Content-Type": "application/json"}
    assert body == b'{"ok":true}'


def test_http_transport_preserves_explicit_port_root_path_and_no_socket_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[tuple[str, int, dict[str, Any], FakeConnection]] = []

    def http_factory(host: str, port: int, **kwargs: Any) -> FakeConnection:
        connection = FakeConnection(sock=None, response=FakeResponse(status=204, headers=[], body=b""))
        created.append((host, port, kwargs, connection))
        return connection

    monkeypatch.setattr("neuroai_workbench.collector.transport.http.client.HTTPConnection", http_factory)
    result = StdlibHttpTransport().send(
        HttpRequest("HEAD", "http://example.org:8080", {"X-Test": "1"}),
        connect_timeout=3.0,
        read_timeout=4.0,
    )

    host, port, kwargs, connection = created[0]
    assert (host, port, kwargs) == ("example.org", 8080, {"timeout": 3.0})
    assert connection.requests == [("HEAD", "/", {"X-Test": "1"})]
    assert connection.closed is True
    assert result == (204, {}, b"")


@pytest.mark.parametrize("url", ["ftp://example.org/file", "https:///missing-host", "not-a-url"])
def test_transport_rejects_non_http_or_missing_host(url: str) -> None:
    with pytest.raises(ValueError, match="URL must use http or https with a hostname"):
        StdlibHttpTransport().send(
            HttpRequest("GET", url, {}),
            connect_timeout=1.0,
            read_timeout=1.0,
        )


def test_transport_closes_connection_when_response_path_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(sock=FakeSocket())
    connection.raise_on_getresponse = RuntimeError("boom")

    def https_factory(host: str, port: int, **kwargs: Any) -> FakeConnection:
        del host, port, kwargs
        return connection

    monkeypatch.setattr("neuroai_workbench.collector.transport.http.client.HTTPSConnection", https_factory)
    with pytest.raises(RuntimeError, match="boom"):
        StdlibHttpTransport().send(
            HttpRequest("GET", "https://example.org/x", {}),
            connect_timeout=1.0,
            read_timeout=2.0,
        )
    assert connection.closed is True
