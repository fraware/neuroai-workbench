"""Test-only socketpair wrappers for pinned HTTP transport fixtures.

Production `_verified_peer_address` fail-closes when an INET `getpeername`
result does not match the selected DnsGuard pin, including loopback. POSIX
`socket.socketpair()` is AF_UNIX and takes the non-INET fixture path. Windows
`socketpair()` is AF_INET to 127.0.0.1, which would otherwise abort Host/SNI
protocol tests as a false SSRF. Protocol fixtures wrap that socket; dedicated
peer-verify tests still use explicit INET doubles.
"""

from __future__ import annotations

import socket
from typing import Any


class NonInternetFixtureSocket:
    """Present a socketpair endpoint as a non-Internet test transport."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self.family = socket.AF_UNSPEC

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sock, name)


def as_transport_fixture_socket(sock: socket.socket) -> socket.socket | NonInternetFixtureSocket:
    family = getattr(sock, "family", None)
    if family in {socket.AF_INET, socket.AF_INET6}:
        return NonInternetFixtureSocket(sock)
    return sock
