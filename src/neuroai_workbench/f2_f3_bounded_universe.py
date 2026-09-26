"""Validators for Release-A F2/F3 frozen provider/query universes.

Historical packets remain immutable. Exhaustion means every frozen record ID in
every declared query family has an exact disposition credit, including credits
from prior immutable packets where the universe explicitly permits them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    CAPTURE_OUTCOMES,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    ProductDiscoveryError,
    load_default_frame_register,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
F2_UNIVERSE_RESOURCE = "RELEASE_A_F2_PROVIDER_QUERY_UNIVERSE.v1.0.json"
F3_UNIVERSE_RESOURCE = "RELEASE_A_F3_PROVIDER_QUERY_UNIVERSE.v1.0.json"
F2_UNIVERSE_ID = "RELEASE_A_F2_PROVIDER_QUERY_UNIVERSE_v1.0"
F3_UNIVERSE_ID = "RELEASE_A_F3_PROVIDER_QUERY_UNIVERSE_v1.0"
F2_UNIVERSE_SHA256 = "7100742182020a7afb91fee5b9c175211eed4d10adac7c2f40bf52ee705af7b0"
F3_UNIVERSE_SHA256 = "7baeb3c7549286360fa6bd5494bcc3386d50e42b34f6be7c487adb9bdbfe10e2"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"

F2_QUERY_FAMILIES = frozenset(
    {
        "DEVICE_REGISTRY_ENUMERATION",
        "AUTHORIZATION_CLEARANCE_SEARCH",
        "REGULATORY_PRODUCT_IDENTITY_SEARCH",
    }
)
F3_QUERY_FAMILIES = frozenset(
    {
        "TRIAL_INTERVENTION_PRODUCT_SEARCH",
        "DEVICE_INTERVENTION_SEARCH",
        "FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH",
    }
)

F2_F3_BOUNDARY = (
    "F2/F3 exhaustion applies only to the frozen provider/query/pagination universes "
    "declared here. Regulatory and trial records are candidate source objects, not "
    "automatic NeuroAI PRODUCT identities. Exhaustion does not establish global "
    "completeness, unseen-population size, market share, effectiveness, commercialization, "
    "S2 publication authority, or v4.2 assessment effect."
)


def provider_query_universe_digest(universe: Mapping[str, Any]) -> str:
    """Return deterministic SHA-256 for a provider/query universe, excluding self-digest."""

    material = {key: value for key, value in universe.items() if key != "universe_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_id_set_digest(record_ids: Iterable[str]) -> str:
    """Return SHA-256 over the sorted unique record-id list."""

    material = sorted({str(record_id) for record_id in record_ids})
    encoded = json.dumps(material, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_universe_resource(resource_name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(resource_name).read_text(encoding="utf-8")),
    )


def load_default_f2_provider_query_universe() -> dict[str, Any]:
    """Load and validate the frozen F2 provider/query universe."""

    universe = _load_universe_resource(F2_UNIVERSE_RESOURCE)
    validate_f2_provider_query_universe(universe)
    return universe


def load_default_f3_provider_query_universe() -> dict[str, Any]:
    """Load and validate the frozen F3 provider/query universe."""

    universe = _load_universe_resource(F3_UNIVERSE_RESOURCE)
    validate_f3_provider_query_universe(universe)
    return universe


def _frame(frame_id: str) -> Mapping[str, Any]:
    register = load_default_frame_register()
    frames = cast(list[Mapping[str, Any]], register["frames"])
    return next(frame for frame in frames if frame["frame_id"] == frame_id)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{label} must be a non-empty string")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductDiscoveryError(f"{label} must be an array")
    return value


def _validate_common_universe(universe: Mapping[str, Any], *, frame_id: str, allowed_families: frozenset[str]) -> None:
    required = {
        "universe_id",
        "universe_sha256",
        "status",
        "frame_id",
        "frame_version",
        "frame_register_version",
        "frame_register_blob_sha",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "census_registered_at",
        "providers",
        "query_families",
        "bounded_exhaustion_rule",
        "boundary",
    }
    missing = sorted(required - set(universe))
    if missing:
        raise ProductDiscoveryError(f"Provider/query universe missing fields: {', '.join(missing)}")
    if universe["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("Provider/query universe status must be FROZEN_v1.0")
    if universe["frame_id"] != frame_id:
        raise ProductDiscoveryError(f"Provider/query universe frame_id must be {frame_id}")
    if universe["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError("Provider/query universe frame_version mismatch")
    if universe["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("Provider/query universe frame_register_version mismatch")
    if universe["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("Provider/query universe frame_register_blob_sha mismatch")
    if universe["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("Provider/query universe analysis_universe_id mismatch")
    if universe["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("Provider/query universe world_time_cutoff mismatch")
    if universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("Provider/query universe knowledge_time_cutoff mismatch")
    if provider_query_universe_digest(universe) != universe["universe_sha256"]:
        raise ProductDiscoveryError("Provider/query universe_sha256 digest mismatch")

    frame = _frame(frame_id)
    frame_families = set(cast(Sequence[str], frame["query_families"]))
    if allowed_families != frame_families:
        raise ProductDiscoveryError(f"{frame_id} allowed query families drifted from frame register")

    providers = _require_list(universe["providers"], "providers")
    if not providers:
        raise ProductDiscoveryError("providers must be non-empty")
    provider_ids: set[str] = set()
    for provider in providers:
        mapping = _require_mapping(provider, "provider")
        provider_id = _require_str(mapping.get("provider_id"), "provider_id")
        if provider_id in provider_ids:
            raise ProductDiscoveryError(f"Duplicate provider_id {provider_id}")
        provider_ids.add(provider_id)
        _require_str(mapping.get("base_url"), "base_url")
        _require_str(mapping.get("authority"), "authority")

    families = _require_list(universe["query_families"], "query_families")
    seen_families: set[str] = set()
    for family in families:
        mapping = _require_mapping(family, "query_family entry")
        query_family = _require_str(mapping.get("query_family"), "query_family")
        if query_family not in allowed_families:
            raise ProductDiscoveryError(f"Unknown query_family {query_family} for {frame_id}")
        if query_family in seen_families:
            raise ProductDiscoveryError(f"Duplicate query_family {query_family}")
        seen_families.add(query_family)
        _require_str(mapping.get("query_id"), "query_id")
        provider_id = _require_str(mapping.get("provider_id"), "provider_id")
        if provider_id not in provider_ids:
            raise ProductDiscoveryError(f"query_family {query_family} references unknown provider_id")
        record_ids = [str(item) for item in _require_list(mapping.get("frozen_record_ids"), "frozen_record_ids")]
        if not record_ids:
            raise ProductDiscoveryError(f"{query_family} frozen_record_ids must be non-empty")
        if len(record_ids) != len(set(record_ids)):
            raise ProductDiscoveryError(f"{query_family} frozen_record_ids must be unique")
        if sorted(record_ids) != record_ids:
            raise ProductDiscoveryError(f"{query_family} frozen_record_ids must be sorted")
        if int(mapping["frozen_record_count"]) != len(record_ids):
            raise ProductDiscoveryError(f"{query_family} frozen_record_count mismatch")
        if mapping["frozen_record_set_sha256"] != record_id_set_digest(record_ids):
            raise ProductDiscoveryError(f"{query_family} frozen_record_set_sha256 mismatch")
        pagination = _require_mapping(mapping.get("pagination", {"mode": "NONE"}), "pagination")
        _require_str(pagination.get("mode"), "pagination.mode")
        _require_str(pagination.get("termination_rule", "n/a"), "pagination.termination_rule")
    if seen_families != allowed_families:
        missing_families = sorted(allowed_families - seen_families)
        raise ProductDiscoveryError(f"{frame_id} missing query families: {', '.join(missing_families)}")

    rule = _require_mapping(universe["bounded_exhaustion_rule"], "bounded_exhaustion_rule")
    if rule.get("requires_every_query_family_record_id_dispositioned") is not True:
        raise ProductDiscoveryError("bounded_exhaustion_rule must require full record disposition")
    if rule.get("global_completeness_claim_prohibited") is not True:
        raise ProductDiscoveryError("bounded_exhaustion_rule must prohibit global completeness claims")
    if rule.get("candidate_is_not_automatic_product_identity") is not True:
        raise ProductDiscoveryError("bounded_exhaustion_rule must keep candidates distinct from products")
    if universe.get("boundary") != F2_F3_BOUNDARY:
        raise ProductDiscoveryError("Provider/query universe boundary text mismatch")


def validate_f2_provider_query_universe(universe: Mapping[str, Any]) -> None:
    """Fail closed if the F2 provider/query universe is incomplete or drifted."""

    _validate_common_universe(universe, frame_id="F2", allowed_families=F2_QUERY_FAMILIES)
    if universe.get("universe_id") != F2_UNIVERSE_ID:
        raise ProductDiscoveryError("F2 universe_id mismatch")
    if universe.get("source_class") != "REGULATOR_OFFICIAL":
        raise ProductDiscoveryError("F2 source_class must be REGULATOR_OFFICIAL")


def validate_f3_provider_query_universe(universe: Mapping[str, Any]) -> None:
    """Fail closed if the F3 provider/query universe is incomplete or drifted."""

    _validate_common_universe(universe, frame_id="F3", allowed_families=F3_QUERY_FAMILIES)
    if universe.get("universe_id") != F3_UNIVERSE_ID:
        raise ProductDiscoveryError("F3 universe_id mismatch")
    source_classes = set(_require_list(universe.get("source_classes"), "source_classes"))
    if source_classes != {"TRIAL_REGISTRY_OFFICIAL", "STUDY_RECORD"}:
        raise ProductDiscoveryError("F3 source_classes mismatch")
    union_ids = [str(item) for item in _require_list(universe.get("union_record_ids"), "union_record_ids")]
    if sorted(union_ids) != union_ids or len(union_ids) != len(set(union_ids)):
        raise ProductDiscoveryError("F3 union_record_ids must be sorted unique")
    if int(universe["union_record_count"]) != len(union_ids):
        raise ProductDiscoveryError("F3 union_record_count mismatch")
    if universe["union_record_set_sha256"] != record_id_set_digest(union_ids):
        raise ProductDiscoveryError("F3 union_record_set_sha256 mismatch")
    expected_union: set[str] = set()
    for family in cast(list[Mapping[str, Any]], universe["query_families"]):
        expected_union.update(str(item) for item in family["frozen_record_ids"])
    if set(union_ids) != expected_union:
        raise ProductDiscoveryError("F3 union_record_ids must equal the union of family record ids")


def _family_map(universe: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(entry["query_family"]): entry for entry in cast(list[Mapping[str, Any]], universe["query_families"])}


def prior_packet_credit_ids(universe: Mapping[str, Any], query_family: str) -> set[str]:
    """Return record IDs the universe permits crediting from the immutable R1 packet."""

    family = _family_map(universe)[query_family]
    prior = family.get("prior_packet_observations")
    if not isinstance(prior, Mapping):
        return set()
    credited = prior.get("already_dispositioned_record_ids", [])
    if not isinstance(credited, list):
        raise ProductDiscoveryError("already_dispositioned_record_ids must be an array")
    return {str(item) for item in credited}


def validate_disposition_credit(credit: Mapping[str, Any], *, frame_id: str) -> None:
    """Validate one record-level disposition credit against a frozen universe family."""

    required = {
        "frame_id",
        "query_family",
        "record_id",
        "capture_outcome",
        "source_packet_id",
        "source_packet_sha256",
    }
    missing = sorted(required - set(credit))
    if missing:
        raise ProductDiscoveryError(f"Disposition credit missing fields: {', '.join(missing)}")
    if credit["frame_id"] != frame_id:
        raise ProductDiscoveryError("Disposition credit frame_id mismatch")
    if credit["capture_outcome"] not in CAPTURE_OUTCOMES:
        raise ProductDiscoveryError("Disposition credit capture_outcome is outside the frozen domain")
    _require_str(credit.get("record_id"), "record_id")
    _require_str(credit.get("query_family"), "query_family")
    _require_str(credit.get("source_packet_id"), "source_packet_id")
    _require_str(credit.get("source_packet_sha256"), "source_packet_sha256")


def family_disposition_coverage(
    universe: Mapping[str, Any],
    credits: Sequence[Mapping[str, Any]],
    *,
    frame_id: str,
) -> dict[str, dict[str, Any]]:
    """Return per-family coverage of frozen record IDs by validated disposition credits."""

    if frame_id == "F2":
        validate_f2_provider_query_universe(universe)
    elif frame_id == "F3":
        validate_f3_provider_query_universe(universe)
    else:
        raise ProductDiscoveryError("frame_id must be F2 or F3")

    families = _family_map(universe)
    coverage: dict[str, dict[str, Any]] = {}
    for query_family, family in families.items():
        frozen = {str(item) for item in family["frozen_record_ids"]}
        credited: set[str] = set()
        for credit in credits:
            validate_disposition_credit(credit, frame_id=frame_id)
            if credit["query_family"] != query_family:
                continue
            record_id = str(credit["record_id"])
            if record_id not in frozen:
                raise ProductDiscoveryError(f"Disposition credit {record_id} is outside frozen {query_family} universe")
            credited.add(record_id)
        # Immutable R1 credits declared by the universe itself.
        prior = prior_packet_credit_ids(universe, query_family)
        unknown_prior = prior - frozen
        if unknown_prior:
            raise ProductDiscoveryError(f"Universe prior credit ids outside {query_family}: {sorted(unknown_prior)}")
        credited |= prior
        # FAILED_INACCESSIBLE prior credits do not close exhaustion when retry is required.
        failed_prior = family.get("prior_packet_observations", {})
        failed_ids: set[str] = set()
        if isinstance(failed_prior, Mapping):
            raw_failed = failed_prior.get("failed_inaccessible_record_ids", [])
            if isinstance(raw_failed, list):
                failed_ids = {str(item) for item in raw_failed}
        # Prior failed IDs are not treated as complete unless a non-prior successor credit exists.
        successor_credits = {
            str(credit["record_id"])
            for credit in credits
            if credit["query_family"] == query_family
            and credit["source_packet_id"] != "RELEASE_A_A2_BOUNDED_TRANCHE_1_v1.0"
        }
        effective = (credited - failed_ids) | (failed_ids & successor_credits)
        remaining = sorted(frozen - effective)
        coverage[query_family] = {
            "frozen_count": len(frozen),
            "credited_count": len(effective),
            "remaining_count": len(remaining),
            "remaining_record_ids": remaining,
            "exhausted": not remaining,
        }
    return coverage


def bounded_frame_exhaustion_state(
    universe: Mapping[str, Any],
    credits: Sequence[Mapping[str, Any]],
    *,
    frame_id: str,
    unresolved_source_barrier: bool = False,
) -> str:
    """Return protocol stop state for one frozen F2/F3 provider/query universe."""

    if unresolved_source_barrier:
        return "UNRESOLVED_SOURCE_BARRIER"
    coverage = family_disposition_coverage(universe, credits, frame_id=frame_id)
    if all(entry["exhausted"] for entry in coverage.values()):
        return "BOUNDED_FRAME_EXHAUSTED"
    return "CONTINUE"
