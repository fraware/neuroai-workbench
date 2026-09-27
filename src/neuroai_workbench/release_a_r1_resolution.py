"""Release-A R1 exact-A2 Product Registry and candidate-resolution ledger.

This module validates the R1.2 corrective analytical inputs without mutating
historical A1/A2/A7/A8/A-G artifacts. Candidate clusters are deterministic
review aids only; they never allocate canonical PRODUCT identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import _packet_content_sha256
from neuroai_workbench.a7_population_estimation import project_capture_record
from neuroai_workbench.product_discovery_frames import (
    A2_JURISDICTION_SCOPE,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    ProductDiscoveryError,
    identity_set_digest,
)
from neuroai_workbench.product_registry import (
    REGISTRY_PROJECTION_VERSION,
    population_view_identity_ids,
    validate_product_registry,
)

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
REGISTRY_RESOURCE_PACKAGE = "neuroai_workbench.resources.product_registry"

R1_PRODUCT_REGISTRY_RESOURCE = "RELEASE_A_R1_PRODUCT_REGISTRY.v1.1.json"
SEED_PRODUCT_REGISTRY_RESOURCE = "RELEASE_A_SEED_PRODUCT_REGISTRY.v1.0.json"
R1_DENOMINATOR_RESOURCE = "RELEASE_A_R1_PRODUCT_DENOMINATOR.v1.0.json"
R1_LEDGER_MANIFEST_RESOURCE = "RELEASE_A_R1_CANDIDATE_RESOLUTION_LEDGER_MANIFEST.v1.0.json"
R1_CLUSTER_LEDGER_RESOURCE = "RELEASE_A_R1_CANDIDATE_RESOLUTION_CLUSTERS.v1.0.json"

R1_PRODUCT_REGISTRY_CANONICAL_SHA256 = "d829de5785254a65e06f12d07059eb8e2b092d43a8ffb4c6a11a34febf1865cf"
R1_DENOMINATOR_SHA256 = "d6b495ce4957e909f29696fb8ea4db44f7b3f346aa673538ad219ee995fcc514"
R1_LEDGER_MANIFEST_SHA256 = "53615e2315649e2569df34f25bbf6e6db0bfd4fdc03acd08c254e3bef7043ac6"
R1_CLUSTER_LEDGER_SHA256 = "f08dee313941fb868744340319e5fb36c401b9ca4d76fbc4171a450d397cf71e"

R1_CLUSTERING_POLICY_ID = "R1_EXACT_NORMALIZED_KEY_NONCANONICAL_CLUSTERING_v1.0"
UNRESOLVED_OUTCOMES = frozenset({"UNRESOLVED_IDENTITY", "BORDERLINE", "ABSTAIN", "FAILED_INACCESSIBLE"})
MARGINAL_YIELD_FRAMES = frozenset({"F1", "F4", "F5", "F6", "F8", "F11"})


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def artifact_sha256(value: Mapping[str, Any], *, digest_field: str) -> str:
    material = {key: item for key, item in value.items() if key != digest_field}
    return canonical_sha256(material)


def _load(package: str, resource: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(package).joinpath(resource).read_text(encoding="utf-8")))


def load_r1_product_registry() -> dict[str, Any]:
    registry = _load(REGISTRY_RESOURCE_PACKAGE, R1_PRODUCT_REGISTRY_RESOURCE)
    validate_r1_product_registry(registry)
    return registry


def validate_r1_product_registry(registry: Mapping[str, Any]) -> None:
    validate_product_registry(registry)
    metadata = cast(Mapping[str, Any], registry["metadata"])
    expected_metadata = {
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "world_time_cutoff": A2_WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": A2_KNOWLEDGE_TIME_CUTOFF,
        "jurisdiction_scope": A2_JURISDICTION_SCOPE,
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            raise ProductDiscoveryError(f"R1 Product Registry metadata.{field} drift")

    if canonical_sha256(registry) != R1_PRODUCT_REGISTRY_CANONICAL_SHA256:
        raise ProductDiscoveryError("R1 Product Registry canonical digest drift")

    seed = _load(REGISTRY_RESOURCE_PACKAGE, SEED_PRODUCT_REGISTRY_RESOURCE)
    validate_product_registry(seed)
    seed_ids = sorted(str(row["canonical_entity_id"]) for row in cast(list[Mapping[str, Any]], seed["rows"]))
    successor_ids = sorted(str(row["canonical_entity_id"]) for row in cast(list[Mapping[str, Any]], registry["rows"]))
    if successor_ids != seed_ids:
        raise ProductDiscoveryError("R1 analytical Product Registry must not allocate or remove canonical identity")


def derive_r1_a_p1_identity_ids(registry: Mapping[str, Any]) -> list[str]:
    validate_r1_product_registry(registry)
    rows = cast(list[Mapping[str, Any]], registry["rows"])
    return sorted(population_view_identity_ids(rows, "A-P1"))


def load_r1_denominator_control() -> dict[str, Any]:
    packet = _load(DISCOVERY_RESOURCE_PACKAGE, R1_DENOMINATOR_RESOURCE)
    validate_r1_denominator_control(packet, load_r1_product_registry())
    return packet


def validate_r1_denominator_control(packet: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    if packet.get("packet_id") != "RELEASE_A_R1_PRODUCT_DENOMINATOR_v1.0":
        raise ProductDiscoveryError("R1 denominator packet_id drift")
    if artifact_sha256(packet, digest_field="packet_sha256") != packet.get("packet_sha256"):
        raise ProductDiscoveryError("R1 denominator packet digest mismatch")
    if packet.get("packet_sha256") != R1_DENOMINATOR_SHA256:
        raise ProductDiscoveryError("R1 denominator frozen digest drift")
    if packet.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("R1 denominator analysis universe drift")
    if packet.get("world_time_cutoff") != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("R1 denominator world-time cutoff drift")
    if packet.get("knowledge_time_cutoff") != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("R1 denominator knowledge-time cutoff drift")
    if packet.get("population_view_id") != "A-P1":
        raise ProductDiscoveryError("R1 denominator population view must be A-P1")
    if packet.get("product_registry_canonical_sha256") != canonical_sha256(registry):
        raise ProductDiscoveryError("R1 denominator does not bind the exact successor Product Registry")

    derived_ids = derive_r1_a_p1_identity_ids(registry)
    if list(packet.get("qualifying_offering_ids", [])) != derived_ids:
        raise ProductDiscoveryError("R1 denominator qualifying IDs must be machine-derived from the successor registry")
    if packet.get("n_observed") != len(derived_ids):
        raise ProductDiscoveryError("R1 denominator n_observed must equal the derived A-P1 identity count")
    if packet.get("a_p1_identity_set_sha256") != identity_set_digest(derived_ids):
        raise ProductDiscoveryError("R1 denominator identity-set digest mismatch")

    nonqualifying = {
        str(row["canonical_entity_id"]): row
        for row in cast(list[Mapping[str, Any]], registry["rows"])
        if str(row["canonical_entity_id"]) not in derived_ids
    }
    declared = cast(list[Mapping[str, Any]], packet.get("nonqualifying_canonical_offerings", []))
    if sorted(str(item.get("canonical_entity_id")) for item in declared) != sorted(nonqualifying):
        raise ProductDiscoveryError("R1 denominator nonqualifying canonical set is incomplete")
    for item in declared:
        cid = str(item["canonical_entity_id"])
        row = nonqualifying[cid]
        if item.get("currentness_state") != row.get("currentness_state"):
            raise ProductDiscoveryError("R1 denominator nonqualifying currentness state drift")
        if item.get("lifecycle_state") != row.get("lifecycle_state"):
            raise ProductDiscoveryError("R1 denominator nonqualifying lifecycle state drift")


def normalize_candidate_key(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip().lower())


def normalized_candidate_label(value: str) -> str:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip())
    if "::" in normalized:
        return normalized.split("::", 1)[1].strip()
    return normalized


def developer_or_organization_label(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip())
    if "::" not in normalized:
        return None
    prefix = normalized.split("::", 1)[0].strip()
    if re.match(r"^F\d+-", prefix):
        return None
    return prefix or None


def candidate_cluster_material(row: Mapping[str, Any]) -> dict[str, Any]:
    canonical_id = row.get("canonical_offering_id")
    if canonical_id:
        return {"cluster_basis": "CANONICAL_OFFERING_ID", "canonical_offering_id": canonical_id}
    return {
        "cluster_basis": "EXACT_NORMALIZED_CANDIDATE_KEY",
        "normalized_candidate_key": normalize_candidate_key(str(row["candidate_key"])),
    }


def candidate_cluster_id(row: Mapping[str, Any]) -> str:
    return "R1CC-" + canonical_sha256(candidate_cluster_material(row))


def derive_r1_source_record(row: Mapping[str, Any]) -> dict[str, Any]:
    outcome = str(row["outcome"])
    unresolved = outcome in UNRESOLVED_OUTCOMES
    cardinality_bounded = outcome in {"UNRESOLVED_IDENTITY", "BORDERLINE"}
    source_barrier = outcome in {"ABSTAIN", "FAILED_INACCESSIBLE"}
    uncertainty_cardinality_class = (
        "ONE_OBJECT_UPPER_BOUND"
        if cardinality_bounded
        else ("UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER" if source_barrier else "TERMINAL")
    )
    canonical_id = row.get("canonical_offering_id")
    identity_state = "RESOLVED_CANONICAL" if canonical_id else "UNRESOLVED"
    if outcome == "EXCLUDE" and canonical_id is None:
        identity_state = "NOT_REQUIRED_EXCLUDED"

    scope_state = {
        "INCLUDE_RESOLVED": "IN_SCOPE_RESOLVED",
        "EXCLUDE": "EXCLUDED",
        "BORDERLINE": "BORDERLINE",
        "ABSTAIN": "ABSTAIN",
        "UNRESOLVED_IDENTITY": "UNRESOLVED",
        "FAILED_INACCESSIBLE": "UNRESOLVED_SOURCE_BARRIER",
    }[outcome]
    adjudication_state = {
        "INCLUDE_RESOLVED": "TERMINAL_FOR_CAPTURE",
        "EXCLUDE": "TERMINAL_FOR_CAPTURE",
        "BORDERLINE": "REVIEW_REQUIRED",
        "ABSTAIN": "ABSTAIN_REVIEW_REQUIRED",
        "UNRESOLVED_IDENTITY": "IDENTITY_REVIEW_REQUIRED",
        "FAILED_INACCESSIBLE": "SOURCE_RETRIEVAL_BLOCKED",
    }[outcome]

    return {
        "source_record_id": row["capture_id"],
        "capture_id": row["capture_id"],
        "source_packet_id": row["source_packet_id"],
        "frame_id": row["frame_id"],
        "round_id": row["round_id"],
        "query_or_seed_id": row["query_or_seed_id"],
        "query_family": row["query_family"],
        "source_class": row["source_class"],
        "raw_candidate_key": row["candidate_key"],
        "normalized_candidate_key": normalize_candidate_key(str(row["candidate_key"])),
        "normalized_candidate_label": normalized_candidate_label(str(row["candidate_key"])),
        "developer_or_organization_label": developer_or_organization_label(str(row["candidate_key"])),
        "developer_or_organization_label_is_canonical": False,
        "canonical_offering_id": canonical_id,
        "source_observation_ref": row["source_observation_ref"],
        "language": row["language"],
        "jurisdiction": row["jurisdiction"],
        "outcome": outcome,
        "observed_at": row["observed_at"],
        "analysis_universe_id": row["analysis_universe_id"],
        "population_view_id": row["population_view_id"],
        "world_time_alignment": row["world_time_alignment"],
        "world_time_support_ref": row["world_time_support_ref"],
        "candidate_cluster_id": candidate_cluster_id(row),
        "identity_resolution_state": identity_state,
        "scope_boundary_disposition_state": scope_state,
        "adjudication_state": adjudication_state,
        "evidence_sufficiency_state": (
            "SUFFICIENT_FOR_CAPTURE_DISPOSITION"
            if outcome in {"INCLUDE_RESOLVED", "EXCLUDE"}
            else "INSUFFICIENT_FOR_TERMINAL_PRODUCT_ACCOUNTING"
        ),
        "could_change_a_p1_membership": unresolved,
        "could_change_a3_increment": unresolved and row["frame_id"] == "F6",
        "could_change_a4_increment": unresolved and row["frame_id"] == "F8",
        "could_change_marginal_yield_stop": unresolved and row["frame_id"] in MARGINAL_YIELD_FRAMES,
        "cardinality_bounded_candidate_object": cardinality_bounded,
        "source_or_abstention_barrier": source_barrier,
        "uncertainty_cardinality_class": uncertainty_cardinality_class,
    }


def _load_packet_rows(binding: Mapping[str, Any]) -> list[dict[str, Any]]:
    resource = str(binding["source_packet_resource"])
    packet = _load(DISCOVERY_RESOURCE_PACKAGE, resource)
    if packet.get("packet_id") != binding.get("source_packet_id"):
        raise ProductDiscoveryError(f"R1 ledger source packet identity drift: {resource}")
    if packet.get("packet_sha256") != binding.get("source_packet_sha256"):
        raise ProductDiscoveryError(f"R1 ledger source packet declared digest drift: {resource}")
    if _packet_content_sha256(packet) != binding.get("source_packet_sha256"):
        raise ProductDiscoveryError(f"R1 ledger source packet content digest drift: {resource}")
    captures = packet.get("captures")
    if not isinstance(captures, list) or len(captures) != binding.get("capture_count"):
        raise ProductDiscoveryError(f"R1 ledger source packet capture count drift: {resource}")
    return [
        project_capture_record(cast(Mapping[str, Any], capture), source_packet_id=str(packet["packet_id"]))
        for capture in captures
    ]


def compile_r1_source_records(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    bindings = manifest.get("source_packet_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ProductDiscoveryError("R1 ledger manifest requires source_packet_bindings")
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise ProductDiscoveryError("R1 ledger source packet binding must be an object")
        rows.extend(_load_packet_rows(binding))
    derived = [derive_r1_source_record(row) for row in rows]
    derived.sort(key=lambda row: (str(row["frame_id"]), str(row["round_id"]), str(row["capture_id"])))
    capture_ids = [str(row["capture_id"]) for row in derived]
    if len(capture_ids) != len(set(capture_ids)):
        raise ProductDiscoveryError("R1 ledger contains duplicate capture IDs")
    return derived


def build_r1_candidate_clusters(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["candidate_cluster_id"])].append(record)

    result: list[dict[str, Any]] = []
    for cluster_id, rows in grouped.items():
        outcomes = sorted({str(row["outcome"]) for row in rows})
        canonical_ids = sorted({str(row["canonical_offering_id"]) for row in rows if row.get("canonical_offering_id")})
        unresolved = any(outcome in UNRESOLVED_OUTCOMES for outcome in outcomes)
        source_barrier = "ABSTAIN" in outcomes or "FAILED_INACCESSIBLE" in outcomes
        cardinality_bounded = (
            not source_barrier and ("UNRESOLVED_IDENTITY" in outcomes or "BORDERLINE" in outcomes)
        )
        uncertainty_cardinality_class = (
            "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            if source_barrier
            else ("ONE_OBJECT_UPPER_BOUND" if cardinality_bounded else "TERMINAL")
        )

        if canonical_ids:
            state = "RESOLVED_CANONICAL"
        elif all(outcome == "EXCLUDE" for outcome in outcomes):
            state = "TERMINAL_EXCLUDED"
        elif "UNRESOLVED_IDENTITY" in outcomes:
            state = "UNRESOLVED_IDENTITY"
        elif "BORDERLINE" in outcomes:
            state = "UNRESOLVED_SCOPE_BOUNDARY"
        elif "ABSTAIN" in outcomes:
            state = "ABSTAIN_REVIEW_REQUIRED"
        else:
            state = "FAILED_INACCESSIBLE"

        result.append(
            {
                "candidate_cluster_id": cluster_id,
                "cluster_basis": "CANONICAL_OFFERING_ID" if canonical_ids else "EXACT_NORMALIZED_CANDIDATE_KEY",
                "canonical_offering_id": canonical_ids[0] if len(canonical_ids) == 1 else None,
                "noncanonical_cluster": not canonical_ids,
                "normalized_candidate_key": None if canonical_ids else rows[0]["normalized_candidate_key"],
                "raw_candidate_keys": sorted({str(row["raw_candidate_key"]) for row in rows}),
                "developer_or_organization_labels": sorted(
                    {
                        str(row["developer_or_organization_label"])
                        for row in rows
                        if row.get("developer_or_organization_label")
                    }
                ),
                "capture_ids": sorted(str(row["capture_id"]) for row in rows),
                "frame_rounds": sorted({f"{row['frame_id']}:{row['round_id']}" for row in rows}),
                "outcomes": outcomes,
                "cluster_state": state,
                "identity_resolution_state": (
                    "RESOLVED_CANONICAL"
                    if canonical_ids
                    else ("NOT_REQUIRED_EXCLUDED" if state == "TERMINAL_EXCLUDED" else "UNRESOLVED")
                ),
                "adjudication_state": (
                    "TERMINAL_FOR_CURRENT_LEDGER"
                    if state in {"RESOLVED_CANONICAL", "TERMINAL_EXCLUDED"}
                    else "REVIEW_OR_EVIDENCE_REQUIRED"
                ),
                "evidence_sufficiency_state": (
                    "SUFFICIENT_FOR_CURRENT_DISPOSITION"
                    if state in {"RESOLVED_CANONICAL", "TERMINAL_EXCLUDED"}
                    else "INSUFFICIENT_FOR_TERMINAL_PRODUCT_ACCOUNTING"
                ),
                "could_change_a_p1_membership": unresolved,
                "could_change_a3_increment": any(bool(row["could_change_a3_increment"]) for row in rows),
                "could_change_a4_increment": any(bool(row["could_change_a4_increment"]) for row in rows),
                "could_change_marginal_yield_stop": any(bool(row["could_change_marginal_yield_stop"]) for row in rows),
                "cardinality_bounded_candidate_object": cardinality_bounded,
                "source_or_abstention_barrier": source_barrier,
                "uncertainty_cardinality_class": uncertainty_cardinality_class,
            }
        )

    result.sort(key=lambda item: str(item["candidate_cluster_id"]))
    return result


def load_r1_candidate_resolution_manifest() -> dict[str, Any]:
    manifest = _load(DISCOVERY_RESOURCE_PACKAGE, R1_LEDGER_MANIFEST_RESOURCE)
    validate_r1_candidate_resolution_ledger(manifest)
    return manifest


def validate_r1_candidate_resolution_ledger(manifest: Mapping[str, Any]) -> None:
    if manifest.get("ledger_manifest_id") != "RELEASE_A_R1_CANDIDATE_RESOLUTION_LEDGER_MANIFEST_v1.0":
        raise ProductDiscoveryError("R1 candidate ledger manifest ID drift")
    if artifact_sha256(manifest, digest_field="ledger_manifest_sha256") != manifest.get("ledger_manifest_sha256"):
        raise ProductDiscoveryError("R1 candidate ledger manifest digest mismatch")
    if manifest.get("ledger_manifest_sha256") != R1_LEDGER_MANIFEST_SHA256:
        raise ProductDiscoveryError("R1 candidate ledger frozen manifest digest drift")
    if manifest.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("R1 candidate ledger analysis universe drift")
    if manifest.get("world_time_cutoff") != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("R1 candidate ledger world-time cutoff drift")
    if manifest.get("knowledge_time_cutoff") != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("R1 candidate ledger knowledge-time cutoff drift")

    derived_records = compile_r1_source_records(manifest)
    declared_shards = manifest.get("source_ledger_shards")
    if not isinstance(declared_shards, list):
        raise ProductDiscoveryError("R1 candidate ledger source_ledger_shards must be an array")

    materialized_records: list[dict[str, Any]] = []
    seen_frames: set[str] = set()
    for binding in declared_shards:
        if not isinstance(binding, Mapping):
            raise ProductDiscoveryError("R1 source-ledger shard binding must be an object")
        frame_id = str(binding["frame_id"])
        if frame_id in seen_frames:
            raise ProductDiscoveryError("R1 source-ledger frames must be unique")
        seen_frames.add(frame_id)
        shard = _load(DISCOVERY_RESOURCE_PACKAGE, str(binding["resource"]))
        if artifact_sha256(shard, digest_field="ledger_shard_sha256") != shard.get("ledger_shard_sha256"):
            raise ProductDiscoveryError(f"R1 source-ledger shard digest mismatch: {frame_id}")
        if shard.get("ledger_shard_sha256") != binding.get("ledger_shard_sha256"):
            raise ProductDiscoveryError(f"R1 source-ledger shard binding drift: {frame_id}")
        if shard.get("frame_id") != frame_id:
            raise ProductDiscoveryError(f"R1 source-ledger shard frame drift: {frame_id}")
        records = shard.get("source_records")
        if not isinstance(records, list) or len(records) != binding.get("source_record_count"):
            raise ProductDiscoveryError(f"R1 source-ledger shard record count drift: {frame_id}")
        materialized_records.extend(cast(list[dict[str, Any]], records))

    materialized_records.sort(key=lambda row: (str(row["frame_id"]), str(row["round_id"]), str(row["capture_id"])))
    if materialized_records != derived_records:
        raise ProductDiscoveryError(
            "R1 materialized source ledger does not exactly reproduce from immutable A2 packets"
        )

    cluster_binding = manifest.get("cluster_ledger_binding")
    if not isinstance(cluster_binding, Mapping):
        raise ProductDiscoveryError("R1 cluster ledger binding must be an object")
    cluster_artifact = _load(DISCOVERY_RESOURCE_PACKAGE, str(cluster_binding["resource"]))
    if artifact_sha256(cluster_artifact, digest_field="cluster_ledger_sha256") != cluster_artifact.get(
        "cluster_ledger_sha256"
    ):
        raise ProductDiscoveryError("R1 cluster ledger digest mismatch")
    if cluster_artifact.get("cluster_ledger_sha256") != R1_CLUSTER_LEDGER_SHA256:
        raise ProductDiscoveryError("R1 cluster ledger frozen digest drift")
    if cluster_artifact.get("cluster_ledger_sha256") != cluster_binding.get("cluster_ledger_sha256"):
        raise ProductDiscoveryError("R1 cluster ledger manifest binding drift")
    if cluster_artifact.get("clustering_policy_id") != R1_CLUSTERING_POLICY_ID:
        raise ProductDiscoveryError("R1 clustering policy drift")

    derived_clusters = build_r1_candidate_clusters(derived_records)
    if cluster_artifact.get("clusters") != derived_clusters:
        raise ProductDiscoveryError("R1 cluster ledger does not reproduce from source records")
    if cluster_artifact.get("candidate_cluster_count") != len(derived_clusters):
        raise ProductDiscoveryError("R1 cluster ledger count drift")

    outcomes = Counter(str(row["outcome"]) for row in derived_records)
    accounting = manifest.get("accounting")
    if not isinstance(accounting, Mapping):
        raise ProductDiscoveryError("R1 candidate ledger accounting must be an object")
    expected_accounting = {
        "raw_capture_row_count": len(derived_records),
        "unique_raw_candidate_key_count": len({str(row["raw_candidate_key"]) for row in derived_records}),
        "governed_candidate_cluster_count": len(derived_clusters),
        "unresolved_identity_capture_row_count": outcomes["UNRESOLVED_IDENTITY"],
        "unresolved_scope_boundary_capture_row_count": outcomes["BORDERLINE"],
        "abstain_capture_row_count": outcomes["ABSTAIN"],
        "borderline_capture_row_count": outcomes["BORDERLINE"],
        "failed_inaccessible_capture_row_count": outcomes["FAILED_INACCESSIBLE"],
        "include_resolved_capture_row_count": outcomes["INCLUDE_RESOLVED"],
        "exclude_capture_row_count": outcomes["EXCLUDE"],
        "unresolved_clusters_capable_of_changing_a_p1_membership": sum(
            bool(cluster["could_change_a_p1_membership"]) for cluster in derived_clusters
        ),
        "unresolved_clusters_capable_of_changing_a3_increment": sum(
            bool(cluster["could_change_a3_increment"]) for cluster in derived_clusters
        ),
        "unresolved_clusters_capable_of_changing_a4_increment": sum(
            bool(cluster["could_change_a4_increment"]) for cluster in derived_clusters
        ),
        "unresolved_clusters_capable_of_changing_marginal_yield_stop": sum(
            bool(cluster["could_change_marginal_yield_stop"]) for cluster in derived_clusters
        ),
        "cardinality_bounded_unresolved_cluster_count": sum(
            cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND" for cluster in derived_clusters
        ),
        "unbounded_source_or_abstention_barrier_cluster_count": sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            for cluster in derived_clusters
        ),
        "cardinality_bounded_clusters_capable_of_changing_marginal_yield_stop": sum(
            cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND"
            and bool(cluster["could_change_marginal_yield_stop"])
            for cluster in derived_clusters
        ),
        "unbounded_barrier_clusters_capable_of_changing_marginal_yield_stop": sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            and bool(cluster["could_change_marginal_yield_stop"])
            for cluster in derived_clusters
        ),
        "cardinality_bounded_clusters_capable_of_changing_a3_increment": sum(
            cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND"
            and bool(cluster["could_change_a3_increment"])
            for cluster in derived_clusters
        ),
        "unbounded_barrier_clusters_capable_of_changing_a3_increment": sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            and bool(cluster["could_change_a3_increment"])
            for cluster in derived_clusters
        ),
        "cardinality_bounded_clusters_capable_of_changing_a4_increment": sum(
            cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND"
            and bool(cluster["could_change_a4_increment"])
            for cluster in derived_clusters
        ),
        "unbounded_barrier_clusters_capable_of_changing_a4_increment": sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            and bool(cluster["could_change_a4_increment"])
            for cluster in derived_clusters
        ),
    }
    if dict(accounting) != expected_accounting:
        raise ProductDiscoveryError("R1 candidate ledger accounting does not reproduce from source rows/clusters")


def validate_default_r1_resolution_state() -> dict[str, Any]:
    registry = load_r1_product_registry()
    denominator = load_r1_denominator_control()
    manifest = load_r1_candidate_resolution_manifest()
    return {
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "a_p1_identity_ids": derive_r1_a_p1_identity_ids(registry),
        "n_observed": denominator["n_observed"],
        "candidate_resolution_accounting": manifest["accounting"],
    }
