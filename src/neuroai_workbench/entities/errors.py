from __future__ import annotations


class EntityRegistryError(ValueError):
    """Base error for entity registry operations."""


class FuzzyMergeRefusedError(EntityRegistryError):
    """Raised when a non-exact or similarity-based merge is requested."""


class OverwriteRefusedError(EntityRegistryError):
    """Raised when an in-place rewrite of a canonical record is attempted."""


class AmbiguousResolutionError(EntityRegistryError):
    """Raised when multiple exact matches would collide."""
