from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .errors import CollectionFailureError
from .url_policy import validate_public_url

GetAddrInfo = Callable[..., Sequence[tuple[Any, ...]]]


@dataclass
class DnsResolutionRecord:
    hostname: str
    resolved_at: str
    addresses: list[str]
    rebinding_check: str = "PASSED"


@dataclass
class DnsGuard:
    getaddrinfo: GetAddrInfo = socket.getaddrinfo
    _seen_addresses: dict[str, frozenset[str]] = field(default_factory=dict)

    def new_session(self) -> DnsGuard:
        """Return an isolated request session using the same resolver.

        Rebinding state is intentionally scoped to one logical HTTP fetch so
        redirects inside that fetch are compared with each other, while
        concurrent independent fetches never clear or overwrite shared state.
        """
        return DnsGuard(getaddrinfo=self.getaddrinfo)

    def reset(self) -> None:
        self._seen_addresses.clear()

    def resolve(self, url: str) -> DnsResolutionRecord:
        validate_public_url(url)
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname
        if hostname is None:
            raise CollectionFailureError("SSRF_BLOCKED", "URL must include a hostname")
        normalized = hostname.lower().rstrip(".")
        try:
            ipaddress.ip_address(normalized)
            addresses = [normalized]
        except ValueError:
            try:
                results = self.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
            except socket.gaierror as exc:
                raise CollectionFailureError("NETWORK_ERROR", f"DNS resolution failed for {normalized!r}") from exc
            addresses = sorted({item[4][0] for item in results if item[4]})
            if not addresses:
                raise CollectionFailureError(
                    "NETWORK_ERROR", f"DNS resolution returned no addresses for {normalized!r}"
                )

        validated: list[str] = []
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise CollectionFailureError(
                    "SSRF_BLOCKED",
                    f"Resolved address {address} is not globally routable",
                )
            validated.append(str(ip))

        current = frozenset(validated)
        previous = self._seen_addresses.get(normalized)
        if previous is not None and previous != current:
            raise CollectionFailureError(
                "DNS_REBINDING_BLOCKED",
                f"DNS rebinding detected for {normalized!r}: {sorted(previous)} -> {sorted(current)}",
            )
        self._seen_addresses[normalized] = current
        resolved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return DnsResolutionRecord(
            hostname=normalized,
            resolved_at=resolved_at,
            addresses=validated,
            rebinding_check="PASSED",
        )
