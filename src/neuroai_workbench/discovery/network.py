from __future__ import annotations

import os

from .boundary import DISCOVERY_NETWORK_ENV, DISCOVERY_SSRF_POLICY
from .errors import DiscoveryNetworkBlockedError


def network_discovery_allowed() -> bool:
    """Opt-in live discovery gate. Default is offline-first (denied)."""
    return os.environ.get(DISCOVERY_NETWORK_ENV) == "1"


def require_network_discovery_allowed() -> dict[str, object]:
    allowed = network_discovery_allowed()
    gate = {
        "env_var": DISCOVERY_NETWORK_ENV,
        "allowed": allowed,
        "ssrf_policy": DISCOVERY_SSRF_POLICY,
    }
    if not allowed:
        raise DiscoveryNetworkBlockedError(
            f"Opt-in network discovery requires {DISCOVERY_NETWORK_ENV}=1; "
            "default remains offline-first with fixture or replay inputs only."
        )
    return gate


def validate_discovery_url(url: str) -> None:
    """Apply the same public-URL SSRF checks used by the collector transport boundary."""
    from ..collector.errors import CollectionFailureError
    from ..collector.url_policy import validate_public_url

    try:
        validate_public_url(url)
    except CollectionFailureError as exc:
        raise DiscoveryNetworkBlockedError(f"Discovery URL blocked by SSRF policy: {exc}") from exc

