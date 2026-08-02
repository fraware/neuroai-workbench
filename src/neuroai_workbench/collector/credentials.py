from __future__ import annotations

import re
from typing import Any, Protocol
from urllib.parse import urlparse

from .errors import CollectionFailureError

SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "authorization",
        "token",
        "secret",
        "access_token",
        "refresh_token",
        "client_secret",
    }
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"^Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"^Basic\s+\S+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*\S+"),
)


class CredentialProvider(Protocol):
    def authorization_header(self, source_id: str) -> str | None:
        """Return an Authorization header value for the source, or None when unavailable."""


class StaticCredentialProvider:
    """In-memory credential map for approved deployments and offline tests only."""

    def __init__(self, headers_by_source: dict[str, str]) -> None:
        self._headers = dict(headers_by_source)

    def authorization_header(self, source_id: str) -> str | None:
        return self._headers.get(source_id)


def embedded_credential_in_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return True
    if "@" in url and "://" in url:
        authority = url.split("://", 1)[1].split("/", 1)[0]
        if "@" in authority and ":" in authority.split("@", 1)[0]:
            return True
    return False


def refuse_embedded_secrets_in_request(request: dict[str, Any]) -> None:
    url = str(request.get("requested_url", ""))
    if embedded_credential_in_url(url):
        raise CollectionFailureError(
            "CREDENTIAL_LEAK_PREVENTED",
            "Collection request URL must not contain embedded credentials",
        )
    refuse_secrets_in_value(request, label="collection request")


def refuse_secrets_in_value(value: Any, *, label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SECRET_FIELD_NAMES:
                raise CollectionFailureError(
                    "CREDENTIAL_LEAK_PREVENTED",
                    f"{label} must not contain credential field {key!r}",
                )
            refuse_secrets_in_value(item, label=label)
        return
    if isinstance(value, list):
        for item in value:
            refuse_secrets_in_value(item, label=label)
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise CollectionFailureError(
                    "CREDENTIAL_LEAK_PREVENTED",
                    f"{label} must not contain embedded secret material",
                )
