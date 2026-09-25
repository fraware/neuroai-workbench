from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.observatory_graph.digest import object_digest
from neuroai_workbench.observatory_graph.schemas import validate_graph_object

RESOURCE_PACKAGE = "neuroai_workbench.resources.product_registry"
ENTITY_REGISTRY_RESOURCE = "RELEASE_A_SEED_PRODUCT_ENTITY_REGISTRY.v1.0.json"
ENTITY_REGISTRY_SCHEMA = "RELEASE_A_SEED_PRODUCT_ENTITY_REGISTRY.schema.json"

ENTITY_REGISTRY_ID = "RELEASE_A_SEED_PRODUCT_ENTITY_REGISTRY_v1.0"
SOURCE_SEED_MANIFEST_ID = "RASIM-7b6a3eb9271c7f8b33b6b467594789f230f6ebcd80d4f53cfac814c26e3b52bf"
SOURCE_SEED_REGISTRY_SHA256 = "9ba43d5614fb1ebb668c097a20c2279dbaaa74511956c16ee6f278cbfc109672"
ENTITY_BOUNDARY = "Release-A seed Product Entity records establish graph identity only for the exact A1 OFFERING identities. They do not establish product effectiveness, commercialization, deployment, regulatory scope beyond bound evidence, market position, population completeness, or publication authority."
BINDING_BOUNDARY = "Identity allocation binds an exact A1 product label and source observation to one canonical PRODUCT Entity ID. It does not transfer substantive product-state claims and does not authorize identity reuse or fuzzy merge."


class ReleaseAProductIdentityError(ValueError):
    """Raised when Release-A product identity authority is malformed or inconsistent."""


def _resource_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any) -> list[str]:
    schema = _resource_json(ENTITY_REGISTRY_SCHEMA)
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def seed_product_entity_registry_sha256(registry: Mapping[str, Any]) -> str:
    """Return the canonical JSON SHA-256 of one exact identity-authority artifact."""

    encoded = json.dumps(
        registry,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_default_seed_product_entity_registry(*, require_frozen: bool = False) -> dict[str, Any]:
    """Load and validate the default A1 Product Entity authority candidate."""

    registry = _resource_json(ENTITY_REGISTRY_RESOURCE)
    validate_seed_product_entity_registry(registry, require_frozen=require_frozen)
    return registry


def validate_seed_product_entity_registry(
    registry: Mapping[str, Any],
    *,
    require_frozen: bool = False,
) -> None:
    errors = _schema_errors(registry)
    if errors:
        raise ReleaseAProductIdentityError("Product Entity registry schema validation failed: " + "; ".join(errors))
    if registry["registry_id"] != ENTITY_REGISTRY_ID:
        raise ReleaseAProductIdentityError(f"registry_id must be {ENTITY_REGISTRY_ID}")
    if registry["source_seed_manifest_id"] != SOURCE_SEED_MANIFEST_ID:
        raise ReleaseAProductIdentityError("Product Entity registry does not bind the exact A1 seed manifest")
    if registry["source_seed_registry_sha256"] != SOURCE_SEED_REGISTRY_SHA256:
        raise ReleaseAProductIdentityError("Product Entity registry does not bind the exact A1 seed registry")

    authority_state = registry["authority_state"]
    if require_frozen and authority_state != "FROZEN_v1.0":
        raise ReleaseAProductIdentityError("Canonical Product Entity authority is not frozen")
    if authority_state == "FROZEN_v1.0":
        if not registry.get("approved_candidate_blob_sha") or not registry.get("approval_ref"):
            raise ReleaseAProductIdentityError("Frozen Product Entity authority requires exact candidate blob and approval ref")
    else:
        if registry.get("approved_candidate_blob_sha") is not None or registry.get("approval_ref") is not None:
            raise ReleaseAProductIdentityError("Pending Product Entity authority cannot claim an approval binding")

    entities = registry["entities"]
    bindings = registry["identity_bindings"]
    if registry["entity_count"] != len(entities) or registry["entity_count"] != len(bindings):
        raise ReleaseAProductIdentityError("entity_count must match entity and identity-binding cardinality")

    entity_index: dict[str, Mapping[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise ReleaseAProductIdentityError("Product Entity entries must be objects")
        entity_id = str(entity.get("entity_id", ""))
        if not entity_id or entity_id in entity_index:
            raise ReleaseAProductIdentityError(f"Duplicate or empty Product Entity ID: {entity_id!r}")
        if entity.get("entity_type") != "PRODUCT":
            raise ReleaseAProductIdentityError(f"{entity_id} must have entity_type PRODUCT")
        if entity.get("object_class") != "Entity":
            raise ReleaseAProductIdentityError(f"{entity_id} must be an Observatory graph Entity")
        if entity.get("boundary") != ENTITY_BOUNDARY:
            raise ReleaseAProductIdentityError(f"{entity_id} identity boundary mismatch")
        body = dict(entity)
        observed_digest = body.pop("canonical_sha256", None)
        graph_errors = validate_graph_object(body, "Entity")
        if graph_errors:
            raise ReleaseAProductIdentityError(f"{entity_id} graph Entity validation failed: {graph_errors}")
        if observed_digest is not None and observed_digest != object_digest(body):
            raise ReleaseAProductIdentityError(f"{entity_id} canonical_sha256 mismatch")
        entity_index[entity_id] = entity

    binding_index: dict[str, Mapping[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise ReleaseAProductIdentityError("Identity bindings must be objects")
        entity_id = str(binding.get("entity_id", ""))
        if not entity_id or entity_id in binding_index:
            raise ReleaseAProductIdentityError(f"Duplicate or empty identity binding: {entity_id!r}")
        if binding.get("identity_level") != "OFFERING":
            raise ReleaseAProductIdentityError(f"{entity_id} identity binding must be OFFERING")
        if binding.get("boundary") != BINDING_BOUNDARY:
            raise ReleaseAProductIdentityError(f"{entity_id} identity-binding boundary mismatch")
        if authority_state == "FROZEN_v1.0" and binding.get("allocation_state") != "CANONICAL_ENTITY_APPROVED":
            raise ReleaseAProductIdentityError(f"{entity_id} frozen authority requires approved allocation state")
        if authority_state != "FROZEN_v1.0" and binding.get("allocation_state") != "NEW_CANONICAL_ENTITY_CANDIDATE":
            raise ReleaseAProductIdentityError(f"{entity_id} pending authority requires candidate allocation state")
        binding_index[entity_id] = binding

    if set(entity_index) != set(binding_index):
        raise ReleaseAProductIdentityError("Product Entity set does not exactly match identity-binding set")

    for entity_id, entity in entity_index.items():
        binding = binding_index[entity_id]
        if entity["canonical_label"] != binding["exact_product_label"]:
            raise ReleaseAProductIdentityError(f"{entity_id} canonical label does not match identity evidence label")


def cross_validate_product_entities_against_a1(
    entity_registry: Mapping[str, Any],
    *,
    seed_manifest: Mapping[str, Any],
    seed_registry: Mapping[str, Any],
    evidence_packet: Mapping[str, Any],
    require_frozen: bool = False,
) -> None:
    """Bind canonical Product Entities to the exact A1 evidence and registry projection."""

    validate_seed_product_entity_registry(entity_registry, require_frozen=require_frozen)

    bindings = {
        str(item["canonical_entity_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], seed_manifest["bindings"])
    }
    rows = {
        str(item["canonical_entity_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], seed_registry["rows"])
    }
    observations = {
        str(item["observation_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], evidence_packet["observations"])
    }
    entity_bindings = {
        str(item["entity_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], entity_registry["identity_bindings"])
    }
    entities = {
        str(item["entity_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], entity_registry["entities"])
    }

    expected_ids = set(bindings)
    if set(rows) != expected_ids or set(entities) != expected_ids or set(entity_bindings) != expected_ids:
        raise ReleaseAProductIdentityError("A1 Product Entity authority must exactly cover the seed offering identity set")

    for entity_id in sorted(expected_ids):
        seed_binding = bindings[entity_id]
        row = rows[entity_id]
        entity = entities[entity_id]
        identity_binding = entity_bindings[entity_id]
        if row.get("canonical_entity_type") != "PRODUCT" or row.get("identity_level") != "OFFERING":
            raise ReleaseAProductIdentityError(f"{entity_id} A1 row is not a PRODUCT OFFERING projection")
        if row.get("identity_state") != "RESOLVED":
            raise ReleaseAProductIdentityError(f"{entity_id} A1 row must remain RESOLVED")
        if entity["canonical_label"] != seed_binding["exact_product_label"]:
            raise ReleaseAProductIdentityError(f"{entity_id} entity label does not match A1 seed binding")
        expected_observations = {str(ref) for ref in seed_binding["source_observation_refs"]}
        observed_binding_refs = {str(ref) for ref in identity_binding["source_observation_refs"]}
        if observed_binding_refs != expected_observations:
            raise ReleaseAProductIdentityError(f"{entity_id} identity evidence does not exactly match A1 seed observations")
        for observation_ref in expected_observations:
            observation = observations.get(observation_ref)
            if observation is None:
                raise ReleaseAProductIdentityError(f"{entity_id} identity evidence references unknown observation")
            if observation.get("exact_product_label") != entity["canonical_label"]:
                raise ReleaseAProductIdentityError(f"{entity_id} source observation label does not match canonical label")
