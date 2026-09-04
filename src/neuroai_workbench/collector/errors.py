from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FailureClass = Literal[
    "SSRF_BLOCKED",
    "DNS_REBINDING_BLOCKED",
    "REDIRECT_BLOCKED",
    "POLICY_BLOCK",
    "TIMEOUT",
    "SIZE_LIMIT_EXCEEDED",
    "DECOMPRESSION_BOMB",
    "UNSAFE_FILENAME",
    "CREDENTIAL_LEAK_PREVENTED",
    "ROBOTS_DISALLOWED",
    "TERMS_OF_USE_BLOCKED",
    "HTTP_ERROR",
    "NETWORK_ERROR",
    "AUTHENTICATION_REQUIRED",
    "CONTENT_TYPE_REJECTED",
    "QUARANTINE_REJECTED",
    "UNKNOWN",
]


@dataclass(frozen=True)
class CollectionFailureError(Exception):
    failure_class: FailureClass
    message: str

    def __str__(self) -> str:
        return self.message
