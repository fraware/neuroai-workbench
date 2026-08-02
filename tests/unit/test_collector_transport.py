from __future__ import annotations

from unittest.mock import MagicMock, patch

from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.transport import StdlibHttpTransport


def test_stdlib_transport_reads_response() -> None:
    transport = StdlibHttpTransport()
    response = MagicMock()
    response.status = 200
    response.getheaders.return_value = [("Content-Type", "text/plain")]
    response.read.return_value = b"hello"

    connection = MagicMock()
    connection.getresponse.return_value = response

    with patch("neuroai_workbench.collector.transport.http.client.HTTPConnection", return_value=connection):
        status, headers, body = transport.send(
            HttpRequest("GET", "http://example.org/path", {"User-Agent": "test"}),
            connect_timeout=1.0,
            read_timeout=1.0,
        )

    assert status == 200
    assert headers["Content-Type"] == "text/plain"
    assert body == b"hello"
    connection.close.assert_called_once()
