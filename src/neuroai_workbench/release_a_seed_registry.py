from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.observatory_graph import validate_graph_object
from neuroai_workbench.product_registry import (
    BOUNDARY_CONTRACT_ID,
    CURRENTNESS_POLICY_ID,
    POPULATION_VIEW_POLICY_ID,
    REFERENCE_STANDARD_ID,
    REGISTRY_BOUNDARY,
    REGISTRY_PROJECTION_VERSION,
    ProductRegistryError,
    registry_row_id,
    validate_product_registry,
    validate_product_registry_row,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.product_registry"
SEED_MANIFEST_SCHEMA = "RELEASE_A_SEED_INPUT_MANIFEST.schema.json"
SEED_EVIDENCE_PACKET_RESOURCE = "RELEASE_A_SEED_EVIDENCE_PACKET.v1.0.json"
SEED_INPUT_MANIFEST_RESOURCE = "RELEASE_A_SEED_INPUT_MANIFEST.v1.0.json"
SEED_PRODUCT_REGISTRY_RESOURCE = "RELEASE_A_SEED_PRODUCT_REGISTRY.v1.0.json"
PRODUCT_IDENTITY_REGISTRY_RESOURCE = "RELEASE_A_PRODUCT_IDENTITY_REGISTRY.v1.0.json"
SEED_IDENTITY_BINDING_RESOURCE = "RELEASE_A_SEED_IDENTITY_BINDING.v1.0.json"

SEED_MANIFEST_VERSION = "RELEASE_A_SEED_INPUT_MANIFEST_v1.0"
PRODUCT_IDENTITY_REGISTRY_ID = "RELEASE_A_PRODUCT_IDENTITY_REGISTRY_v1.0"
SEED_IDENTITY_BINDING_VERSION = "RELEASE_A_SEED_IDENTITY_BINDING_v1.0"
OBSERVATORY_DATA_REPO = "fraware/neuroai-observatory-data"
SEED_EVIDENCE_BASIS = "EXACT_PRODUCT_OR_SERVICE_EVIDENCE"

SEED_REGISTRY_BOUNDARY = (
    "Release-A seed assembly admits only resolved INCLUDE exact-product/service evidence at the frozen "
    "PRODUCT_REGISTRY_v1.0 grain. Organization records and broad family mentions may seed discovery but cannot "
    "be converted mechanically into product rows. Seed-registry composition is not a global product count."
)

PRODUCT_IDENTITY_BOUNDARY = (
    "Release-A product identity allocation establishes canonical PRODUCT identity only for the exact source-bound "
    "OFFERING labels in this registry. It does not establish scope inclusion, currentness, commercialization, "
    "deployment, regulatory status, effectiveness, market importance, or global completeness."
)

SEED_IDENTITY_BINDING_BOUNDARY = (
    "This successor binding demonstrates that every canonical PRODUCT/OFFERING ID used by the A1 seed Product "
    "Registry is separately materialized in the controlled product identity registry. It does not change product "
    "scope, state, count, or publication authority."
)


class ReleaseASeedRegistryError(ValueError):
    """Raised when Release-A seed-registry inputs violate the A1 evidence boundary."""


def _resource_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def seed_evidence_packet_sha256(packet: Mapping[str, Any]) -> str:
    """Return the canonical JSON digest used to bind the repository-safe A1 evidence packet."""

    encoded = json.dumps(
        packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def product_identity_registry_sha256(registry: Mapping[str, Any]) -> str:
    """Return the canonical digest of the controlled Release-A product identity registry."""

    validate_product_identity_registry(registry)
    return _canonical_sha256(registry)


def seed_identity_binding_id(binding: Mapping[str, Any]) -> str:
    """Return the deterministic identity of one A1 seed-to-identity authority binding."""

    material = {key: value for key, value in binding.items() if key != "binding_id"}
    return "RAIB-" + _canonical_sha256(material)


def validate_product_identity_registry(registry: Mapping[str, Any]) -> None:
    """Validate the canonical PRODUCT/OFFERING identities backing the A1 seed projection."""

    if registry.get("registry_id") != PRODUCT_IDENTITY_REGISTRY_ID:
        raise ReleaseASeedRegistryError(f"identity registry_id must be {PRODUCT_IDENTITY_REGISTRY_ID}")
    if registry.get("version") != "1.0" or registry.get("status") != "FROZEN_v1.0":
        raise ReleaseASeedRegistryError("Product identity registry must be frozen v1.0")
    if registry.get("identity_unit") != "PRODUCT/OFFERING":
        raise ReleaseASeedRegistryError("Product identity registry must use PRODUCT/OFFERING as its identity unit")
    if registry.get("boundary") != PRODUCT_IDENTITY_BOUNDARY:
        raise ReleaseASeedRegistryError(
            "Product identity registry boundary does not match the frozen identity boundary"
        )

    records = registry.get("records")
    if not isinstance(records, list) or not records:
        raise ReleaseASeedRegistryError("Product identity registry records must be a non-empty list")
    if int(registry.get("record_count", -1)) != len(records):
        raise ReleaseASeedRegistryError("Product identity registry record_count does not match records")

    entity_ids: set[str] = set()
    row_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ReleaseASeedRegistryError("Product identity registry records must be objects")
        entity = record.get("entity")
        if not isinstance(entity, Mapping):
            raise ReleaseASeedRegistryError("Product identity registry record requires an Entity object")
        schema_errors = validate_graph_object(dict(entity), "Entity")
        if schema_errors:
            raise ReleaseASeedRegistryError(
                "Product identity Entity schema validation failed: " + "; ".join(schema_errors)
            )
        entity_id = str(entity.get("entity_id", "")).strip()
        if entity.get("entity_type") != "PRODUCT" or not entity_id.startswith("PRD-"):
            raise ReleaseASeedRegistryError("A1 canonical identities must be PRODUCT entities with PRD- IDs")
        if entity.get("status") != "ACTIVE":
            raise ReleaseASeedRegistryError("A1 canonical product identities must be ACTIVE")
        if entity.get("boundary") != PRODUCT_IDENTITY_BOUNDARY:
            raise ReleaseASeedRegistryError("A1 product Entity boundary does not match the identity registry boundary")
        if entity_id in entity_ids:
            raise ReleaseASeedRegistryError(f"Duplicate canonical product entity_id: {entity_id}")
        entity_ids.add(entity_id)

        if record.get("product_identity_level") != "OFFERING" or record.get("allocation_state") != "ALLOCATED":
            raise ReleaseASeedRegistryError("A1 product identities must be allocated at OFFERING level")
        source_refs = record.get("source_observation_refs")
        if not isinstance(source_refs, list) or not source_refs or any(not str(ref).strip() for ref in source_refs):
            raise ReleaseASeedRegistryError("A1 product identity allocation requires source_observation_refs")
        row_id = str(record.get("seed_registry_row_id", "")).strip()
        if not row_id or row_id in row_ids:
            raise ReleaseASeedRegistryError("A1 product identity allocation requires unique seed_registry_row_id")
        row_ids.add(row_id)


def validate_seed_identity_binding(
    binding: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    registry: Mapping[str, Any],
    identity_registry: Mapping[str, Any],
) -> None:
    """Validate the immutable successor binding from A1 seed projection to canonical identities."""

    validate_seed_input_manifest(manifest)
    try:
        validate_product_registry(registry)
    except ProductRegistryError as exc:
        raise ReleaseASeedRegistryError(str(exc)) from exc
    validate_product_identity_registry(identity_registry)

    if binding.get("binding_version") != SEED_IDENTITY_BINDING_VERSION:
        raise ReleaseASeedRegistryError(f"binding_version must be {SEED_IDENTITY_BINDING_VERSION}")
    if binding.get("status") != "FROZEN_v1.0":
        raise ReleaseASeedRegistryError("Seed identity binding must be FROZEN_v1.0")
    if binding.get("boundary") != SEED_IDENTITY_BINDING_BOUNDARY:
        raise ReleaseASeedRegistryError("Seed identity binding boundary does not match the frozen boundary")
    if binding.get("binding_id") != seed_identity_binding_id(binding):
        raise ReleaseASeedRegistryError("Seed identity binding_id does not match deterministic identity")
    if binding.get("seed_manifest_id") != manifest.get("manifest_id"):
        raise ReleaseASeedRegistryError("Seed identity binding does not bind the exact A1 seed manifest")
    if binding.get("seed_registry_sha256") != seed_registry_sha256(registry):
        raise ReleaseASeedRegistryError("Seed identity binding does not bind the exact A1 seed registry digest")
    if binding.get("identity_registry_id") != identity_registry.get("registry_id"):
        raise ReleaseASeedRegistryError("Seed identity binding does not bind the exact product identity registry")
    if binding.get("identity_registry_sha256") != product_identity_registry_sha256(identity_registry):
        raise ReleaseASeedRegistryError("Seed identity binding product identity registry digest mismatch")

    identity_records = cast(Sequence[Mapping[str, Any]], identity_registry["records"])
    identity_by_id = {
        str(cast(Mapping[str, Any], record["entity"])["entity_id"]): record for record in identity_records
    }
    seed_bindings = cast(Sequence[Mapping[str, Any]], manifest["bindings"])
    seed_entity_ids = {str(item["canonical_entity_id"]) for item in seed_bindings}
    declared_entity_ids = {str(value) for value in cast(Sequence[str], binding.get("entity_ids", []))}
    if declared_entity_ids != seed_entity_ids or set(identity_by_id) != seed_entity_ids:
        raise ReleaseASeedRegistryError("Seed identity authority must cover exactly the A1 canonical entity set")

    rows_by_id = {str(row["registry_row_id"]): row for row in cast(Sequence[Mapping[str, Any]], registry["rows"])}
    binding_by_entity = {str(item["canonical_entity_id"]): item for item in seed_bindings}
    for entity_id, identity_record in identity_by_id.items():
        seed_binding = binding_by_entity[entity_id]
        entity = cast(Mapping[str, Any], identity_record["entity"])
        if str(entity.get("canonical_label", "")).strip() != str(seed_binding["exact_product_label"]).strip():
            raise ReleaseASeedRegistryError("Canonical product identity label does not match A1 exact product label")
        if set(cast(Sequence[str], identity_record["source_observation_refs"])) != set(
            cast(Sequence[str], seed_binding["source_observation_refs"])
        ):
            raise ReleaseASeedRegistryError("Canonical product identity evidence does not match A1 seed evidence")
        row_id = str(identity_record["seed_registry_row_id"])
        if row_id != str(seed_binding["registry_row_id"]) or row_id not in rows_by_id:
            raise ReleaseASeedRegistryError("Canonical product identity does not bind the exact A1 seed registry row")
        if str(rows_by_id[row_id]["canonical_entity_id"]) != entity_id:
            raise ReleaseASeedRegistryError(
                "A1 seed registry row canonical_entity_id lacks matching identity authority"
            )


def _parse_bound_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseASeedRegistryError(f"{field} requires a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseASeedRegistryError(f"{field} must be a valid offset-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseASeedRegistryError(f"{field} must include an explicit timezone")
    return parsed


def load_default_seed_artifacts() -> dict[str, Any]:
    """Load and cross-validate the substantive Release-A A1 seed artifacts."""

    packet = _resource_json(SEED_EVIDENCE_PACKET_RESOURCE)
    manifest = _resource_json(SEED_INPUT_MANIFEST_RESOURCE)
    registry = _resource_json(SEED_PRODUCT_REGISTRY_RESOURCE)
    identity_registry = _resource_json(PRODUCT_IDENTITY_REGISTRY_RESOURCE)
    identity_binding = _resource_json(SEED_IDENTITY_BINDING_RESOURCE)

    validate_seed_input_manifest(manifest)
    try:
        validate_product_registry(registry)
    except ProductRegistryError as exc:
        raise ReleaseASeedRegistryError(str(exc)) from exc

    packet_digest = seed_evidence_packet_sha256(packet)
    if packet_digest not in set(cast(list[str], manifest["controlled_packet_digests"])):
        raise ReleaseASeedRegistryError("Default A1 evidence packet digest is not bound by the seed input manifest")

    observations = packet.get("observations")
    assertions = packet.get("assertions")
    if not isinstance(observations, list) or not isinstance(assertions, list):
        raise ReleaseASeedRegistryError("Default A1 evidence packet requires observation and assertion lists")

    observation_index: dict[str, Mapping[str, Any]] = {}
    for item in observations:
        if not isinstance(item, Mapping):
            raise ReleaseASeedRegistryError("Default A1 evidence packet observations must be objects")
        observation_id = str(item.get("observation_id", "")).strip()
        if not observation_id or observation_id in observation_index:
            raise ReleaseASeedRegistryError("Default A1 evidence packet contains missing or duplicate observation IDs")
        registered_at = _parse_bound_timestamp(
            item.get("observation_registered_at"),
            field=f"Observation {observation_id} observation_registered_at",
        )
        knowledge_cutoff = _parse_bound_timestamp(
            manifest["knowledge_time_cutoff"],
            field="Seed manifest knowledge_time_cutoff",
        )
        if registered_at > knowledge_cutoff:
            raise ReleaseASeedRegistryError(
                f"Observation {observation_id} registration cannot exceed the seed knowledge-time cutoff"
            )
        observation_index[observation_id] = item

    assertion_index: dict[str, Mapping[str, Any]] = {}
    for item in assertions:
        if not isinstance(item, Mapping):
            raise ReleaseASeedRegistryError("Default A1 evidence packet assertions must be objects")
        assertion_id = str(item.get("assertion_id", "")).strip()
        if not assertion_id or assertion_id in assertion_index:
            raise ReleaseASeedRegistryError("Default A1 evidence packet contains missing or duplicate assertion IDs")
        source_refs = item.get("source_observation_refs")
        if not isinstance(source_refs, list) or not source_refs:
            raise ReleaseASeedRegistryError("Default A1 projected assertions require source_observation_refs")
        missing_observations = {str(ref) for ref in source_refs} - set(observation_index)
        if missing_observations:
            raise ReleaseASeedRegistryError(
                "Default A1 projected assertion references unknown source observations: "
                + ", ".join(sorted(missing_observations))
            )
        assertion_index[assertion_id] = item

    observation_ids = set(observation_index)
    assertion_ids = set(assertion_index)
    if seed_evidence_index_sha256(observation_ids, assertion_ids) != manifest["evidence_index_sha256"]:
        raise ReleaseASeedRegistryError("Default A1 evidence identity index does not match the seed input manifest")
    if packet.get("knowledge_time_cutoff") != manifest["knowledge_time_cutoff"]:
        raise ReleaseASeedRegistryError("Default A1 evidence packet knowledge cutoff does not match the seed manifest")

    registry_rows_by_id = {
        str(row["registry_row_id"]): row for row in cast(Sequence[Mapping[str, Any]], registry["rows"])
    }
    for binding in cast(Sequence[Mapping[str, Any]], manifest["bindings"]):
        canonical_entity_id = str(binding["canonical_entity_id"])
        exact_product_label = str(binding["exact_product_label"])
        binding_observation_refs = {str(ref) for ref in cast(Sequence[str], binding["source_observation_refs"])}
        for observation_ref in binding_observation_refs:
            observation = observation_index.get(observation_ref)
            if observation is None:
                continue
            if str(observation.get("exact_product_label", "")).strip() != exact_product_label:
                raise ReleaseASeedRegistryError(
                    "Seed binding exact product label does not match its source observation"
                )
        for assertion_ref in cast(Sequence[str], binding["projected_assertion_refs"]):
            assertion = assertion_index.get(str(assertion_ref))
            if assertion is None:
                continue
            if str(assertion.get("canonical_entity_id", "")).strip() != canonical_entity_id:
                raise ReleaseASeedRegistryError("Seed binding canonical entity does not match its projected assertion")
            assertion_source_refs = {
                str(ref) for ref in cast(Sequence[str], assertion.get("source_observation_refs", []))
            }
            if not assertion_source_refs <= binding_observation_refs:
                raise ReleaseASeedRegistryError(
                    "Seed binding does not bind every source observation used by its projected assertion"
                )

        row = registry_rows_by_id.get(str(binding["registry_row_id"]))
        if row is None:
            continue
        bound_registration_times = sorted(
            _parse_bound_timestamp(
                observation_index[observation_ref]["observation_registered_at"],
                field=f"Observation {observation_ref} observation_registered_at",
            )
            for observation_ref in binding_observation_refs
            if observation_ref in observation_index
        )
        if not bound_registration_times:
            raise ReleaseASeedRegistryError("Seed binding requires at least one attributable observation registration")
        first_observed_at = _parse_bound_timestamp(
            row.get("first_observed_at"),
            field=f"Seed row {row['registry_row_id']} first_observed_at",
        )
        last_observed_at = _parse_bound_timestamp(
            row.get("last_observed_at"),
            field=f"Seed row {row['registry_row_id']} last_observed_at",
        )
        if first_observed_at != bound_registration_times[0] or last_observed_at != bound_registration_times[-1]:
            raise ReleaseASeedRegistryError(
                "Seed registry observation chronology does not match its bound observation registrations"
            )

    rebuilt = build_seed_product_registry(
        cast(Sequence[Mapping[str, Any]], registry["rows"]),
        manifest,
        known_observation_ids=observation_ids,
        known_assertion_ids=assertion_ids,
    )
    if rebuilt != registry:
        raise ReleaseASeedRegistryError(
            "Materialized A1 seed Product Registry does not match deterministic compiler output"
        )

    validate_seed_identity_binding(
        identity_binding,
        manifest=manifest,
        registry=registry,
        identity_registry=identity_registry,
    )

    return {
        "packet": packet,
        "manifest": manifest,
        "registry": registry,
        "identity_registry": identity_registry,
        "identity_binding": identity_binding,
        "packet_sha256": packet_digest,
        "evidence_index_sha256": manifest["evidence_index_sha256"],
        "registry_sha256": seed_registry_sha256(registry),
        "identity_registry_sha256": product_identity_registry_sha256(identity_registry),
        "identity_binding_id": identity_binding["binding_id"],
    }


def _manifest_schema() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(SEED_MANIFEST_SCHEMA).read_text(encoding="utf-8")),
    )


def _manifest_schema_errors(value: Any) -> list[str]:
    validator = Draft202012Validator(_manifest_schema())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _canonical_manifest_material(manifest: Mapping[str, Any]) -> dict[str, Any]:
    bindings = []
    for raw in cast(Sequence[Mapping[str, Any]], manifest.get("bindings", [])):
        binding = dict(raw)
        for field in ("source_observation_refs", "projected_assertion_refs", "organization_seed_refs"):
            binding[field] = sorted(cast(list[str], binding.get(field, [])))
        bindings.append(binding)
    bindings.sort(key=lambda item: (str(item.get("registry_row_id")), str(item.get("canonical_entity_id"))))

    return {
        "manifest_version": manifest.get("manifest_version"),
        "registry_projection_version": manifest.get("registry_projection_version"),
        "workbench_baseline_sha": manifest.get("workbench_baseline_sha"),
        "observatory_data_repo": manifest.get("observatory_data_repo"),
        "observatory_data_commit": manifest.get("observatory_data_commit"),
        "observatory_release_refs": sorted(cast(list[str], manifest.get("observatory_release_refs", []))),
        "controlled_packet_digests": sorted(cast(list[str], manifest.get("controlled_packet_digests", []))),
        "evidence_index_sha256": manifest.get("evidence_index_sha256"),
        "world_time_cutoff": manifest.get("world_time_cutoff"),
        "knowledge_time_cutoff": manifest.get("knowledge_time_cutoff"),
        "jurisdiction_scope": manifest.get("jurisdiction_scope"),
        "seed_input_count": manifest.get("seed_input_count"),
        "bindings": bindings,
        "boundary": manifest.get("boundary"),
    }


def seed_evidence_index_sha256(
    observation_ids: Iterable[str],
    assertion_ids: Iterable[str],
) -> str:
    """Return a deterministic digest over the exact evidence-record identity index."""

    material = {
        "observation_ids": sorted({str(value) for value in observation_ids}),
        "assertion_ids": sorted({str(value) for value in assertion_ids}),
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def seed_input_manifest_id(manifest: Mapping[str, Any]) -> str:
    """Return the deterministic identity of one exact Release-A seed input manifest."""

    encoded = json.dumps(
        _canonical_manifest_material(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "RASIM-" + hashlib.sha256(encoded).hexdigest()


def validate_seed_input_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate immutable A1 source-state and exact-product evidence bindings."""

    errors = _manifest_schema_errors(manifest)
    if errors:
        raise ReleaseASeedRegistryError("Release-A seed input manifest schema validation failed: " + "; ".join(errors))

    if manifest["manifest_version"] != SEED_MANIFEST_VERSION:
        raise ReleaseASeedRegistryError(f"manifest_version must be {SEED_MANIFEST_VERSION}")
    if manifest["registry_projection_version"] != REGISTRY_PROJECTION_VERSION:
        raise ReleaseASeedRegistryError(f"registry_projection_version must be {REGISTRY_PROJECTION_VERSION}")
    if manifest["observatory_data_repo"] != OBSERVATORY_DATA_REPO:
        raise ReleaseASeedRegistryError(f"observatory_data_repo must be {OBSERVATORY_DATA_REPO}")
    if manifest["boundary"] != SEED_REGISTRY_BOUNDARY:
        raise ReleaseASeedRegistryError("Seed input manifest boundary does not match the frozen A1 boundary")
    if manifest["manifest_id"] != seed_input_manifest_id(manifest):
        raise ReleaseASeedRegistryError("manifest_id does not match the deterministic seed-input identity")

    bindings = cast(list[Mapping[str, Any]], manifest["bindings"])
    if int(manifest["seed_input_count"]) != len(bindings):
        raise ReleaseASeedRegistryError("seed_input_count does not match the number of exact-product bindings")

    row_ids: set[str] = set()
    for binding in bindings:
        row_id = str(binding["registry_row_id"])
        if row_id in row_ids:
            raise ReleaseASeedRegistryError(f"Duplicate seed registry_row_id binding: {row_id}")
        row_ids.add(row_id)
        if binding["evidence_basis"] != SEED_EVIDENCE_BASIS:
            raise ReleaseASeedRegistryError("Organization-only or generic evidence cannot be a seed product-row basis")


def _binding_map(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(binding["registry_row_id"]): binding for binding in cast(list[Mapping[str, Any]], manifest["bindings"])}


def _validate_seed_row(
    row: Mapping[str, Any],
    binding: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    try:
        validate_product_registry_row(row)
    except ProductRegistryError as exc:
        raise ReleaseASeedRegistryError(str(exc)) from exc

    if row["registry_row_id"] != registry_row_id(row):
        raise ReleaseASeedRegistryError("Seed row registry_row_id is not deterministic")
    if row["identity_level"] == "FAMILY":
        raise ReleaseASeedRegistryError(
            "Family-only records are not admissible in the high-confidence A1 seed registry"
        )
    if row["identity_state"] != "RESOLVED":
        raise ReleaseASeedRegistryError("A1 seed rows require resolved exact identity")
    if row["boundary_disposition"] != "INCLUDE":
        raise ReleaseASeedRegistryError("A1 seed rows require INCLUDE boundary disposition")
    if row["primary_enumeration_role"] in {"UNRESOLVED", "OTHER_REVIEW_REQUIRED"}:
        raise ReleaseASeedRegistryError("A1 seed rows require a resolved primary enumeration role")
    if not row["projected_assertion_refs"]:
        raise ReleaseASeedRegistryError("A1 seed rows require exact-product assertion references")
    if not row["source_observation_refs"]:
        raise ReleaseASeedRegistryError("A1 seed rows require source observation references")
    if not row["evidence_state"] or set(cast(list[str], row["evidence_state"])) == {"UNRESOLVED"}:
        raise ReleaseASeedRegistryError("A1 seed rows require substantive evidence state")

    for field in ("world_time_cutoff", "knowledge_time_cutoff", "jurisdiction_scope"):
        if row[field] != manifest[field]:
            raise ReleaseASeedRegistryError(f"Seed row {field} does not match its immutable input manifest")

    if binding["canonical_entity_id"] != row["canonical_entity_id"]:
        raise ReleaseASeedRegistryError("Seed binding canonical_entity_id does not match the registry row")
    if set(cast(list[str], binding["source_observation_refs"])) != set(cast(list[str], row["source_observation_refs"])):
        raise ReleaseASeedRegistryError("Seed binding source observations do not exactly match the registry row")
    if set(cast(list[str], binding["projected_assertion_refs"])) != set(
        cast(list[str], row["projected_assertion_refs"])
    ):
        raise ReleaseASeedRegistryError("Seed binding assertions do not exactly match the registry row")
    if binding["boundary_disposition_ref"] != row["boundary_disposition_ref"]:
        raise ReleaseASeedRegistryError("Seed binding boundary disposition does not match the registry row")


def build_seed_product_registry(
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    *,
    known_observation_ids: set[str] | None = None,
    known_assertion_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic high-confidence A1 Product Registry from exact-product evidence rows.

    The compiler is intentionally stricter than the generic Product Registry validator. It rejects
    organization-only/family-only/unresolved material and requires exact evidence bindings for every row.
    """

    validate_seed_input_manifest(manifest)

    if known_observation_ids is None or known_assertion_ids is None:
        raise ReleaseASeedRegistryError("Exact evidence identity index is required for A1 seed assembly")
    evidence_index_digest = seed_evidence_index_sha256(known_observation_ids, known_assertion_ids)
    if manifest["evidence_index_sha256"] != evidence_index_digest:
        raise ReleaseASeedRegistryError("Evidence index digest does not match the immutable seed input manifest")

    bindings = _binding_map(manifest)
    referenced_observations = {
        str(ref) for binding in bindings.values() for ref in cast(Sequence[str], binding["source_observation_refs"])
    }
    referenced_assertions = {
        str(ref) for binding in bindings.values() for ref in cast(Sequence[str], binding["projected_assertion_refs"])
    }
    unknown_observations = referenced_observations - known_observation_ids
    if unknown_observations:
        raise ReleaseASeedRegistryError(
            "Seed manifest references unknown source observations: " + ", ".join(sorted(unknown_observations))
        )
    unknown_assertions = referenced_assertions - known_assertion_ids
    if unknown_assertions:
        raise ReleaseASeedRegistryError(
            "Seed manifest references unknown product assertions: " + ", ".join(sorted(unknown_assertions))
        )
    observed_row_ids = {str(row.get("registry_row_id")) for row in rows}
    if observed_row_ids != set(bindings):
        raise ReleaseASeedRegistryError("Seed rows do not exactly match the immutable manifest binding set")
    if len(rows) != len(observed_row_ids):
        raise ReleaseASeedRegistryError("Duplicate seed registry rows are not permitted")

    indexed_by_offering: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _validate_seed_row(row, bindings[str(row["registry_row_id"])], manifest)
        if row["identity_level"] == "OFFERING":
            indexed_by_offering[str(row["product_offering_id"])] = row

    for row in rows:
        if row["identity_level"] != "CONFIGURATION":
            continue
        parent_id = str(row["product_offering_id"])
        parent = indexed_by_offering.get(parent_id)
        if parent is None:
            raise ReleaseASeedRegistryError(
                f"Configuration seed {row['canonical_entity_id']} requires its parent offering row in the same seed registry"
            )
        if parent["boundary_disposition"] != "INCLUDE" or parent["identity_state"] != "RESOLVED":
            raise ReleaseASeedRegistryError("Configuration seed parent offering must be resolved and INCLUDE")

    ordered_rows = [dict(row) for row in sorted(rows, key=lambda item: str(item["registry_row_id"]))]
    registry: dict[str, Any] = {
        "metadata": {
            "title": "Release A high-confidence seed Product Registry",
            "registry_projection_version": REGISTRY_PROJECTION_VERSION,
            "row_count": len(ordered_rows),
            "world_time_cutoff": manifest["world_time_cutoff"],
            "knowledge_time_cutoff": manifest["knowledge_time_cutoff"],
            "jurisdiction_scope": manifest["jurisdiction_scope"],
            "boundary_contract_id": BOUNDARY_CONTRACT_ID,
            "reference_standard_id": REFERENCE_STANDARD_ID,
            "population_view_policy_id": POPULATION_VIEW_POLICY_ID,
            "currentness_policy_id": CURRENTNESS_POLICY_ID,
        },
        "rows": ordered_rows,
        "boundary": REGISTRY_BOUNDARY,
    }
    try:
        validate_product_registry(registry)
    except ProductRegistryError as exc:
        raise ReleaseASeedRegistryError(str(exc)) from exc
    return registry


def seed_registry_sha256(registry: Mapping[str, Any]) -> str:
    """Return the canonical digest of a validated A1 seed Product Registry."""

    try:
        validate_product_registry(registry)
    except ProductRegistryError as exc:
        raise ReleaseASeedRegistryError(str(exc)) from exc
    encoded = json.dumps(
        registry,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
