from __future__ import annotations

import http.client
from dataclasses import dataclass
from urllib.parse import urlparse

from .http_client import HttpRequest


@dataclass(frozen=True)
class StdlibHttpTransport:
    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        parsed = urlparse(request.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL must use http or https with a hostname")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        if parsed.scheme == "https":
            # Let HTTPSConnection construct Python's secure default TLS context.
            # Supplying our own otherwise-unmodified SSLContext changes the TLS
            # client profile and has caused standards-compliant upstream edges
            # to reject requests. The implicit context retains certificate and
            # hostname verification and Python's current HTTPS defaults.
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                parsed.hostname,
                port,
                timeout=connect_timeout,
            )
        else:
            connection = http.client.HTTPConnection(parsed.hostname, port, timeout=connect_timeout)

        try:
            connection.connect()
            if connection.sock is not None:
                connection.sock.settimeout(read_timeout)
            connection.request(request.method, path, headers=dict(request.headers))
            response = connection.getresponse()
            headers = {key: value for key, value in response.getheaders()}
            body = response.read()
            return response.status, headers, body
        finally:
            connection.close()
