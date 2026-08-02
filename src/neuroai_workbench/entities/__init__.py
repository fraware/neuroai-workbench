"""Controlled entity registry with exact-ID resolution only."""

from .errors import (
    AmbiguousResolutionError,
    EntityRegistryError,
    FuzzyMergeRefusedError,
    OverwriteRefusedError,
)
from .registry import (
    ENTITY_BOUNDARY,
    ENTITY_TYPES,
    EXACT_MATCH_MODES,
    IDENTIFIER_SCHEMES,
    RESOLUTION_STATES,
    assert_record_immutable,
    initialize_registry,
    load_entity,
    load_registry,
    refuse_fuzzy_merge,
    register_alias,
    register_entity,
    register_identifier,
    registry_status,
    resolve_exact,
    validate_registry,
)

__all__ = [
    "ENTITY_BOUNDARY",
    "ENTITY_TYPES",
    "EXACT_MATCH_MODES",
    "IDENTIFIER_SCHEMES",
    "RESOLUTION_STATES",
    "AmbiguousResolutionError",
    "EntityRegistryError",
    "FuzzyMergeRefusedError",
    "OverwriteRefusedError",
    "assert_record_immutable",
    "initialize_registry",
    "load_entity",
    "load_registry",
    "refuse_fuzzy_merge",
    "register_alias",
    "register_entity",
    "register_identifier",
    "registry_status",
    "resolve_exact",
    "validate_registry",
]
