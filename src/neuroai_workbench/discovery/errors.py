from __future__ import annotations


class DiscoveryError(ValueError):
    """Base error for discovery workflow failures."""


class DiscoveryNetworkBlockedError(DiscoveryError):
    """Raised when opt-in network discovery is attempted without the live gate."""


class DiscoveryOverwriteRefusedError(DiscoveryError):
    """Raised when a caller attempts in-place registry overwrite instead of a successor."""


class DiscoveryAdjudicationRequiredError(DiscoveryError):
    """Raised when registry succession is requested without accepted human adjudication."""
