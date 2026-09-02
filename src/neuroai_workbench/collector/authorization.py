from __future__ import annotations

import json
import os
from typing import Any

from ..util import canonical_json_bytes, sha256_bytes, utc_now

LIVE_COLLECTION_ENV = "NEUROAI_LIVE_COLLECTION"
LIVE_AUTHORIZATION_ENV = "NEUROAI_LIVE_COLLECTION_AUTHORIZATION_JSON"
AUTHORIZATION_BOUNDARY = (
    "A collection authorization packet records claimed local permission for one controlled retrieval run. "
    "It is not institutional authority, legal authorization, source authenticity, or canonical publication."
)
NETWORK_MODES = frozenset({"OFFLINE", "AUTHORIZED_NETWORK"})


class CollectionAuthorizationError(PermissionError):
    """Raised when network collection is attempted without a valid authorization packet or live gate."""


def live_collection_enabled() -> bool:
    return os.environ.get(LIVE_COLLECTION_ENV, "").strip() == "1"


def authorization_digest(packet: dict[str, Any]) -> str:
    controlled = {key: value for key, value in packet.items() if key != "authorization_sha256"}
    return sha256_bytes(canonical_json_bytes(controlled))


def validate_authorization_packet(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise CollectionAuthorizationError("Collection authorization packet must be an object")
    required = (
        "authorization_id",
        "authorized_by",
        "authorized_at",
        "purpose",
        "network_mode",
        "network_permitted",
        "boundary",
    )
    missing = [key for key in required if key not in packet]
    if missing:
        raise CollectionAuthorizationError(f"Authorization packet missing fields: {missing}")
    network_mode = str(packet["network_mode"])
    if network_mode not in NETWORK_MODES:
        raise CollectionAuthorizationError(f"Unsupported authorization network_mode {network_mode!r}")
    if packet.get("boundary") != AUTHORIZATION_BOUNDARY:
        raise CollectionAuthorizationError("Authorization packet boundary is invalid")
    if not isinstance(packet["authorization_id"], str) or not str(packet["authorization_id"]).strip():
        raise CollectionAuthorizationError("authorization_id must be a non-empty string")
    if not isinstance(packet["authorized_by"], str) or not str(packet["authorized_by"]).strip():
        raise CollectionAuthorizationError("authorized_by must be a non-empty claimed local identity")
    if not isinstance(packet["authorized_at"], str) or not str(packet["authorized_at"]).strip():
        raise CollectionAuthorizationError("authorized_at must be a non-empty timestamp/date string")
    if not isinstance(packet["purpose"], str) or not str(packet["purpose"]).strip():
        raise CollectionAuthorizationError("purpose must be a non-empty string")
    if not isinstance(packet["network_permitted"], bool):
        raise CollectionAuthorizationError("network_permitted must be a boolean")
    if network_mode == "AUTHORIZED_NETWORK" and packet["network_permitted"] is not True:
        raise CollectionAuthorizationError("AUTHORIZED_NETWORK requires network_permitted=true")
    if network_mode == "OFFLINE" and packet["network_permitted"] is True:
        raise CollectionAuthorizationError("OFFLINE authorization cannot set network_permitted=true")
    digest = packet.get("authorization_sha256")
    if digest is not None:
        if not isinstance(digest, str) or len(digest) != 64:
            raise CollectionAuthorizationError("authorization_sha256 must be a 64-character hex digest")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise CollectionAuthorizationError("authorization_sha256 must be hexadecimal") from exc
        expected = authorization_digest(packet)
        if digest != expected:
            raise CollectionAuthorizationError("Authorization packet digest mismatch")
    return dict(packet)


def require_network_authorization(packet: dict[str, Any]) -> dict[str, Any]:
    validated = validate_authorization_packet(packet)
    if validated["network_mode"] != "AUTHORIZED_NETWORK":
        raise CollectionAuthorizationError("Network collection requires network_mode=AUTHORIZED_NETWORK")
    digest = validated.get("authorization_sha256")
    if not isinstance(digest, str):
        raise CollectionAuthorizationError("Network collection requires a digest-bound authorization packet")
    if digest != authorization_digest(validated):
        raise CollectionAuthorizationError("Authorization packet digest mismatch")
    if not live_collection_enabled():
        raise CollectionAuthorizationError(
            f"{LIVE_COLLECTION_ENV}=1 is required in addition to an authorization packet. "
            "The environment variable is not a sufficient gate by itself; the packet is not a sufficient "
            "gate by itself. Default CLI and data builds remain offline."
        )
    return validated


def load_live_authorization_from_environment() -> dict[str, Any]:
    raw = os.environ.get(LIVE_AUTHORIZATION_ENV, "").strip()
    if not raw:
        raise CollectionAuthorizationError(
            f"{LIVE_AUTHORIZATION_ENV} must contain a digest-bound authorization packet for live collection"
        )
    try:
        packet = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CollectionAuthorizationError(f"{LIVE_AUTHORIZATION_ENV} is not valid JSON") from exc
    if not isinstance(packet, dict):
        raise CollectionAuthorizationError(f"{LIVE_AUTHORIZATION_ENV} must decode to an object")
    return require_network_authorization(packet)


def build_authorization_packet(
    *,
    authorization_id: str,
    authorized_by: str,
    purpose: str,
    network_mode: str,
    network_permitted: bool,
    authorized_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    packet = {
        "authorization_id": authorization_id,
        "authorized_by": authorized_by,
        "authorized_at": authorized_at or utc_now(),
        "purpose": purpose,
        "network_mode": network_mode,
        "network_permitted": network_permitted,
        "expires_at": expires_at,
        "live_env": LIVE_COLLECTION_ENV,
        "boundary": AUTHORIZATION_BOUNDARY,
    }
    packet["authorization_sha256"] = authorization_digest(packet)
    return validate_authorization_packet(packet)
