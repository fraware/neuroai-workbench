from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .errors import CollectionFailureError


def public_url_error(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "URL must use http or https and include a hostname"
    if parsed.username or parsed.password:
        return "URL must not contain embedded credentials"
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        return "URL must not target a local or internal hostname"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return "URL must not target a private, loopback, link-local, reserved, multicast, or unspecified address"
    return None


def validate_public_url(value: str, *, failure_class: str = "SSRF_BLOCKED") -> None:
    error = public_url_error(value)
    if error:
        raise CollectionFailureError(failure_class, error)  # type: ignore[arg-type]
    if "@" in value:
        raise CollectionFailureError("CREDENTIAL_LEAK_PREVENTED", "URL must not contain embedded credentials")


def validate_redirect_url(value: str) -> None:
    validate_public_url(value, failure_class="REDIRECT_BLOCKED")
