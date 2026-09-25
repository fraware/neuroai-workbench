from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
FRAME_SCHEMA = "PRODUCT_DISCOVERY_FRAME.schema.json"
CAPTURE_SCHEMA = "PRODUCT_DISCOVERY_CAPTURE.schema.json"
RUN_SCHEMA = "PRODUCT_DISCOVERY_RUN.schema.json"
ANALYSIS_UNIVERSE_SCHEMA = "RELEASE_A_A2_ANALYSIS_UNIVERSE.schema.json"
FRAME_REGISTER_RESOURCE = "PRODUCT_DISCOVERY_FRAME_REGISTER.v1.0.json"
F9_ACTOR_SEED_REGISTER_RESOURCE = "RELEASE_A_F9_ACTOR_SEED_REGISTER.v1.0.json"
ANALYSIS_UNIVERSE_RESOURCE = "RELEASE_A_A2_ANALYSIS_UNIVERSE.v1.0.json"

FRAME_VERSION = "PRODUCT_DISCOVERY_FRAME_v1.0"
FRAME_REGISTER_VERSION = "PRODUCT_DISCOVERY_FRAME_REGISTER_v1.0"
F9_ACTOR_SEED_REGISTER_ID = "RELEASE_A_F9_ACTOR_SEED_REGISTER_v1.0"
ANALYSIS_UNIVERSE_VERSION = "RELEASE_A_A2_ANALYSIS_UNIVERSE_v1.0"
DEFAULT_ANALYSIS_UNIVERSE_ID = "RAU-241571c4d7c3f362eee14aa7d36ee03c76f8cfa1fa557160d1ea1e4247ccb299"
A1_SEED_MANIFEST_ID = "RASIM-7b6a3eb9271c7f8b33b6b467594789f230f6ebcd80d4f53cfac814c26e3b52bf"
A1_SEED_REGISTRY_SHA256 = "9ba43d5614fb1ebb668c097a20c2279dbaaa74511956c16ee6f278cbfc109672"
A1_INITIAL_KNOWN_IDENTITY_SHA256 = "21034ecec898f81f27ad143282967354315b5b31f9eaf430334ca172186c26c0"
A2_WORKBENCH_BASELINE_SHA = "11c516209fc77dea497fc3bb61012e2f3daecdf7"
A2_FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
A2_WORLD_TIME_CUTOFF = "2026-09-24"
A2_KNOWLEDGE_TIME_CUTOFF = "2026-10-24T23:59:59Z"
A2_JURISDICTION_SCOPE = "GLOBAL_PROTOCOL_SCOPE"
A2_LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"
REGISTRY_PROJECTION_VERSION = "PRODUCT_REGISTRY_v1.0"
FRAME_IDS = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11")
FRAME_ID_SET = frozenset(FRAME_IDS)
PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS = frozenset({"F7", "F9", "F11"})
FRAME_CLASS_BY_ID = {
    "F1": "FIRST_PARTY",
    "F2": "REGULATORY",
    "F3": "CLINICAL_TRIAL",
    "F4": "SCIENTIFIC_RESEARCH",
    "F5": "COMMERCIAL_ECOSYSTEM",
    "F6": "CAPABILITY_FIRST",
    "F7": "EXPERT_NOMINATION",
    "F8": "LOCAL_LANGUAGE",
    "F9": "CURATED_ACTOR_SEED",
    "F10": "PATENT_COMMERCIALIZATION",
    "F11": "SNOWBALL_EXPANSION",
}

CAPTURE_OUTCOMES = frozenset(
    {
        "INCLUDE_RESOLVED",
        "EXCLUDE",
        "BORDERLINE",
        "ABSTAIN",
        "UNRESOLVED_IDENTITY",
        "FAILED_INACCESSIBLE",
    }
)
STOP_STATES = frozenset(
    {
        "CONTINUE",
        "SATURATION_UNDER_DECLARED_PROTOCOL",
        "BOUNDED_FRAME_EXHAUSTED",
        "BUDGET_COVERAGE_TERMINATION",
        "UNRESOLVED_SOURCE_BARRIER",
    }
)

DISCOVERY_BOUNDARY = (
    "Product discovery measures protocol-bounded coverage and capture overlap. "
    "No discovery frame, yield threshold, stop state, or capture history establishes global completeness."
)


class ProductDiscoveryError(ValueError):
    """Raised when Release-A product-discovery records violate the P0.4 contract."""


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


def _parse_bound_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{field} requires a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductDiscoveryError(f"{field} must be a valid offset-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductDiscoveryError(f"{field} must include an explicit timezone")
    return parsed


def analysis_universe_id(universe: Mapping[str, Any]) -> str:
    """Return the deterministic identity of one frozen Release-A A2 analysis universe."""

    material = {key: value for key, value in universe.items() if key != "analysis_universe_id"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "RAU-" + hashlib.sha256(encoded).hexdigest()


def load_default_analysis_universe() -> dict[str, Any]:
    """Load and validate the frozen Release-A A2 analysis universe."""

    universe = cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(ANALYSIS_UNIVERSE_RESOURCE).read_text(encoding="utf-8")),
    )
    validate_analysis_universe(universe)
    return universe


def validate_analysis_universe(universe: Mapping[str, Any]) -> None:
    errors = _schema_errors(universe, ANALYSIS_UNIVERSE_SCHEMA)
    if errors:
        raise ProductDiscoveryError("Analysis-universe schema validation failed: " + "; ".join(errors))
    if universe["analysis_universe_id"] != analysis_universe_id(universe):
        raise ProductDiscoveryError("analysis_universe_id does not match the deterministic frozen universe")
    if universe["manifest_version"] != ANALYSIS_UNIVERSE_VERSION:
        raise ProductDiscoveryError(f"manifest_version must be {ANALYSIS_UNIVERSE_VERSION}")
    if universe["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("Release-A A2 analysis universe must be FROZEN_v1.0")
    if universe["a1_seed_manifest_id"] != A1_SEED_MANIFEST_ID:
        raise ProductDiscoveryError("Analysis universe does not bind the frozen A1 seed manifest")
    if universe["a1_seed_registry_sha256"] != A1_SEED_REGISTRY_SHA256:
        raise ProductDiscoveryError("Analysis universe does not bind the frozen A1 seed registry digest")
    if universe["initial_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("Analysis universe initial known-identity digest does not match A1")
    if int(universe["initial_known_identity_count"]) != 6:
        raise ProductDiscoveryError("Analysis universe initial_known_identity_count must be 6")
    if universe["workbench_baseline_sha"] != A2_WORKBENCH_BASELINE_SHA:
        raise ProductDiscoveryError("Analysis universe does not bind the exact A2 workbench baseline")
    if universe["frame_register_blob_sha"] != A2_FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("Analysis universe does not bind the frozen frame-register blob")
    if universe["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("Analysis universe world_time_cutoff does not match frozen A2 v1.0")
    if universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("Analysis universe knowledge_time_cutoff does not match frozen A2 v1.0")
    if universe["analysis_jurisdiction_scope"] != A2_JURISDICTION_SCOPE:
        raise ProductDiscoveryError("Analysis universe jurisdiction scope does not match frozen A2 v1.0")
    if universe["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("Analysis universe language scope does not match frozen A2 v1.0")
    if universe["registry_projection_version"] != REGISTRY_PROJECTION_VERSION:
        raise ProductDiscoveryError(f"registry_projection_version must be {REGISTRY_PROJECTION_VERSION}")
    if universe["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if universe["population_view_id"] != "A-P1":
        raise ProductDiscoveryError("A2 v1.0 analysis universe must bind A-P1")
    primary = set(cast(list[str], universe["primary_estimation_frame_ids"]))
    diagnostic = set(cast(list[str], universe["diagnostic_only_frame_ids"]))
    expected_primary = FRAME_ID_SET - PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS
    if primary != expected_primary:
        raise ProductDiscoveryError("Analysis universe primary frame set does not match the frozen P0.5 estimator set")
    if diagnostic != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("Analysis universe diagnostic-only frame set must be F7/F9/F11")
    if primary & diagnostic:
        raise ProductDiscoveryError("Analysis universe primary and diagnostic frame sets must be disjoint")


def validate_discovery_frame(frame: Mapping[str, Any]) -> None:
    errors = _schema_errors(frame, FRAME_SCHEMA)
    if errors:
        raise ProductDiscoveryError("Discovery frame schema validation failed: " + "; ".join(errors))

    frame_id = str(frame["frame_id"])
    if frame_id not in FRAME_ID_SET:
        raise ProductDiscoveryError(f"Unknown frame_id {frame_id!r}")
    if frame["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    expected_class = FRAME_CLASS_BY_ID[frame_id]
    if frame["frame_class"] != expected_class:
        raise ProductDiscoveryError(f"{frame_id} frame_class must be {expected_class!r}, got {frame['frame_class']!r}")

    dependencies = set(cast(list[str], frame["dependent_or_nested_with"]))
    if frame_id in dependencies:
        raise ProductDiscoveryError("A discovery frame cannot be dependent or nested with itself")

    if frame_id in PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS and frame["capture_estimation_eligible"] is not False:
        raise ProductDiscoveryError(
            f"{frame_id} is purposive/path-dependent in v1.0 and cannot enter the primary capture estimator"
        )

    rule = cast(Mapping[str, Any], frame["stopping_rule"])
    mode = rule["mode"]
    threshold_fields = (
        "minimum_completed_rounds",
        "consecutive_low_yield_rounds",
        "maximum_marginal_new_identity_yield",
        "minimum_raw_candidates_per_round",
    )
    if mode == "MARGINAL_YIELD" and any(rule[field] is None for field in threshold_fields):
        raise ProductDiscoveryError("MARGINAL_YIELD stopping rule requires all threshold fields")


def load_default_frame_register() -> dict[str, Any]:
    """Load and validate the frozen Release-A discovery frame register."""

    register = cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(FRAME_REGISTER_RESOURCE).read_text(encoding="utf-8")),
    )
    validate_frame_register(register)
    return register


def load_f9_actor_seed_register() -> dict[str, Any]:
    """Load and validate the frozen Release-A F9 curated-actor seed input."""

    register = cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(F9_ACTOR_SEED_REGISTER_RESOURCE).read_text(encoding="utf-8")),
    )
    validate_f9_actor_seed_register(register)
    return register


def validate_f9_actor_seed_register(register: Mapping[str, Any]) -> None:
    """Validate the exact bounded actor seed set used by F9 discovery."""

    if register.get("register_id") != F9_ACTOR_SEED_REGISTER_ID:
        raise ProductDiscoveryError(f"F9 actor seed register_id must be {F9_ACTOR_SEED_REGISTER_ID}")
    if register.get("frame_id") != "F9":
        raise ProductDiscoveryError("F9 actor seed register must bind frame_id F9")
    if register.get("frame_register_version") != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"F9 actor seed register must bind {FRAME_REGISTER_VERSION}")
    if register.get("estimator_role") != "EXCLUDED_FROM_PRIMARY_UNSEEN_POPULATION_ESTIMATOR":
        raise ProductDiscoveryError("F9 actor seed register must remain excluded from the primary estimator")

    actors = register.get("actors")
    if not isinstance(actors, list) or not actors:
        raise ProductDiscoveryError("F9 actor seed register actors must be a non-empty list")
    if int(register.get("actor_count", -1)) != len(actors):
        raise ProductDiscoveryError("F9 actor seed actor_count does not match actor list length")

    organization_ids: set[str] = set()
    for actor in actors:
        if not isinstance(actor, Mapping):
            raise ProductDiscoveryError("F9 actor seed entries must be objects")
        organization_id = str(actor.get("organization_id", "")).strip()
        canonical_name = str(actor.get("canonical_name", "")).strip()
        if not organization_id or not canonical_name:
            raise ProductDiscoveryError("F9 actor seed entries require organization_id and canonical_name")
        if organization_id in organization_ids:
            raise ProductDiscoveryError(f"Duplicate F9 actor organization_id: {organization_id}")
        organization_ids.add(organization_id)

    source_binding = register.get("source_binding")
    if not isinstance(source_binding, Mapping):
        raise ProductDiscoveryError("F9 actor seed register requires an exact source_binding")
    for field in ("repository", "commit_sha", "path", "blob_sha"):
        if not str(source_binding.get(field, "")).strip():
            raise ProductDiscoveryError(f"F9 actor seed source_binding requires {field}")


def validate_frame_register(register: Mapping[str, Any]) -> None:
    if register.get("register_id") != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"register_id must be {FRAME_REGISTER_VERSION}")
    if register.get("status") != "FROZEN_v1.0":
        raise ProductDiscoveryError("Default discovery frame register must be FROZEN_v1.0")
    frames = register.get("frames")
    if not isinstance(frames, list):
        raise ProductDiscoveryError("Frame register frames must be a list")
    indexed = _frame_map(cast(Sequence[Mapping[str, Any]], frames))
    if set(indexed) != FRAME_ID_SET:
        missing = sorted(FRAME_ID_SET - set(indexed))
        extra = sorted(set(indexed) - FRAME_ID_SET)
        raise ProductDiscoveryError(f"Frame register must contain exactly F1-F11; missing={missing!r}, extra={extra!r}")
    excluded = {frame_id for frame_id, frame in indexed.items() if not bool(frame["capture_estimation_eligible"])}
    declared = set(cast(list[str], register.get("estimation_policy", {}).get("purposive_frames_excluded", [])))
    if excluded != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS or declared != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError(
            "Frame register estimation-policy exclusions must exactly match the frozen F7/F9/F11 policy"
        )


def product_capture_id(capture: Mapping[str, Any]) -> str:
    """Return a deterministic ID for one product-discovery observation."""

    material = {
        key: capture.get(key)
        for key in (
            "frame_id",
            "frame_version",
            "round_id",
            "query_or_seed_id",
            "query_family",
            "source_class",
            "candidate_key",
            "canonical_offering_id",
            "source_observation_ref",
            "language",
            "jurisdiction",
            "outcome",
            "capture_estimation_eligible",
            "observed_at",
            "registry_projection_version",
            "frame_register_version",
            "analysis_universe_id",
            "population_view_id",
            "analysis_jurisdiction_scope",
            "language_scope_id",
            "world_time_cutoff",
            "knowledge_time_cutoff",
            "world_time_alignment",
        )
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "PDC-" + hashlib.sha256(encoded).hexdigest()


def validate_product_capture(capture: Mapping[str, Any]) -> None:
    errors = _schema_errors(capture, CAPTURE_SCHEMA)
    if errors:
        raise ProductDiscoveryError("Product capture schema validation failed: " + "; ".join(errors))
    if capture["capture_id"] != product_capture_id(capture):
        raise ProductDiscoveryError("capture_id does not match the deterministic observation key")
    if capture["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    if capture["registry_projection_version"] != REGISTRY_PROJECTION_VERSION:
        raise ProductDiscoveryError(f"registry_projection_version must be {REGISTRY_PROJECTION_VERSION}")
    if capture["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if capture["boundary"] != DISCOVERY_BOUNDARY:
        raise ProductDiscoveryError("Product capture boundary does not match the frozen Release-A boundary")

    outcome = capture["outcome"]
    if outcome not in CAPTURE_OUTCOMES:
        raise ProductDiscoveryError(f"Unknown capture outcome {outcome!r}")
    if outcome == "INCLUDE_RESOLVED":
        if not capture.get("canonical_offering_id"):
            raise ProductDiscoveryError("INCLUDE_RESOLVED capture requires canonical_offering_id")
        if not capture.get("source_observation_ref"):
            raise ProductDiscoveryError("INCLUDE_RESOLVED capture requires source_observation_ref")
        if capture.get("world_time_alignment") != "EVIDENCE_SUPPORTS_AT_OR_BEFORE_CUTOFF":
            raise ProductDiscoveryError(
                "INCLUDE_RESOLVED capture requires evidence supporting identity/state at or before the world-time cutoff"
            )
    if capture["capture_estimation_eligible"] and outcome != "INCLUDE_RESOLVED":
        raise ProductDiscoveryError("Only resolved in-scope offering captures can be capture-estimation eligible")

    observed_at = _parse_bound_timestamp(capture["observed_at"], field="Product capture observed_at")
    knowledge_cutoff = _parse_bound_timestamp(
        capture["knowledge_time_cutoff"],
        field="Product capture knowledge_time_cutoff",
    )
    if observed_at > knowledge_cutoff:
        raise ProductDiscoveryError("Product capture observed_at cannot exceed its knowledge_time_cutoff")


def validate_capture_against_analysis_universe(
    capture: Mapping[str, Any],
    universe: Mapping[str, Any],
) -> None:
    """Require one capture to bind exactly to the frozen A2 analysis universe."""

    validate_product_capture(capture)
    validate_analysis_universe(universe)
    if capture["analysis_universe_id"] != universe["analysis_universe_id"]:
        raise ProductDiscoveryError("Capture analysis_universe_id does not match the frozen A2 universe")
    for field in (
        "registry_projection_version",
        "frame_register_version",
        "population_view_id",
        "analysis_jurisdiction_scope",
        "language_scope_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
    ):
        if capture[field] != universe[field]:
            raise ProductDiscoveryError(f"Capture {field} does not match the frozen A2 analysis universe")


def validate_capture_against_frame(
    capture: Mapping[str, Any],
    frame: Mapping[str, Any],
) -> None:
    validate_discovery_frame(frame)
    validate_product_capture(capture)
    if capture["frame_id"] != frame["frame_id"]:
        raise ProductDiscoveryError("Capture frame_id does not match frame definition")
    if capture["frame_version"] != frame["frame_version"]:
        raise ProductDiscoveryError("Capture frame_version does not match frame definition")
    if capture["query_family"] not in frame["query_families"]:
        raise ProductDiscoveryError("Capture query_family is outside the declared discovery frame")
    if capture["source_class"] not in frame["source_classes"]:
        raise ProductDiscoveryError("Capture source_class is outside the declared discovery frame")
    if capture["capture_estimation_eligible"] and not frame["capture_estimation_eligible"]:
        raise ProductDiscoveryError("Capture cannot be estimation-eligible when its discovery frame is excluded")


def _capture_universe_key(capture: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        capture.get("registry_projection_version"),
        capture.get("frame_register_version"),
        capture.get("analysis_universe_id"),
        capture.get("population_view_id"),
        capture.get("analysis_jurisdiction_scope"),
        capture.get("language_scope_id"),
        capture.get("world_time_cutoff"),
        capture.get("knowledge_time_cutoff"),
    )


def _require_one_capture_universe(captures: Sequence[Mapping[str, Any]]) -> None:
    keys = {_capture_universe_key(capture) for capture in captures}
    if len(keys) > 1:
        raise ProductDiscoveryError("Capture histories cannot mix registry/view/jurisdiction/language/cutoff universes")


def identity_set_digest(identity_ids: Iterable[str]) -> str:
    """Return the canonical SHA-256 digest for a round-start known-identity set."""

    encoded = json.dumps(
        sorted(set(identity_ids)),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def product_discovery_run_id(run: Mapping[str, Any]) -> str:
    """Return the deterministic ID for one frame/round execution declaration."""

    material = {
        key: run.get(key)
        for key in (
            "frame_id",
            "frame_version",
            "frame_register_version",
            "analysis_universe_id",
            "round_id",
            "analysis_jurisdiction_scope",
            "language_scope_id",
            "registry_projection_version",
            "population_view_id",
            "world_time_cutoff",
            "knowledge_time_cutoff",
            "known_identity_set_sha256",
            "capture_count",
            "stop_state",
            "stop_reason",
        )
    }
    for set_field in ("query_or_seed_ids", "languages", "jurisdictions", "capture_ids"):
        material[set_field] = sorted(cast(list[str], run.get(set_field, [])))
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "PDR-" + hashlib.sha256(encoded).hexdigest()


def validate_discovery_run(run: Mapping[str, Any]) -> None:
    errors = _schema_errors(run, RUN_SCHEMA)
    if errors:
        raise ProductDiscoveryError("Discovery run schema validation failed: " + "; ".join(errors))
    if run["run_id"] != product_discovery_run_id(run):
        raise ProductDiscoveryError("run_id does not match the deterministic run declaration")
    if run["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    if run["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if run["registry_projection_version"] != REGISTRY_PROJECTION_VERSION:
        raise ProductDiscoveryError(f"registry_projection_version must be {REGISTRY_PROJECTION_VERSION}")
    if run["boundary"] != DISCOVERY_BOUNDARY:
        raise ProductDiscoveryError("Discovery run boundary does not match the frozen Release-A boundary")


def validate_run_against_captures(
    run: Mapping[str, Any],
    captures: Sequence[Mapping[str, Any]],
    frame: Mapping[str, Any],
) -> None:
    """Bind one declared frame/round run to its exact capture records."""

    validate_discovery_run(run)
    validate_discovery_frame(frame)
    if run["frame_id"] != frame["frame_id"] or run["frame_version"] != frame["frame_version"]:
        raise ProductDiscoveryError("Discovery run does not match its frame definition")

    expected_ids: list[str] = []
    query_or_seed_ids = set(cast(list[str], run["query_or_seed_ids"]))
    languages = set(cast(list[str], run["languages"]))
    jurisdictions = set(cast(list[str], run["jurisdictions"]))
    for capture in captures:
        validate_capture_against_frame(capture, frame)
        if capture["round_id"] != run["round_id"]:
            raise ProductDiscoveryError("Capture round_id does not match discovery run")
        if capture["query_or_seed_id"] not in query_or_seed_ids:
            raise ProductDiscoveryError("Capture query_or_seed_id is outside the discovery run declaration")
        if capture["language"] not in languages:
            raise ProductDiscoveryError("Capture language is outside the discovery run declaration")
        if capture["jurisdiction"] not in jurisdictions:
            raise ProductDiscoveryError("Capture jurisdiction is outside the discovery run declaration")
        for field in (
            "frame_register_version",
            "analysis_universe_id",
            "registry_projection_version",
            "population_view_id",
            "analysis_jurisdiction_scope",
            "language_scope_id",
            "world_time_cutoff",
            "knowledge_time_cutoff",
        ):
            if capture[field] != run[field]:
                raise ProductDiscoveryError(f"Capture {field} does not match discovery run")
        expected_ids.append(str(capture["capture_id"]))

    if int(run["capture_count"]) != len(captures):
        raise ProductDiscoveryError("capture_count does not match exact discovery-run captures")
    if sorted(cast(list[str], run["capture_ids"])) != sorted(expected_ids):
        raise ProductDiscoveryError("capture_ids do not match exact discovery-run captures")


def validate_run_against_analysis_universe(
    run: Mapping[str, Any],
    universe: Mapping[str, Any],
) -> None:
    """Require one run declaration to bind exactly to the frozen A2 analysis universe."""

    validate_discovery_run(run)
    validate_analysis_universe(universe)
    if run["analysis_universe_id"] != universe["analysis_universe_id"]:
        raise ProductDiscoveryError("Discovery run analysis_universe_id does not match the frozen A2 universe")
    for field in (
        "registry_projection_version",
        "frame_register_version",
        "population_view_id",
        "analysis_jurisdiction_scope",
        "language_scope_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
    ):
        if run[field] != universe[field]:
            raise ProductDiscoveryError(f"Discovery run {field} does not match the frozen A2 analysis universe")


def _frame_map(frames: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for frame in frames:
        validate_discovery_frame(frame)
        frame_id = str(frame["frame_id"])
        if frame_id in indexed:
            raise ProductDiscoveryError(f"Duplicate discovery frame definition: {frame_id}")
        indexed[frame_id] = frame
    return indexed


def build_capture_histories(
    captures: Sequence[Mapping[str, Any]],
    frames: Sequence[Mapping[str, Any]],
    *,
    estimation_eligible_only: bool = False,
) -> dict[str, dict[str, int]]:
    """Build binary frame histories after exact-offering deduplication."""

    indexed_frames = _frame_map(frames)
    _require_one_capture_universe(captures)
    selected_frame_ids = [
        frame_id
        for frame_id in FRAME_IDS
        if frame_id in indexed_frames
        and (not estimation_eligible_only or bool(indexed_frames[frame_id]["capture_estimation_eligible"]))
    ]
    histories: dict[str, dict[str, int]] = {}
    for capture in captures:
        frame_id = str(capture["frame_id"])
        if frame_id not in indexed_frames:
            raise ProductDiscoveryError(f"Capture references undeclared frame {frame_id}")
        validate_capture_against_frame(capture, indexed_frames[frame_id])
        if frame_id not in selected_frame_ids or capture["outcome"] != "INCLUDE_RESOLVED":
            continue
        if estimation_eligible_only and not capture["capture_estimation_eligible"]:
            continue
        offering_id = str(capture["canonical_offering_id"])
        histories.setdefault(
            offering_id,
            {candidate_frame_id: 0 for candidate_frame_id in selected_frame_ids},
        )
        histories[offering_id][frame_id] = 1
    return histories


def frame_overlap_matrix(
    captures: Sequence[Mapping[str, Any]],
    frames: Sequence[Mapping[str, Any]],
    *,
    estimation_eligible_only: bool = False,
) -> dict[str, dict[str, int]]:
    """Return pairwise unique-offering overlaps across declared frames."""

    histories = build_capture_histories(
        captures,
        frames,
        estimation_eligible_only=estimation_eligible_only,
    )
    if histories:
        frame_ids = list(next(iter(histories.values())).keys())
    else:
        indexed = _frame_map(frames)
        frame_ids = [
            frame_id
            for frame_id in FRAME_IDS
            if frame_id in indexed
            and (not estimation_eligible_only or bool(indexed[frame_id]["capture_estimation_eligible"]))
        ]

    matrix = {left: {right: 0 for right in frame_ids} for left in frame_ids}
    for history in histories.values():
        captured = [frame_id for frame_id, value in history.items() if value]
        for left in captured:
            for right in captured:
                matrix[left][right] += 1
    return matrix


def summarize_discovery_round(
    captures: Sequence[Mapping[str, Any]],
    *,
    known_identity_ids_before: Iterable[str] = (),
) -> dict[str, Any]:
    """Summarize one round without converting source observations into product counts."""

    known = set(known_identity_ids_before)
    for capture in captures:
        validate_product_capture(capture)
    _require_one_capture_universe(captures)

    frame_ids = {str(capture["frame_id"]) for capture in captures}
    round_ids = {str(capture["round_id"]) for capture in captures}
    if len(frame_ids) > 1:
        raise ProductDiscoveryError("A discovery-round summary cannot mix discovery frames")
    if len(round_ids) > 1:
        raise ProductDiscoveryError("A discovery-round summary cannot mix round_id values")

    include_captures = [capture for capture in captures if capture["outcome"] == "INCLUDE_RESOLVED"]
    unique_include_ids = {str(capture["canonical_offering_id"]) for capture in include_captures}
    new_ids = unique_include_ids - known
    known_identity_ids = unique_include_ids & known
    within_round_duplicate_count = len(include_captures) - len(unique_include_ids)
    known_identity_duplicate_count = len(known_identity_ids)
    duplicate_capture_count = known_identity_duplicate_count + within_round_duplicate_count

    outcome_counts = {
        outcome: sum(capture["outcome"] == outcome for capture in captures) for outcome in sorted(CAPTURE_OUTCOMES)
    }
    raw_count = len(captures)
    return {
        "frame_id": next(iter(frame_ids), None),
        "round_id": next(iter(round_ids), None),
        "raw_candidates": raw_count,
        "unique_resolved_include_identities": len(unique_include_ids),
        "new_resolved_include_identities": len(new_ids),
        "known_identity_duplicate_count": known_identity_duplicate_count,
        "within_round_duplicate_count": within_round_duplicate_count,
        "duplicate_capture_count": duplicate_capture_count,
        "outcome_counts": outcome_counts,
        "marginal_new_identity_yield": len(new_ids) / raw_count if raw_count else None,
        "duplicate_yield": duplicate_capture_count / raw_count if raw_count else None,
        "new_identity_ids": sorted(new_ids),
        "boundary": DISCOVERY_BOUNDARY,
    }


def summarize_discovery_contributions(
    captures: Sequence[Mapping[str, Any]],
    *,
    known_identity_ids_before: Iterable[str] = (),
) -> dict[str, dict[str, dict[str, int]]]:
    """Report language and jurisdiction contribution after exact-offering deduplication."""

    known = set(known_identity_ids_before)
    for capture in captures:
        validate_product_capture(capture)
    _require_one_capture_universe(captures)

    def summarize(field: str) -> dict[str, dict[str, int]]:
        grouped: dict[str, set[str]] = {}
        for capture in captures:
            if capture["outcome"] != "INCLUDE_RESOLVED":
                continue
            key = str(capture[field])
            grouped.setdefault(key, set()).add(str(capture["canonical_offering_id"]))
        return {
            key: {
                "unique_resolved_include_identities": len(ids),
                "new_resolved_include_identities": len(ids - known),
            }
            for key, ids in sorted(grouped.items())
        }

    return {
        "by_language": summarize("language"),
        "by_jurisdiction": summarize("jurisdiction"),
    }


def incremental_unique_identities(
    captures: Sequence[Mapping[str, Any]],
    *,
    baseline_frame_ids: Iterable[str],
    expanded_frame_ids: Iterable[str],
) -> set[str]:
    """Return exact offering identities added by expanded discovery frames."""

    _require_one_capture_universe(captures)
    baseline = set(baseline_frame_ids)
    expanded = set(expanded_frame_ids)
    if not baseline <= FRAME_ID_SET or not expanded <= FRAME_ID_SET:
        raise ProductDiscoveryError("Unknown discovery frame in incremental-yield comparison")
    if not baseline <= expanded:
        raise ProductDiscoveryError("baseline_frame_ids must be a subset of expanded_frame_ids")

    by_frame: dict[str, set[str]] = {frame_id: set() for frame_id in expanded}
    for capture in captures:
        validate_product_capture(capture)
        frame_id = str(capture["frame_id"])
        if frame_id not in expanded or capture["outcome"] != "INCLUDE_RESOLVED":
            continue
        by_frame[frame_id].add(str(capture["canonical_offering_id"]))

    baseline_ids: set[str] = set()
    expanded_ids: set[str] = set()
    for frame_id in expanded:
        expanded_ids.update(by_frame[frame_id])
        if frame_id in baseline:
            baseline_ids.update(by_frame[frame_id])
    return expanded_ids - baseline_ids


def evaluate_frame_stop(
    frame: Mapping[str, Any],
    round_summaries: Sequence[Mapping[str, Any]],
    *,
    source_exhausted: bool = False,
    budget_limit_reached: bool = False,
    unresolved_source_barrier: bool = False,
) -> str:
    """Evaluate only the predeclared protocol stop state for one frame."""

    validate_discovery_frame(frame)
    if unresolved_source_barrier:
        return "UNRESOLVED_SOURCE_BARRIER"
    if budget_limit_reached:
        return "BUDGET_COVERAGE_TERMINATION"

    rule = cast(Mapping[str, Any], frame["stopping_rule"])
    mode = rule["mode"]
    if mode == "BOUNDED_SOURCE_EXHAUSTION" and source_exhausted:
        return "BOUNDED_FRAME_EXHAUSTED"
    if mode != "MARGINAL_YIELD":
        return "CONTINUE"

    minimum_rounds = int(rule["minimum_completed_rounds"])
    consecutive = int(rule["consecutive_low_yield_rounds"])
    threshold = float(rule["maximum_marginal_new_identity_yield"])
    minimum_raw = int(rule["minimum_raw_candidates_per_round"])

    if len(round_summaries) < max(minimum_rounds, consecutive):
        return "CONTINUE"

    tail = list(round_summaries[-consecutive:])
    if len(tail) < consecutive:
        return "CONTINUE"
    if any(
        int(summary.get("raw_candidates", 0)) < minimum_raw or summary.get("marginal_new_identity_yield") is None
        for summary in tail
    ):
        return "CONTINUE"
    if all(float(summary["marginal_new_identity_yield"]) <= threshold for summary in tail):
        return "SATURATION_UNDER_DECLARED_PROTOCOL"
    return "CONTINUE"
