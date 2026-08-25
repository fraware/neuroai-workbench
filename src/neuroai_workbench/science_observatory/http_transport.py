from __future__ import annotations

import urllib.error
import urllib.request
from typing import NamedTuple


class HttpResult(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirect responses to the caller instead of following them implicitly."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


class NoRedirectUrllibTransport:
    """HTTP transport that makes redirects explicit acquisition evidence.

    The caller must supply the user-agent identity from the frozen S2 query
    contract. No repository-local default is used. Automatic redirects are
    disabled because following one would introduce an unrecorded response and
    silently change the effective endpoint.
    """

    redirect_policy = "FAIL_CLOSED_NO_AUTO_FOLLOW"

    def __init__(self, *, user_agent: str, timeout_seconds: float = 60.0) -> None:
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be a non-empty frozen client identity")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.user_agent = user_agent
        self.timeout_seconds = float(timeout_seconds)
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def fetch(self, url: str) -> HttpResult:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                return HttpResult(
                    status=int(response.status),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return HttpResult(
                status=int(exc.code),
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=exc.read(),
            )
