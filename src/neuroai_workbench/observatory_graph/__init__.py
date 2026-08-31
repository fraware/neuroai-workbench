"""Canonical observatory-graph types as schema-validated dicts with deterministic digests."""

from .digest import attach_digest, object_digest
from .identity import (
    GRAPH_BOUNDARY,
    IDENTITY_KINDS,
    KIND_IDENTIFIER,
    KIND_RESOLVED_ENTITY_REFERENCE,
    KIND_UNRESOLVED_LITERAL,
    IdentityError,
    UnresolvedLiteralError,
    dump_identity_ref,
    parse_identity_ref,
    require_resolved_entity_id,
)
from .loaders import (
    LOADER_BOUNDARY,
    assert_non_authoritative,
    materialize_derived_projection,
)
from .objects import (
    OBJECT_CLASSES,
    build_assertion,
    build_candidate,
    build_entity,
    build_event,
    build_observation,
    build_relationship,
    build_reopening_decision,
    build_source,
    persistable,
)
from .schemas import validate_graph_object, validate_or_raise
from .temporal_compiler import (
    COMPILER_BOUNDARY,
    compile_temporal_graph,
    predecessor_successor_diff,
    state_as_of_release,
    state_valid_at,
    validate_temporal_integrity,
)

__all__ = [
    "COMPILER_BOUNDARY",
    "GRAPH_BOUNDARY",
    "IDENTITY_KINDS",
    "KIND_IDENTIFIER",
    "KIND_RESOLVED_ENTITY_REFERENCE",
    "KIND_UNRESOLVED_LITERAL",
    "LOADER_BOUNDARY",
    "OBJECT_CLASSES",
    "IdentityError",
    "UnresolvedLiteralError",
    "assert_non_authoritative",
    "attach_digest",
    "build_assertion",
    "build_candidate",
    "build_entity",
    "build_event",
    "build_observation",
    "build_reopening_decision",
    "build_relationship",
    "build_source",
    "compile_temporal_graph",
    "dump_identity_ref",
    "materialize_derived_projection",
    "object_digest",
    "parse_identity_ref",
    "persistable",
    "predecessor_successor_diff",
    "require_resolved_entity_id",
    "state_as_of_release",
    "state_valid_at",
    "validate_graph_object",
    "validate_or_raise",
    "validate_temporal_integrity",
]
