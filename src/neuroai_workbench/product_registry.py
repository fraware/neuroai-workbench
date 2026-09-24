from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

RESOURCE_PACKAGE = "neuroai_workbench.resources.product_registry"
ROW_SCHEMA = "PRODUCT_REGISTRY_ROW.schema.json"
REGISTRY_SCHEMA = "PRODUCT_REGISTRY.schema.json"

REGISTRY_PROJECTION_VERSION = "PRODUCT_REGISTRY_v1.0"
BOUNDARY_CONTRACT_ID = "PRODUCT_MEASUREMENT_CONTRACT_v1.0"
BOUNDARY_CONTRACT_SEMANTIC_BLOB = "7cbd7f086d80505da7a7c35a38f3aa0ce690ec41"
REFERENCE_STANDARD_ID = "D4_PRODUCT_REFERENCE_STANDARD_v1.0"
REFERENCE_STANDARD_VERSION = "1.0"
REFERENCE_STANDARD_VALIDATION_STATE = "FROZEN_WORKING_REFERENCE"
CURRENTNESS_POLICY_ID = "PRODUCT_CURRENTNESS_POLICY_v1.0"
POPULATION_VIEW_POLICY_ID = "PRODUCT_POPULATION_VIEW_POLICY_v1.0"

IDENTITY_LEVELS = frozenset({"FAMILY", "OFFERING", "CONFIGURATION"})
ENUMERATION_ROLES = frozenset(
    {
        "INTEGRATED_SYSTEM",
        "COMPONENT_OR_SUBSYSTEM",
        "STANDALONE_SOFTWARE_OR_SERVICE",
        "UNRESOLVED",
        "OTHER_REVIEW_REQUIRED",
    }
)
BOUNDARY_DISPOSITIONS = frozenset({"INCLUDE", "EXCLUDE", "BORDERLINE", "ABSTAIN"})
TERMINAL_LIFECYCLE_STATES = frozenset({"CANCELLED", "DISCONTINUED", "WITHDRAWN", "SUPERSEDED"})
CURRENT_LIFECYCLE_STATES = frozenset({"ANNOUNCED", "IN_DEVELOPMENT", "MANUFACTURING_PRE_DELIVERY", "RELEASED"})
COMMERCIAL_ACCESS_STATES = frozenset(
    {
        "PREORDER_RESERVATION",
        "COMMERCIAL_DIRECT",
        "RESEARCH_USE_SOLD_OR_LICENSED",
        "CLINICAL_COMMERCIAL",
        "INSTITUTIONAL_SERVICE",
    }
)
RESEARCH_ACCESS_STATES = frozenset({"RESEARCH_USE_SOLD_OR_LICENSED", "TRIAL_INVESTIGATIONAL"})
EXTERNAL_ACCESS_STATES = frozenset(
    {
        "PREORDER_RESERVATION",
        "COMMERCIAL_DIRECT",
        "RESEARCH_USE_SOLD_OR_LICENSED",
        "CLINICAL_COMMERCIAL",
        "TRIAL_INVESTIGATIONAL",
        "INSTITUTIONAL_SERVICE",
    }
)
DOCUMENTED_DEPLOYMENT_STATES = frozenset(
    {
        "TRIAL_USE",
        "RESEARCH_DEPLOYMENT",
        "DOCUMENTED_CLINICAL_DEPLOYMENT",
        "DOCUMENTED_CONSUMER_ACCESS",
        "DOCUMENTED_WORKPLACE_INSTITUTIONAL_DEPLOYMENT",
    }
)

POPULATION_VIEWS = frozenset(
    {
        "A-P1",
        "A-P2",
        "A-P3",
        "A-P4",
        "A-P5",
        "A-P6",
        "A-P7",
        "A-P8",
    }
)

REGISTRY_BOUNDARY = (
    "Product-registry rows are deterministic analytical projections over canonical PRODUCT and SYSTEM identities. "
    "They do not create canonical identity, product effectiveness, commercial success, regulatory authorization, "
    "deployment, market share, or global completeness by themselves."
)


class ProductRegistryError(ValueError):
    """Raised when a product-registry projection violates the frozen P0.1 semantics."""


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any, schema_name: str) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def registry_row_id(row: Mapping[str, Any]) -> str:
    """Return the deterministic analytical row key required by P0.1.

    The key binds the projected subject, offering/configuration binding,
    jurisdiction scope, cutoff pair, and projection version. It is never a
    canonical PRODUCT or SYSTEM identifier.
    """

    configuration_marker = row.get("configuration_system_id")
    if configuration_marker is None:
        configuration_marker = f"CONFIGURATION:{row.get('configuration_coverage_state')}"
    material = {
        "canonical_entity_id": row.get("canonical_entity_id"),
        "product_offering_id": row.get("product_offering_id"),
        "configuration_system_id": configuration_marker,
        "jurisdiction_scope": row.get("jurisdiction_scope"),
        "world_time_cutoff": row.get("world_time_cutoff"),
        "knowledge_time_cutoff": row.get("knowledge_time_cutoff"),
        "registry_projection_version": row.get("registry_projection_version"),
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "PRR-" + hashlib.sha256(encoded).hexdigest()


def validate_product_registry_row(row: Mapping[str, Any]) -> None:
    errors = _schema_errors(row, ROW_SCHEMA)
    if errors:
        raise ProductRegistryError("Product registry row schema validation failed: " + "; ".join(errors))

    for field, expected in (
        ("registry_projection_version", REGISTRY_PROJECTION_VERSION),
        ("boundary_contract_id", BOUNDARY_CONTRACT_ID),
        ("boundary_contract_semantic_blob", BOUNDARY_CONTRACT_SEMANTIC_BLOB),
        ("reference_standard_id", REFERENCE_STANDARD_ID),
        ("reference_standard_version", REFERENCE_STANDARD_VERSION),
        ("reference_standard_validation_state", REFERENCE_STANDARD_VALIDATION_STATE),
        ("currentness_policy_id", CURRENTNESS_POLICY_ID),
        ("population_view_policy_id", POPULATION_VIEW_POLICY_ID),
    ):
        if row.get(field) != expected:
            raise ProductRegistryError(f"{field} must be {expected!r}")

    if row.get("registry_row_id") != registry_row_id(row):
        raise ProductRegistryError("registry_row_id does not match the deterministic projection key")

    identity_level = row.get("identity_level")
    entity_type = row.get("canonical_entity_type")
    canonical_id = row.get("canonical_entity_id")
    family_id = row.get("product_family_id")
    offering_id = row.get("product_offering_id")
    configuration_id = row.get("configuration_system_id")
    configuration_state = row.get("configuration_coverage_state")

    if identity_level not in IDENTITY_LEVELS:
        raise ProductRegistryError("Unknown identity_level")
    if identity_level in {"FAMILY", "OFFERING"} and entity_type != "PRODUCT":
        raise ProductRegistryError(f"{identity_level} rows must project canonical PRODUCT identities")
    if identity_level == "CONFIGURATION" and entity_type != "SYSTEM":
        raise ProductRegistryError("CONFIGURATION rows must project canonical SYSTEM identities")

    if identity_level == "FAMILY":
        if family_id != canonical_id:
            raise ProductRegistryError("FAMILY row product_family_id must equal canonical_entity_id")
        if offering_id is not None or configuration_id is not None or configuration_state != "NOT_APPLICABLE":
            raise ProductRegistryError("FAMILY rows cannot silently bind offering/configuration identities")
    elif identity_level == "OFFERING":
        if offering_id != canonical_id:
            raise ProductRegistryError("OFFERING row product_offering_id must equal canonical_entity_id")
        if configuration_state == "RESOLVED" and not isinstance(configuration_id, str):
            raise ProductRegistryError("Resolved offering configuration requires configuration_system_id")
        if configuration_state in {"UNRESOLVED", "NOT_APPLICABLE"} and configuration_id is not None:
            raise ProductRegistryError("Unresolved/not-applicable configuration must not carry configuration_system_id")
    else:
        if configuration_id != canonical_id:
            raise ProductRegistryError("CONFIGURATION row configuration_system_id must equal canonical_entity_id")
        if not isinstance(offering_id, str) or not offering_id:
            raise ProductRegistryError("CONFIGURATION row requires a parent product_offering_id")
        if configuration_state != "RESOLVED":
            raise ProductRegistryError("CONFIGURATION row must have RESOLVED configuration coverage")
        if row.get("system_or_offering_role") != "PRODUCT_CONFIGURATION":
            raise ProductRegistryError("CONFIGURATION row system_or_offering_role must be PRODUCT_CONFIGURATION")

    if row.get("primary_enumeration_role") not in ENUMERATION_ROLES:
        raise ProductRegistryError("Unknown primary_enumeration_role")
    if row.get("boundary_disposition") not in BOUNDARY_DISPOSITIONS:
        raise ProductRegistryError("Unknown boundary_disposition")

    identity_state = row.get("identity_state")
    if identity_state == "RESOLVED" and not row.get("source_observation_refs"):
        raise ProductRegistryError("Resolved identity requires source_observation_refs")
    if row.get("boundary_disposition") == "INCLUDE" and not row.get("boundary_disposition_ref"):
        raise ProductRegistryError("INCLUDE requires boundary_disposition_ref")

    lifecycle = row.get("lifecycle_state")
    currentness = row.get("currentness_state")
    if lifecycle in TERMINAL_LIFECYCLE_STATES and currentness == "CURRENT":
        raise ProductRegistryError("Terminal lifecycle state cannot be CURRENT in the offering-currentness projection")
    if lifecycle == "UNRESOLVED" and currentness != "UNRESOLVED":
        raise ProductRegistryError("UNRESOLVED lifecycle requires UNRESOLVED currentness")

    first_observed = row.get("first_observed_at")
    last_observed = row.get("last_observed_at")
    if first_observed is not None and last_observed is not None and first_observed > last_observed:
        raise ProductRegistryError("first_observed_at cannot be later than last_observed_at")


def validate_product_registry(registry: Mapping[str, Any]) -> None:
    errors = _schema_errors(registry, REGISTRY_SCHEMA)
    if errors:
        raise ProductRegistryError("Product registry schema validation failed: " + "; ".join(errors))

    rows = registry.get("rows")
    if not isinstance(rows, list):
        raise ProductRegistryError("rows must be a list")

    seen_row_ids: set[str] = set()
    projection_tuples: set[tuple[Any, ...]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ProductRegistryError("Every registry row must be an object")
        validate_product_registry_row(row)
        row_id = str(row["registry_row_id"])
        if row_id in seen_row_ids:
            raise ProductRegistryError(f"Duplicate registry_row_id: {row_id}")
        seen_row_ids.add(row_id)
        projection_tuple = (
            row.get("canonical_entity_id"),
            row.get("product_offering_id"),
            row.get("configuration_system_id"),
            row.get("configuration_coverage_state"),
            row.get("jurisdiction_scope"),
            row.get("world_time_cutoff"),
            row.get("knowledge_time_cutoff"),
            row.get("registry_projection_version"),
        )
        if projection_tuple in projection_tuples:
            raise ProductRegistryError("Duplicate analytical projection tuple")
        projection_tuples.add(projection_tuple)

    declared = registry.get("metadata", {}).get("row_count")
    if declared != len(rows):
        raise ProductRegistryError(f"metadata.row_count={declared!r} does not match observed row count {len(rows)}")


def _base_offering_eligible(row: Mapping[str, Any]) -> bool:
    return (
        row.get("canonical_entity_type") == "PRODUCT"
        and row.get("identity_level") == "OFFERING"
        and row.get("identity_state") == "RESOLVED"
        and row.get("boundary_disposition") == "INCLUDE"
        and row.get("currentness_state") == "CURRENT"
        and row.get("lifecycle_state") in CURRENT_LIFECYCLE_STATES
        and row.get("primary_enumeration_role") in ENUMERATION_ROLES - {"UNRESOLVED", "OTHER_REVIEW_REQUIRED"}
        and bool(row.get("boundary_disposition_ref"))
        and bool(row.get("source_observation_refs"))
    )


def row_qualifies_for_population_view(row: Mapping[str, Any], view_id: str) -> bool:
    """Apply a v1.0 single-row predicate for A-P1 through A-P7.

    A-P8 requires registry context because a configuration must be associated
    with a qualifying current offering. Use population_view_identity_ids().
    """

    if view_id not in POPULATION_VIEWS:
        raise ProductRegistryError(f"Unknown population view {view_id!r}")
    if view_id == "A-P8":
        raise ProductRegistryError("A-P8 requires registry context; use population_view_identity_ids")

    if view_id == "A-P5":
        return (
            row.get("canonical_entity_type") == "PRODUCT"
            and row.get("identity_level") == "OFFERING"
            and row.get("identity_state") == "RESOLVED"
            and row.get("boundary_disposition") == "INCLUDE"
            and bool(row.get("source_observation_refs"))
        )

    if view_id == "A-P7":
        return (
            row.get("canonical_entity_type") == "PRODUCT"
            and row.get("identity_level") == "OFFERING"
            and row.get("identity_state") == "RESOLVED"
            and row.get("boundary_disposition") == "INCLUDE"
            and row.get("lifecycle_state") in {"DISCONTINUED", "WITHDRAWN", "SUPERSEDED"}
            and row.get("deployment_state") in DOCUMENTED_DEPLOYMENT_STATES
            and bool(row.get("source_observation_refs"))
        )

    if not _base_offering_eligible(row):
        return False
    if view_id == "A-P1":
        return True
    if view_id == "A-P2":
        return row.get("access_commercial_state") in COMMERCIAL_ACCESS_STATES
    if view_id == "A-P3":
        return row.get("access_commercial_state") in RESEARCH_ACCESS_STATES
    if view_id == "A-P4":
        return row.get("primary_enumeration_role") == "INTEGRATED_SYSTEM"
    if view_id == "A-P6":
        return (
            row.get("access_commercial_state") in EXTERNAL_ACCESS_STATES
            or row.get("deployment_state") in DOCUMENTED_DEPLOYMENT_STATES
        )
    raise AssertionError(f"Unhandled population view {view_id}")


def population_view_identity_ids(rows: Sequence[Mapping[str, Any]], view_id: str) -> set[str]:
    """Return unique canonical identities qualifying for a declared population view."""

    if view_id not in POPULATION_VIEWS:
        raise ProductRegistryError(f"Unknown population view {view_id!r}")

    if view_id != "A-P8":
        return {str(row["canonical_entity_id"]) for row in rows if row_qualifies_for_population_view(row, view_id)}

    offering_rows: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in rows:
        if row.get("identity_level") != "OFFERING":
            continue
        key = (
            row.get("product_offering_id"),
            row.get("jurisdiction_scope"),
            row.get("world_time_cutoff"),
            row.get("knowledge_time_cutoff"),
            row.get("registry_projection_version"),
        )
        offering_rows[key] = row

    result: set[str] = set()
    for row in rows:
        if (
            row.get("canonical_entity_type") != "SYSTEM"
            or row.get("identity_level") != "CONFIGURATION"
            or row.get("system_or_offering_role") != "PRODUCT_CONFIGURATION"
            or row.get("identity_state") != "RESOLVED"
            or row.get("boundary_disposition") != "INCLUDE"
            or row.get("currentness_state") != "CURRENT"
        ):
            continue
        key = (
            row.get("product_offering_id"),
            row.get("jurisdiction_scope"),
            row.get("world_time_cutoff"),
            row.get("knowledge_time_cutoff"),
            row.get("registry_projection_version"),
        )
        parent = offering_rows.get(key)
        if parent is not None and _base_offering_eligible(parent):
            result.add(str(row["canonical_entity_id"]))
    return result
