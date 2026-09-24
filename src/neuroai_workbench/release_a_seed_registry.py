from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

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

SEED_MANIFEST_VERSION = "RELEASE_A_SEED_INPUT_MANIFEST_v1.0"
OBSERVATORY_DATA_REPO = "fraware/neuroai-observatory-data"
SEED_EVIDENCE_BASIS = "EXACT_PRODUCT_OR_SERVICE_EVIDENCE"

SEED_REGISTRY_BOUNDARY = (
    "Release-A seed assembly admits only resolved INCLUDE exact-product/service evidence at the frozen "
    "PRODUCT_REGISTRY_v1.0 grain. Organization records and broad family mentions may seed discovery but cannot "
    "be converted mechanically into product rows. Seed-registry composition is not a global product count."
)


class ReleaseASeedRegistryError(ValueError):
    """Raised when Release-A seed-registry inputs violate the A1 evidence boundary."""


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
        str(ref)
        for binding in bindings.values()
        for ref in cast(Sequence[str], binding["source_observation_refs"])
    }
    referenced_assertions = {
        str(ref)
        for binding in bindings.values()
        for ref in cast(Sequence[str], binding["projected_assertion_refs"])
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
