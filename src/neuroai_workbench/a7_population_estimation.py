"""Validators for Release-A A7 capture-history compile and pre-fit model-spec lock.

Compiles exact-offering capture histories across F1–F11 under one analysis
universe and freezes the population-model specification before any unseen-
population model is fit. Freeze alone does not emit the Population Estimation
Report, allocate canonical identities, or start A8 / A-G.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import CHECKPOINT_ID, _packet_content_sha256
from neuroai_workbench.a6_saturation_analysis import A6_PREREG_SHA256, A6_STUDY_PACKET_SHA256
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_FRAME_REGISTER_BLOB_SHA,
    A2_JURISDICTION_SCOPE,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_LANGUAGE_SCOPE_ID,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_IDS,
    FRAME_REGISTER_VERSION,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
    identity_set_digest,
    validate_product_capture,
)
from neuroai_workbench.release_a_preregistration import (
    FRAME_SET_SENSITIVITIES,
    PREREGISTRATION_VERSION,
    PRIMARY_ESTIMATION_FRAME_IDS,
    REQUIRED_DIAGNOSTICS,
    REQUIRED_MODEL_FAMILIES,
    REQUIRED_SENSITIVITIES,
    validate_estimation_universe,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

A7_CAPTURE_HISTORY_RESOURCE = "RELEASE_A_A7_CAPTURE_HISTORY_DATASET.v1.0.json"
A7_CAPTURE_HISTORY_ID = "RELEASE_A_A7_CAPTURE_HISTORY_DATASET_v1.0"
A7_CAPTURE_HISTORY_SHA256 = "f3718778dada33bafd55c7d2ce45aa0305eb04db15ffad85c2306393004d0af8"
A7_ELIGIBLE_CAPTURE_RECORDS_SHA256 = "c1c1eb216285941085a4f158cbcf0d076216e36f9646a98f4fa841da0f327851"

A7_MODEL_SPEC_RESOURCE = "RELEASE_A_A7_POPULATION_MODEL_SPECIFICATION.v1.0.json"
A7_MODEL_SPEC_ID = "RELEASE_A_A7_POPULATION_MODEL_SPECIFICATION_v1.0"
A7_MODEL_SPEC_SHA256 = "9986bb58515955a53962df6bae5d79e250a9c9076c74f030347c82f52d3ce04b"
A7_STUDY_ID = "RELEASE_A_A7_PRODUCT_POPULATION_ESTIMATION_REPORT_v1.0"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
N_OBSERVED = 6
OBSERVED_OFFERING_IDS = (
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
)

CAPTURE_PROJECTION_FIELDS = (
    "capture_id",
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
    "analysis_jurisdiction_scope",
    "language_scope_id",
    "population_view_id",
    "world_time_cutoff",
    "knowledge_time_cutoff",
    "world_time_alignment",
    "world_time_support_ref",
    "boundary",
)

IDENTIFIABILITY_THRESHOLDS = {
    "min_estimator_eligible_distinct_offerings": 20,
    "min_primary_frames_with_positive_eligible_capture": 4,
    "min_offerings_captured_in_gte_2_eligible_frames": 10,
    "min_pairwise_positive_overlaps_among_positive_frames": 3,
    "reject_if_majority_eligible_frames_are_structural_zeros": True,
}

FAIL_CLOSED_REASONS = (
    "CAPTURE_STRUCTURE_NON_IDENTIFIABLE",
    "CAPTURE_TABLE_TOO_SPARSE",
    "INSUFFICIENT_MULTI_FRAME_OVERLAP",
    "INDEPENDENCE_ASSUMPTION_CONTRADICTED",
    "NO_HEADLINE_ADMISSIBLE_MODEL",
    "STRATUM_SUPPORT_INADEQUATE",
    "BAYESIAN_SENSITIVITY_NOT_JUSTIFIED",
)

VALID_NO_ESTIMATE_OUTCOME = "NO_DEFENSIBLE_UNSEEN_POPULATION_ESTIMATE_UNDER_PREREGISTERED_ACCEPTANCE_CRITERIA"

A7_CAPTURE_HISTORY_BOUNDARY = (
    "A7 capture-history dataset compiles exact-offering discovery captures across "
    "F1-F11 under one analysis universe for pre-fit model binding. It does not fit "
    "unseen-population models, allocate canonical identity, establish global "
    "completeness, market share, effectiveness, S2 publication authority, or v4.2 "
    "assessment effect. Estimator-eligible subset excludes F7/F9/F11."
)

A7_MODEL_SPEC_BOUNDARY = (
    "A7 population-model specification lock freezes model families, "
    "interaction/stratification/Bayesian rules, uncertainty construction, late-round "
    "holdback interpretation, and identifiability/fail-closed thresholds before "
    "fitting. It binds the observed offering universe and estimator-eligible capture "
    "histories without using estimates to choose a preferred specification. Freeze "
    "alone does not fit models, emit the Population Estimation Report, allocate "
    "identity, or establish global completeness, market share, effectiveness, S2 "
    "publication authority, or v4.2 assessment effect."
)


def content_digest(material: Mapping[str, Any], *, exclude: str) -> str:
    """Return deterministic SHA-256 for a freeze artifact, excluding a self-digest field."""

    payload = {key: value for key, value in material.items() if key != exclude}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def records_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """Return deterministic SHA-256 over a list of capture projections."""

    encoded = json.dumps(
        list(records),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_resource(resource_name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(resource_name).read_text(encoding="utf-8")),
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductDiscoveryError(f"{label} must be an array")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be a boolean")
    return value


def _require_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be an integer")
    return value


def a7_freeze_does_not_fit_models() -> str:
    """Freeze alone never implies fitted unseen-population estimates."""

    return "PREREGISTERED_AWAITING_EXECUTION"


def project_capture_record(capture: Mapping[str, Any], *, source_packet_id: str) -> dict[str, Any]:
    """Project one capture onto the A7 capture-history row schema."""

    validate_product_capture(capture)
    row = {field: capture[field] for field in CAPTURE_PROJECTION_FIELDS}
    row["source_packet_id"] = source_packet_id
    return row


def compile_capture_history_rows_from_resources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recompile capture projections and source bindings from frozen A2 packets."""

    sources: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    package = files(RESOURCE_PACKAGE)
    for entry in sorted(package.iterdir(), key=lambda item: item.name):
        name = entry.name
        if not name.startswith("RELEASE_A_A2") or not name.endswith(".json"):
            continue
        if name.startswith("RELEASE_A_A7"):
            continue
        packet = cast(dict[str, Any], json.loads(entry.read_text(encoding="utf-8")))
        captures = packet.get("captures")
        if not isinstance(captures, list) or not captures:
            continue
        packet_id = _require_str(packet.get("packet_id"), "packet_id")
        packet_sha = _require_str(packet.get("packet_sha256"), "packet_sha256")
        if _packet_content_sha256(packet) != packet_sha:
            raise ProductDiscoveryError(f"source packet digest drift: {packet_id}")
        sources.append(
            {
                "source_packet_id": packet_id,
                "source_packet_resource": name,
                "source_packet_sha256": packet_sha,
                "capture_count": len(captures),
            }
        )
        for capture in captures:
            rows.append(project_capture_record(_require_mapping(capture, "capture"), source_packet_id=packet_id))

    rows.sort(key=lambda row: (str(row["frame_id"]), str(row["round_id"]), str(row["capture_id"])))
    sources.sort(key=lambda item: str(item["source_packet_id"]))
    return sources, rows


def estimator_eligible_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return estimator-eligible capture rows (no F7/F9/F11)."""

    eligible: list[dict[str, Any]] = []
    for row in rows:
        if row.get("capture_estimation_eligible") is not True:
            continue
        frame_id = str(row["frame_id"])
        if frame_id in PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
            raise ProductDiscoveryError(f"estimator-eligible capture from excluded frame {frame_id} is prohibited")
        if row.get("outcome") != "INCLUDE_RESOLVED":
            raise ProductDiscoveryError("estimator-eligible capture must be INCLUDE_RESOLVED")
        eligible.append(dict(row))
    return eligible


def offering_binary_histories(
    eligible_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build binary frame histories for estimator-eligible offerings."""

    histories: dict[str, dict[str, int]] = {}
    for row in eligible_rows:
        offering_id = str(row["canonical_offering_id"])
        frame_id = str(row["frame_id"])
        if frame_id not in PRIMARY_ESTIMATION_FRAME_IDS:
            raise ProductDiscoveryError(f"eligible capture frame {frame_id} outside primary estimation set")
        histories.setdefault(
            offering_id,
            {candidate: 0 for candidate in PRIMARY_ESTIMATION_FRAME_IDS},
        )
        histories[offering_id][frame_id] = 1
    return [
        {"canonical_offering_id": offering_id, "frame_capture_vector": histories[offering_id]}
        for offering_id in sorted(histories)
    ]


def evaluate_identifiability_gate(
    histories: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate predeclared identifiability thresholds without fitting models."""

    rules = dict(thresholds or IDENTIFIABILITY_THRESHOLDS)
    vectors = [dict(cast(Mapping[str, Any], item["frame_capture_vector"])) for item in histories]
    n_offerings = len(vectors)
    frames_with_capture = [
        frame_id
        for frame_id in PRIMARY_ESTIMATION_FRAME_IDS
        if any(int(vector.get(frame_id, 0)) == 1 for vector in vectors)
    ]
    multi_frame = sum(1 for vector in vectors if sum(int(vector[frame]) for frame in PRIMARY_ESTIMATION_FRAME_IDS) >= 2)
    pairwise_overlaps = 0
    for index, left in enumerate(frames_with_capture):
        for right in frames_with_capture[index + 1 :]:
            overlap = sum(1 for vector in vectors if int(vector[left]) == 1 and int(vector[right]) == 1)
            if overlap > 0:
                pairwise_overlaps += 1
    structural_zero_count = len(PRIMARY_ESTIMATION_FRAME_IDS) - len(frames_with_capture)
    majority_zeros = structural_zero_count > (len(PRIMARY_ESTIMATION_FRAME_IDS) / 2)

    failures: list[str] = []
    if n_offerings < int(rules["min_estimator_eligible_distinct_offerings"]):
        failures.append("CAPTURE_TABLE_TOO_SPARSE")
    if len(frames_with_capture) < int(rules["min_primary_frames_with_positive_eligible_capture"]):
        failures.append("CAPTURE_STRUCTURE_NON_IDENTIFIABLE")
    if multi_frame < int(rules["min_offerings_captured_in_gte_2_eligible_frames"]):
        failures.append("INSUFFICIENT_MULTI_FRAME_OVERLAP")
    if pairwise_overlaps < int(rules["min_pairwise_positive_overlaps_among_positive_frames"]):
        failures.append("INSUFFICIENT_MULTI_FRAME_OVERLAP")
    if bool(rules["reject_if_majority_eligible_frames_are_structural_zeros"]) and majority_zeros:
        failures.append("CAPTURE_STRUCTURE_NON_IDENTIFIABLE")

    unique_failures = sorted(set(failures))
    return {
        "n_estimator_eligible_distinct_offerings": n_offerings,
        "primary_frames_with_positive_eligible_capture": frames_with_capture,
        "n_primary_frames_with_positive_eligible_capture": len(frames_with_capture),
        "n_offerings_captured_in_gte_2_eligible_frames": multi_frame,
        "n_pairwise_positive_overlaps_among_positive_frames": pairwise_overlaps,
        "n_structural_zero_primary_frames": structural_zero_count,
        "majority_primary_frames_structural_zeros": majority_zeros,
        "identifiability_gate_passed": not unique_failures,
        "fail_closed_reasons": unique_failures,
        "valid_outcome_if_failed": VALID_NO_ESTIMATE_OUTCOME,
    }


def load_default_a7_capture_history_dataset() -> dict[str, Any]:
    """Load the frozen A7 capture-history dataset."""

    dataset = _load_resource(A7_CAPTURE_HISTORY_RESOURCE)
    validate_a7_capture_history_dataset(dataset)
    if dataset["dataset_sha256"] != A7_CAPTURE_HISTORY_SHA256:
        raise ProductDiscoveryError("Loaded A7 capture-history digest drifted from frozen A7_CAPTURE_HISTORY_SHA256")
    return dataset


def load_default_a7_population_model_specification() -> dict[str, Any]:
    """Load the frozen A7 population-model specification."""

    spec = _load_resource(A7_MODEL_SPEC_RESOURCE)
    validate_a7_population_model_specification(spec)
    if spec["specification_sha256"] != A7_MODEL_SPEC_SHA256:
        raise ProductDiscoveryError("Loaded A7 model-spec digest drifted from frozen A7_MODEL_SPEC_SHA256")
    return spec


def validate_a7_capture_history_dataset(dataset: Mapping[str, Any]) -> None:
    """Validate the frozen A7 capture-history compile."""

    required = (
        "dataset_id",
        "dataset_sha256",
        "status",
        "compiled_at",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "observed_offering_ids",
        "observed_offering_set_sha256",
        "n_observed",
        "population_view_id",
        "language_scope_id",
        "identity_level",
        "frame_register_version",
        "frame_register_blob_sha",
        "a6_preregistration_sha256",
        "a6_study_sha256",
        "source_packet_bindings",
        "capture_record_count",
        "capture_records_sha256",
        "estimator_eligible_capture_count",
        "estimator_eligible_capture_records_sha256",
        "estimator_excluded_frame_ids",
        "primary_estimation_frame_ids",
        "estimator_eligible_offering_binary_histories",
        "estimator_eligible_offering_binary_histories_sha256",
        "capture_records",
        "mixed_universe_policy",
        "compilation_rule",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in dataset]
    if missing:
        raise ProductDiscoveryError("A7 capture-history missing fields: " + ", ".join(missing))

    if dataset["dataset_id"] != A7_CAPTURE_HISTORY_ID:
        raise ProductDiscoveryError(f"dataset_id must be {A7_CAPTURE_HISTORY_ID}")
    if dataset["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if content_digest(dataset, exclude="dataset_sha256") != dataset["dataset_sha256"]:
        raise ProductDiscoveryError("dataset_sha256 does not match content digest")

    if dataset["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal the frozen A2 analysis universe")
    if dataset["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff must equal the frozen A2 world cutoff")
    if dataset["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff must equal the frozen A2 knowledge cutoff")
    if dataset["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id must equal the frozen A2 checkpoint")
    if dataset["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 must equal the frozen A2 checkpoint")

    observed_ids = [str(item) for item in _require_list(dataset["observed_offering_ids"], "observed_offering_ids")]
    if observed_ids != list(OBSERVED_OFFERING_IDS):
        raise ProductDiscoveryError("observed_offering_ids must equal the frozen A1 known-identity set")
    if identity_set_digest(observed_ids) != dataset["observed_offering_set_sha256"]:
        raise ProductDiscoveryError("observed_offering_set_sha256 digest mismatch")
    if dataset["observed_offering_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("observed_offering_set_sha256 must equal A1 known-identity digest")
    if _require_int(dataset["n_observed"], "n_observed") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed must be {N_OBSERVED}")

    if dataset["population_view_id"] != "A-P1":
        raise ProductDiscoveryError("population_view_id must be A-P1 for the primary capture-history compile")
    if dataset["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id drift")
    if dataset["identity_level"] != "OFFERING":
        raise ProductDiscoveryError("identity_level must be OFFERING")
    if dataset["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("frame_register_version drift")
    if dataset["frame_register_blob_sha"] != A2_FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha drift")
    if dataset["a6_preregistration_sha256"] != A6_PREREG_SHA256:
        raise ProductDiscoveryError("a6_preregistration_sha256 drift")
    if dataset["a6_study_sha256"] != A6_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a6_study_sha256 drift")
    if dataset["mixed_universe_policy"] != "REJECT":
        raise ProductDiscoveryError("mixed_universe_policy must be REJECT")
    if dataset["boundary"] != A7_CAPTURE_HISTORY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    if tuple(dataset["estimator_excluded_frame_ids"]) != tuple(sorted(PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS)):
        raise ProductDiscoveryError("estimator_excluded_frame_ids must be F7/F9/F11")
    if tuple(dataset["primary_estimation_frame_ids"]) != PRIMARY_ESTIMATION_FRAME_IDS:
        raise ProductDiscoveryError("primary_estimation_frame_ids must equal F1-F6,F8,F10")

    gate = _require_mapping(dataset["execution_gate"], "execution_gate")
    for field in (
        "freeze_alone_does_not_fit_models",
        "does_not_emit_a7_estimation_report",
        "does_not_start_a8_or_ag",
        "f7_f9_f11_remain_estimator_excluded",
    ):
        if gate.get(field) is not True:
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    records = [
        _require_mapping(item, "capture_record")
        for item in _require_list(dataset["capture_records"], "capture_records")
    ]
    if len(records) != _require_int(dataset["capture_record_count"], "capture_record_count"):
        raise ProductDiscoveryError("capture_record_count does not match capture_records length")
    if records_digest(records) != dataset["capture_records_sha256"]:
        raise ProductDiscoveryError("capture_records_sha256 does not match capture_records")

    universes = {str(row["analysis_universe_id"]) for row in records}
    if universes != {DEFAULT_ANALYSIS_UNIVERSE_ID}:
        raise ProductDiscoveryError("mixed or unexpected analysis_universe_id in capture_records")
    for row in records:
        for field, expected in (
            ("world_time_cutoff", A2_WORLD_TIME_CUTOFF),
            ("knowledge_time_cutoff", A2_KNOWLEDGE_TIME_CUTOFF),
            ("analysis_jurisdiction_scope", A2_JURISDICTION_SCOPE),
            ("language_scope_id", A2_LANGUAGE_SCOPE_ID),
            ("population_view_id", "A-P1"),
            ("frame_register_version", FRAME_REGISTER_VERSION),
        ):
            if row.get(field) != expected:
                raise ProductDiscoveryError(f"capture_record {field} incompatible with frozen universe")
        if str(row["frame_id"]) not in FRAME_IDS:
            raise ProductDiscoveryError(f"unknown frame_id in capture_record: {row['frame_id']}")

    eligible = estimator_eligible_rows(records)
    if len(eligible) != _require_int(dataset["estimator_eligible_capture_count"], "estimator_eligible_capture_count"):
        raise ProductDiscoveryError("estimator_eligible_capture_count mismatch")
    if records_digest(eligible) != dataset["estimator_eligible_capture_records_sha256"]:
        raise ProductDiscoveryError("estimator_eligible_capture_records_sha256 mismatch")
    if any(str(row["frame_id"]) in PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS for row in eligible):
        raise ProductDiscoveryError("estimator-eligible subset must contain no F7/F9/F11 records")

    histories = [
        _require_mapping(item, "binary_history")
        for item in _require_list(
            dataset["estimator_eligible_offering_binary_histories"],
            "estimator_eligible_offering_binary_histories",
        )
    ]
    expected_histories = offering_binary_histories(eligible)
    if histories != expected_histories:
        raise ProductDiscoveryError("estimator_eligible_offering_binary_histories do not match eligible captures")
    if records_digest(histories) != dataset["estimator_eligible_offering_binary_histories_sha256"]:
        raise ProductDiscoveryError("estimator_eligible_offering_binary_histories_sha256 mismatch")

    sources = [
        _require_mapping(item, "source_packet_binding")
        for item in _require_list(dataset["source_packet_bindings"], "source_packet_bindings")
    ]
    recompiled_sources, recompiled_rows = compile_capture_history_rows_from_resources()
    if sources != recompiled_sources:
        raise ProductDiscoveryError("source_packet_bindings do not reproduce from frozen A2 packets")
    if records != recompiled_rows:
        raise ProductDiscoveryError("capture_records do not reproduce from frozen A2 packets")


def validate_a7_population_model_specification(spec: Mapping[str, Any]) -> None:
    """Validate the frozen A7 population-model specification lock."""

    required = (
        "specification_id",
        "specification_sha256",
        "status",
        "study_id",
        "census_registered_at",
        "preregistration_version",
        "analysis_universe_id",
        "estimation_universe_id",
        "estimation_universe",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "observed_offering_set_sha256",
        "n_observed_declared",
        "capture_history_dataset_id",
        "capture_history_dataset_sha256",
        "estimator_eligible_capture_records_sha256",
        "a6_preregistration_sha256",
        "a6_study_sha256",
        "predeclaration_rule",
        "model_families",
        "model_family_specifications",
        "frame_set_sensitivities",
        "late_round_holdback",
        "acceptance_and_fail_closed_criteria",
        "required_diagnostics",
        "required_sensitivities",
        "reporting_policy_id",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in spec]
    if missing:
        raise ProductDiscoveryError("A7 model-spec missing fields: " + ", ".join(missing))

    if spec["specification_id"] != A7_MODEL_SPEC_ID:
        raise ProductDiscoveryError(f"specification_id must be {A7_MODEL_SPEC_ID}")
    if spec["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if spec["study_id"] != A7_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A7_STUDY_ID}")
    if content_digest(spec, exclude="specification_sha256") != spec["specification_sha256"]:
        raise ProductDiscoveryError("specification_sha256 does not match content digest")

    if spec["preregistration_version"] != PREREGISTRATION_VERSION:
        raise ProductDiscoveryError("preregistration_version drift")
    if spec["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal the frozen A2 analysis universe")
    if spec["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if spec["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if spec["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id drift")
    if spec["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 drift")
    if spec["observed_offering_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("observed_offering_set_sha256 drift")
    if _require_int(spec["n_observed_declared"], "n_observed_declared") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed_declared must be {N_OBSERVED}")
    if spec["capture_history_dataset_id"] != A7_CAPTURE_HISTORY_ID:
        raise ProductDiscoveryError("capture_history_dataset_id drift")
    if spec["capture_history_dataset_sha256"] != A7_CAPTURE_HISTORY_SHA256:
        raise ProductDiscoveryError("capture_history_dataset_sha256 drift")
    if spec["estimator_eligible_capture_records_sha256"] != A7_ELIGIBLE_CAPTURE_RECORDS_SHA256:
        raise ProductDiscoveryError("estimator_eligible_capture_records_sha256 drift")
    if spec["a6_preregistration_sha256"] != A6_PREREG_SHA256:
        raise ProductDiscoveryError("a6_preregistration_sha256 drift")
    if spec["a6_study_sha256"] != A6_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a6_study_sha256 drift")
    if spec["boundary"] != A7_MODEL_SPEC_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")
    if spec["reporting_policy_id"] != "RELEASE_A_MODEL_ENVELOPE_REPORTING_v1.0":
        raise ProductDiscoveryError("reporting_policy_id drift")

    universe = _require_mapping(spec["estimation_universe"], "estimation_universe")
    validate_estimation_universe(universe)
    if universe["universe_id"] != spec["estimation_universe_id"]:
        raise ProductDiscoveryError("estimation_universe_id does not match estimation_universe.universe_id")

    families = tuple(_require_list(spec["model_families"], "model_families"))
    if set(families) != set(REQUIRED_MODEL_FAMILIES) or len(families) != len(REQUIRED_MODEL_FAMILIES):
        raise ProductDiscoveryError("model_families must equal the preregistered comparison set")
    family_specs = _require_mapping(spec["model_family_specifications"], "model_family_specifications")
    if set(family_specs) != set(REQUIRED_MODEL_FAMILIES):
        raise ProductDiscoveryError("model_family_specifications must cover every preregistered family")

    pairwise = _require_mapping(family_specs["PAIRWISE_CAPTURE_RECAPTURE_DIAGNOSTIC"], "pairwise family")
    if pairwise.get("headline_admissible") is not False:
        raise ProductDiscoveryError("pairwise capture-recapture must remain diagnostic-only")
    observed_only = _require_mapping(family_specs["OBSERVED_ONLY_BASELINE"], "observed-only family")
    if observed_only.get("fits_unseen_population") is not False:
        raise ProductDiscoveryError("observed-only baseline must not fit an unseen population")

    sensitivities = _require_mapping(spec["frame_set_sensitivities"], "frame_set_sensitivities")
    if set(sensitivities) != set(FRAME_SET_SENSITIVITIES):
        raise ProductDiscoveryError("frame_set_sensitivities keys drift")
    for key, frames in FRAME_SET_SENSITIVITIES.items():
        if tuple(sensitivities[key]) != frames:
            raise ProductDiscoveryError(f"frame_set_sensitivities.{key} drift")

    if set(_require_list(spec["required_diagnostics"], "required_diagnostics")) != REQUIRED_DIAGNOSTICS:
        raise ProductDiscoveryError("required_diagnostics drift")
    if set(_require_list(spec["required_sensitivities"], "required_sensitivities")) != REQUIRED_SENSITIVITIES:
        raise ProductDiscoveryError("required_sensitivities drift")

    holdback = _require_mapping(spec["late_round_holdback"], "late_round_holdback")
    if holdback.get("policy_id") != "RELEASE_A_LATE_ROUND_HOLDBACK_v1.0":
        raise ProductDiscoveryError("late_round_holdback.policy_id drift")
    if holdback.get("final_estimates_refit_on_all_eligible_data_after_diagnostic") is not True:
        raise ProductDiscoveryError("late_round holdback must require final refit after diagnostic")

    criteria = _require_mapping(spec["acceptance_and_fail_closed_criteria"], "acceptance_and_fail_closed_criteria")
    for field in (
        "report_n_observed_separately_from_any_estimate",
        "no_forced_point_estimate_when_inadmissible",
        "headline_requires_at_least_one_admissible_non_diagnostic_family",
        "model_total_below_n_observed_is_incoherent_not_floored",
    ):
        if criteria.get(field) is not True:
            raise ProductDiscoveryError(f"acceptance_and_fail_closed_criteria.{field} must be true")
    thresholds = _require_mapping(criteria.get("identifiability_thresholds"), "identifiability_thresholds")
    for key, expected in IDENTIFIABILITY_THRESHOLDS.items():
        if thresholds.get(key) != expected:
            raise ProductDiscoveryError(f"identifiability_thresholds.{key} drift")
    reasons = tuple(_require_list(criteria.get("sparseness_fail_closed_reasons"), "sparseness_fail_closed_reasons"))
    if set(reasons) != set(FAIL_CLOSED_REASONS) or len(reasons) != len(FAIL_CLOSED_REASONS):
        raise ProductDiscoveryError("sparseness_fail_closed_reasons drift")
    if criteria.get("valid_scientific_outcome_without_estimate") != VALID_NO_ESTIMATE_OUTCOME:
        raise ProductDiscoveryError("valid_scientific_outcome_without_estimate drift")

    gate = _require_mapping(spec["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_capture_history_before_fit",
        "freeze_alone_does_not_fit_models",
        "does_not_emit_a7_estimation_report",
        "does_not_start_a8_or_ag",
        "specification_immutable_without_named_successor",
        "f7_f9_f11_remain_estimator_excluded",
    ):
        if gate.get(field) is not True:
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    # Binding check: specification must not contain fitted estimates.
    forbidden_result_keys = {
        "n_estimated",
        "n_unobserved",
        "headline_estimate",
        "model_fit_results",
        "fitted_model_totals",
    }
    if forbidden_result_keys & set(spec):
        raise ProductDiscoveryError("model-spec lock must not contain fitted estimate fields")


A7_STUDY_RESOURCE = "RELEASE_A_A7_PRODUCT_POPULATION_ESTIMATION_REPORT.v1.0.json"
A7_STUDY_PACKET_ID = "RELEASE_A_A7_PRODUCT_POPULATION_ESTIMATION_REPORT_v1.0"
A7_STUDY_PACKET_SHA256 = "a533cc52517f8611770910597a83a60745fbb7d781ac73f2a7b3890031d371eb"

A7_STUDY_BOUNDARY = (
    "Repository-safe A7 Product Population Estimation Report under the frozen "
    "capture-history and model-specification digests. N_observed is reported "
    "separately from any estimate. Because the preregistered identifiability/"
    "sparseness gate failed, no unseen-population point estimate or headline "
    "interval is emitted. This does not establish global completeness, market "
    "share, effectiveness, S2 publication authority, or v4.2 assessment effect. "
    "Does not start A8 or A-G."
)

EXPECTED_FAIL_CLOSED_REASONS = (
    "CAPTURE_TABLE_TOO_SPARSE",
    "INSUFFICIENT_MULTI_FRAME_OVERLAP",
)

POORLY_OBSERVED_CLASS_IDS = (
    "REGULATORY_TRIAL_CAPTURE_SPARSE",
    "LOCAL_LANGUAGE_STRUCTURAL_ZERO",
    "PATENT_CROSSOVER_STRUCTURAL_ZERO",
    "PURPOSIVE_DIAGNOSTIC_ONLY_FRAMES",
    "OPEN_WORLD_KNOWN_IDENTITY_ONLY",
)


def load_default_a7_population_estimation_report() -> dict[str, Any]:
    """Load the frozen A7 Product Population Estimation Report."""

    packet = _load_resource(A7_STUDY_RESOURCE)
    validate_a7_population_estimation_report(packet)
    if packet["packet_sha256"] != A7_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A7 report digest drifted from frozen A7_STUDY_PACKET_SHA256")
    return packet


def validate_a7_population_estimation_report(packet: Mapping[str, Any]) -> None:
    """Validate the executed A7 estimation report against frozen pre-fit locks."""

    required = (
        "packet_id",
        "packet_sha256",
        "status",
        "assembled_on",
        "study_id",
        "model_specification_id",
        "model_specification_sha256",
        "capture_history_dataset_id",
        "capture_history_dataset_sha256",
        "estimator_eligible_capture_records_sha256",
        "analysis_universe_id",
        "estimation_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "observed_offering_ids",
        "observed_offering_set_sha256",
        "n_observed",
        "n_estimated",
        "n_unobserved",
        "coverage_estimated",
        "estimation_outcome",
        "fail_closed_outcome",
        "fail_closed_reasons",
        "identifiability_diagnostics",
        "assumptions",
        "dependence_diagnostics",
        "model_family_results",
        "headline_admissible_models",
        "admissible_model_envelope",
        "interval_or_sensitivity",
        "classes_likely_poorly_observed",
        "authority_controls",
        "key_result",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A7 report packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != A7_STUDY_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {A7_STUDY_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["study_id"] != A7_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A7_STUDY_ID}")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")

    if packet["model_specification_id"] != A7_MODEL_SPEC_ID:
        raise ProductDiscoveryError("model_specification_id drift")
    if packet["model_specification_sha256"] != A7_MODEL_SPEC_SHA256:
        raise ProductDiscoveryError("model_specification_sha256 drift")
    if packet["capture_history_dataset_id"] != A7_CAPTURE_HISTORY_ID:
        raise ProductDiscoveryError("capture_history_dataset_id drift")
    if packet["capture_history_dataset_sha256"] != A7_CAPTURE_HISTORY_SHA256:
        raise ProductDiscoveryError("capture_history_dataset_sha256 drift")
    if packet["estimator_eligible_capture_records_sha256"] != A7_ELIGIBLE_CAPTURE_RECORDS_SHA256:
        raise ProductDiscoveryError("estimator_eligible_capture_records_sha256 drift")

    if packet["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal the frozen A2 analysis universe")
    if packet["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if packet["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if packet["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id drift")
    if packet["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 drift")

    observed_ids = [str(item) for item in _require_list(packet["observed_offering_ids"], "observed_offering_ids")]
    if observed_ids != list(OBSERVED_OFFERING_IDS):
        raise ProductDiscoveryError("observed_offering_ids must equal the frozen A1 known-identity set")
    if identity_set_digest(observed_ids) != packet["observed_offering_set_sha256"]:
        raise ProductDiscoveryError("observed_offering_set_sha256 digest mismatch")
    if packet["observed_offering_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("observed_offering_set_sha256 must equal A1 known-identity digest")
    if _require_int(packet["n_observed"], "n_observed") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed must be {N_OBSERVED}")

    # Observed count must remain separate from any estimate; fail-closed emits nulls.
    if packet["n_estimated"] is not None:
        raise ProductDiscoveryError("fail-closed report must not emit n_estimated")
    if packet["n_unobserved"] is not None:
        raise ProductDiscoveryError("fail-closed report must not emit n_unobserved")
    if packet["coverage_estimated"] is not None:
        raise ProductDiscoveryError("fail-closed report must not emit coverage_estimated")
    if packet["estimation_outcome"] != "FAIL_CLOSED":
        raise ProductDiscoveryError("estimation_outcome must be FAIL_CLOSED under sparse capture structure")
    if packet["fail_closed_outcome"] != VALID_NO_ESTIMATE_OUTCOME:
        raise ProductDiscoveryError("fail_closed_outcome drift")
    reasons = tuple(_require_list(packet["fail_closed_reasons"], "fail_closed_reasons"))
    if set(reasons) != set(EXPECTED_FAIL_CLOSED_REASONS):
        raise ProductDiscoveryError("fail_closed_reasons must match the frozen sparse-gate outcome")

    dataset = load_default_a7_capture_history_dataset()
    spec = load_default_a7_population_model_specification()
    if packet["estimation_universe_id"] != spec["estimation_universe_id"]:
        raise ProductDiscoveryError("estimation_universe_id must match frozen model-spec")
    expected_gate = evaluate_identifiability_gate(dataset["estimator_eligible_offering_binary_histories"])
    diagnostics = _require_mapping(packet["identifiability_diagnostics"], "identifiability_diagnostics")
    if diagnostics != expected_gate:
        raise ProductDiscoveryError("identifiability_diagnostics must reproduce from frozen capture histories")
    if diagnostics.get("identifiability_gate_passed") is not False:
        raise ProductDiscoveryError("identifiability gate must fail closed for this sparse capture table")

    assumptions = _require_mapping(packet["assumptions"], "assumptions")
    for field in (
        "f10_patent_leads_are_not_products",
        "independence_not_assumed_for_headline",
        "no_forced_point_estimate_when_inadmissible",
        "model_total_below_n_observed_is_incoherent_not_floored",
    ):
        if assumptions.get(field) is not True:
            raise ProductDiscoveryError(f"assumptions.{field} must be true")
    if tuple(assumptions.get("primary_estimation_frames", ())) != PRIMARY_ESTIMATION_FRAME_IDS:
        raise ProductDiscoveryError("assumptions.primary_estimation_frames drift")
    if set(assumptions.get("estimator_excluded_frames", ())) != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("assumptions.estimator_excluded_frames drift")

    dependence = _require_mapping(packet["dependence_diagnostics"], "dependence_diagnostics")
    matrix = _require_mapping(dependence.get("pairwise_unique_offering_overlap_matrix"), "overlap matrix")
    if set(matrix) != set(PRIMARY_ESTIMATION_FRAME_IDS):
        raise ProductDiscoveryError("pairwise overlap matrix must cover primary estimation frames")
    if list(dependence.get("structural_zero_primary_frames", [])) != ["F3", "F8", "F10"]:
        raise ProductDiscoveryError("structural_zero_primary_frames must be F3/F8/F10")

    family_results = [
        _require_mapping(item, "model_family_result")
        for item in _require_list(packet["model_family_results"], "model_family_results")
    ]
    if [item["model_family"] for item in family_results] != list(REQUIRED_MODEL_FAMILIES):
        raise ProductDiscoveryError("model_family_results must follow the preregistered family order")
    for item in family_results:
        if item.get("headline_admissible") is not False:
            raise ProductDiscoveryError(f"{item['model_family']} must not be headline-admissible")
        if item.get("fitted_unseen_estimate") is not False:
            raise ProductDiscoveryError(f"{item['model_family']} must not emit a fitted unseen estimate")
    if _require_list(packet["headline_admissible_models"], "headline_admissible_models"):
        raise ProductDiscoveryError("headline_admissible_models must be empty under fail-closed")
    if packet["admissible_model_envelope"] is not None:
        raise ProductDiscoveryError("admissible_model_envelope must be null under fail-closed")
    if packet["interval_or_sensitivity"] is not None:
        raise ProductDiscoveryError("interval_or_sensitivity must be null under fail-closed")

    poorly = [
        _require_mapping(item, "poorly_observed_class")
        for item in _require_list(packet["classes_likely_poorly_observed"], "classes_likely_poorly_observed")
    ]
    if [item["class_id"] for item in poorly] != list(POORLY_OBSERVED_CLASS_IDS):
        raise ProductDiscoveryError("classes_likely_poorly_observed class_id set drift")

    controls = _require_mapping(packet["authority_controls"], "authority_controls")
    for field in (
        "does_not_start_a8_or_ag",
        "does_not_allocate_canonical_identity",
        "does_not_claim_global_completeness",
        "observed_count_reported_separately_from_estimate",
        "no_headline_unseen_population_estimate",
    ):
        if controls.get(field) is not True:
            raise ProductDiscoveryError(f"authority_controls.{field} must be true")

    key = _require_mapping(packet["key_result"], "key_result")
    if key.get("n_observed") != N_OBSERVED:
        raise ProductDiscoveryError("key_result.n_observed drift")
    if key.get("n_estimated") is not None:
        raise ProductDiscoveryError("key_result must not emit n_estimated under fail-closed")
    if key.get("estimation_outcome") != "FAIL_CLOSED":
        raise ProductDiscoveryError("key_result.estimation_outcome must be FAIL_CLOSED")
    if key.get("fail_closed_outcome") != VALID_NO_ESTIMATE_OUTCOME:
        raise ProductDiscoveryError("key_result.fail_closed_outcome drift")

    if packet["next_required_state"] != "A8_PRODUCT_POPULATION_RELEASE_PACKAGE":
        raise ProductDiscoveryError("next_required_state must be A8_PRODUCT_POPULATION_RELEASE_PACKAGE")
    if packet["boundary"] != A7_STUDY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")
