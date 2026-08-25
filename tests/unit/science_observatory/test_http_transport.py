from __future__ import annotations

import io
import urllib.error
from email.message import Message

import pytest

from neuroai_workbench.science_observatory.http_transport import NoRedirectUrllibTransport
from neuroai_workbench.science_observatory.source_contracts import EXPECTED_FROZEN_USER_AGENT


class RedirectingOpener:
    def __init__(self) -> None:
        self.last_request = None
        self.last_timeout = None

    def open(self, request, timeout=None):
        self.last_request = request
        self.last_timeout = timeout
        headers = Message()
        headers["Location"] = "https://example.invalid/redirected"
        raise urllib.error.HTTPError(
            request.full_url,
            302,
            "Found",
            headers,
            io.BytesIO(b"redirect-body"),
        )


def test_redirect_is_returned_as_http_result_not_followed() -> None:
    transport = NoRedirectUrllibTransport(
        user_agent=EXPECTED_FROZEN_USER_AGENT,
        timeout_seconds=1.0,
    )
    opener = RedirectingOpener()
    transport._opener = opener

    result = transport.fetch("https://example.invalid/original")

    assert result.status == 302
    assert result.body == b"redirect-body"
    assert result.headers["location"] == "https://example.invalid/redirected"
    assert transport.redirect_policy == "FAIL_CLOSED_NO_AUTO_FOLLOW"
    assert opener.last_request.full_url == "https://example.invalid/original"
    assert opener.last_request.get_header("User-agent") == EXPECTED_FROZEN_USER_AGENT
    assert opener.last_timeout == 1.0


def test_transport_has_no_repository_local_default_client_identity() -> None:
    with pytest.raises(TypeError):
        NoRedirectUrllibTransport()  # type: ignore[call-arg]


def test_blank_user_agent_is_rejected() -> None:
    with pytest.raises(ValueError, match="user_agent"):
        NoRedirectUrllibTransport(user_agent="   ")


def test_nonpositive_timeout_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        NoRedirectUrllibTransport(user_agent=EXPECTED_FROZEN_USER_AGENT, timeout_seconds=0)
