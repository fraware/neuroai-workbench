from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
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
    load_f9_actor_seed_register,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
F9_ACTOR_ENUMERATION_PROCEDURE_RESOURCE = "RELEASE_A_F9_ACTOR_ENUMERATION_PROCEDURE.v1.0.json"
F9_ACTOR_ENUMERATION_PROCEDURE_ID = "RELEASE_A_F9_ACTOR_ENUMERATION_PROCEDURE_v1.0"
F9_ACTOR_ENUMERATION_PROCEDURE_SHA256 = "402af2464750688b6f7cb36f3444c113871836d4dd4fe9feac17350431710e72"
F9_ACTOR_SEED_REGISTER_ID = "RELEASE_A_F9_ACTOR_SEED_REGISTER_v1.0"
F9_ACTOR_SEED_REGISTER_BLOB_SHA = "ddee79131b4eaf73193a1432039bf0eb470aa776"
F9_FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
F9_QUERY_FAMILY = "FROZEN_ACTOR_PRODUCT_ENUMERATION"

F9_COMPLETION_STATES = frozenset(
    {
        "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL",
        "ACTOR_ENUMERATION_PARTIAL",
        "ACTOR_ENUMERATION_BLOCKED",
    }
)
F9_SURFACE_ROLES = frozenset(
    {
        "FROZEN_OFFICIAL_LOCATOR",
        "PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE",
        "PRODUCT_DETAIL_SURFACE",
        "BOUNDARY_EVIDENCE_SURFACE",
    }
)
F9_RETRIEVAL_OUTCOMES = frozenset({"RETRIEVED", "FAILED_INACCESSIBLE"})
F9_CANDIDATE_OBJECT_CLASSES = frozenset(
    {
        "PLAUSIBLE_PRODUCT_OFFERING",
        "COMPONENT_OR_ACCESSORY_BOUNDARY",
        "SERVICE_OR_SOFTWARE_BOUNDARY",
        "SYSTEM_OR_CONFIGURATION_BOUNDARY",
        "DISCONTINUED_OR_HISTORICAL_BOUNDARY",
        "OTHER_SCOPE_BOUNDARY",
    }
)

F9_ENUMERATION_BOUNDARY = (
    "F9 exhaustion is bounded only by the frozen 37-actor seed set and this declared per-actor "
    "first-party enumeration procedure. Actor completion does not establish that no other products "
    "exist on the open web, does not allocate canonical PRODUCT identity, and does not establish "
    "global product completeness, unseen-population size, market share, effectiveness, S2 publication "
    "authority, or v4.2 assessment effect."
)


def f9_enumeration_procedure_digest(procedure: Mapping[str, Any]) -> str:
    """Return the deterministic SHA-256 for the procedure, excluding its self-digest field."""

    material = {key: value for key, value in procedure.items() if key != "procedure_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_default_f9_actor_enumeration_procedure() -> dict[str, Any]:
    """Load and validate the frozen F9 per-actor enumeration procedure."""

    procedure = cast(
        dict[str, Any],
        json.loads(
            files(RESOURCE_PACKAGE).joinpath(F9_ACTOR_ENUMERATION_PROCEDURE_RESOURCE).read_text(encoding="utf-8")
        ),
    )
    validate_f9_actor_enumeration_procedure(procedure)
    return procedure


def _f9_frame() -> Mapping[str, Any]:
    register = load_default_frame_register()
    frames = cast(list[Mapping[str, Any]], register["frames"])
    return next(frame for frame in frames if frame["frame_id"] == "F9")


def validate_f9_actor_enumeration_procedure(procedure: Mapping[str, Any]) -> None:
    """Fail closed if the F9 enumeration procedure drifts from frozen inputs or semantics."""

    if procedure.get("procedure_id") != F9_ACTOR_ENUMERATION_PROCEDURE_ID:
        raise ProductDiscoveryError(f"F9 enumeration procedure_id must be {F9_ACTOR_ENUMERATION_PROCEDURE_ID}")
    if procedure.get("procedure_sha256") != f9_enumeration_procedure_digest(procedure):
        raise ProductDiscoveryError("F9 enumeration procedure_sha256 does not match deterministic content")
    if procedure.get("status") != "FROZEN_v1.0":
        raise ProductDiscoveryError("F9 enumeration procedure must be FROZEN_v1.0")
    if procedure.get("frame_id") != "F9" or procedure.get("frame_version") != FRAME_VERSION:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the frozen F9 frame/version")
    if procedure.get("frame_register_version") != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the frozen frame register version")
    if procedure.get("frame_register_blob_sha") != F9_FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the exact frame-register blob")
    if procedure.get("actor_seed_register_id") != F9_ACTOR_SEED_REGISTER_ID:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the frozen actor-seed register")
    if procedure.get("actor_seed_register_blob_sha") != F9_ACTOR_SEED_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the exact actor-seed register blob")
    if procedure.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("F9 enumeration procedure must bind the frozen A2 analysis universe")
    if procedure.get("world_time_cutoff") != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("F9 enumeration procedure world_time_cutoff drift")
    if procedure.get("knowledge_time_cutoff") != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("F9 enumeration procedure knowledge_time_cutoff drift")
    if procedure.get("query_family") != F9_QUERY_FAMILY:
        raise ProductDiscoveryError("F9 enumeration procedure query_family drift")
    if procedure.get("boundary") != F9_ENUMERATION_BOUNDARY:
        raise ProductDiscoveryError("F9 enumeration procedure boundary drift")

    seed_register = load_f9_actor_seed_register()
    expected_actor_ids = [str(actor["organization_id"]) for actor in seed_register["actors"]]
    actual_actor_ids = cast(list[str], procedure.get("actor_identity_ids"))
    if int(procedure.get("actor_count", -1)) != len(expected_actor_ids):
        raise ProductDiscoveryError("F9 enumeration procedure actor_count does not match frozen seed set")
    if actual_actor_ids != expected_actor_ids:
        raise ProductDiscoveryError("F9 enumeration procedure actor identities do not exactly match frozen seed order")

    frame = _f9_frame()
    if set(cast(list[str], procedure.get("allowed_source_classes"))) != set(cast(list[str], frame["source_classes"])):
        raise ProductDiscoveryError("F9 enumeration procedure allowed source classes drift from frozen F9")
    if [procedure.get("query_family")] != cast(list[str], frame["query_families"]):
        raise ProductDiscoveryError("F9 enumeration procedure query family does not exactly match frozen F9")

    if set(cast(list[str], procedure.get("surface_roles"))) != F9_SURFACE_ROLES:
        raise ProductDiscoveryError("F9 enumeration procedure surface-role domain drift")
    if set(cast(list[str], procedure.get("retrieval_outcomes"))) != F9_RETRIEVAL_OUTCOMES:
        raise ProductDiscoveryError("F9 enumeration procedure retrieval-outcome domain drift")
    if set(cast(list[str], procedure.get("candidate_object_classes"))) != F9_CANDIDATE_OBJECT_CLASSES:
        raise ProductDiscoveryError("F9 enumeration procedure candidate-object domain drift")
    if set(cast(list[str], procedure.get("capture_outcomes"))) != CAPTURE_OUTCOMES:
        raise ProductDiscoveryError("F9 enumeration procedure capture-outcome domain drift")
    if set(cast(list[str], procedure.get("actor_completion_states"))) != F9_COMPLETION_STATES:
        raise ProductDiscoveryError("F9 enumeration procedure actor-completion domain drift")
    if procedure.get("procedure_sha256") != F9_ACTOR_ENUMERATION_PROCEDURE_SHA256:
        raise ProductDiscoveryError("F9 enumeration procedure digest does not match the frozen v1.0 digest")


def f9_actor_completion_record_id(record: Mapping[str, Any]) -> str:
    """Return a deterministic ID for one F9 actor-enumeration completion record."""

    material = {key: value for key, value in record.items() if key != "completion_record_id"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "F9AC-" + hashlib.sha256(encoded).hexdigest()


def _seed_actor_by_id() -> dict[str, Mapping[str, Any]]:
    register = load_f9_actor_seed_register()
    return {str(actor["organization_id"]): actor for actor in cast(list[Mapping[str, Any]], register["actors"])}


def validate_f9_actor_completion_record(
    record: Mapping[str, Any],
    procedure: Mapping[str, Any] | None = None,
) -> None:
    """Validate one actor-level F9 enumeration record against the frozen procedure."""

    bound_procedure = procedure or load_default_f9_actor_enumeration_procedure()
    validate_f9_actor_enumeration_procedure(bound_procedure)

    if record.get("completion_record_id") != f9_actor_completion_record_id(record):
        raise ProductDiscoveryError("F9 actor completion_record_id does not match deterministic content")
    if record.get("procedure_id") != bound_procedure["procedure_id"]:
        raise ProductDiscoveryError("F9 actor completion record does not bind the frozen procedure ID")
    if record.get("procedure_sha256") != bound_procedure["procedure_sha256"]:
        raise ProductDiscoveryError("F9 actor completion record does not bind the frozen procedure digest")
    if record.get("query_family") != F9_QUERY_FAMILY:
        raise ProductDiscoveryError("F9 actor completion record query_family drift")
    if record.get("boundary") != F9_ENUMERATION_BOUNDARY:
        raise ProductDiscoveryError("F9 actor completion record boundary drift")

    actor_id = str(record.get("actor_organization_id", "")).strip()
    actors = _seed_actor_by_id()
    if actor_id not in actors:
        raise ProductDiscoveryError(f"F9 actor completion record references unknown frozen actor {actor_id!r}")
    expected_official_locator = str(actors[actor_id]["official_url"])

    completion_state = record.get("completion_state")
    if completion_state not in F9_COMPLETION_STATES:
        raise ProductDiscoveryError("F9 actor completion record has invalid completion_state")
    completion_reason = str(record.get("completion_reason", "")).strip()
    if not completion_reason:
        raise ProductDiscoveryError("F9 actor completion record requires completion_reason")

    surfaces = record.get("inspection_surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ProductDiscoveryError("F9 actor completion record requires non-empty inspection_surfaces")

    official_locator_seen = False
    catalogue_surface_retrieved = False
    for surface in surfaces:
        if not isinstance(surface, Mapping):
            raise ProductDiscoveryError("F9 inspection surfaces must be objects")
        locator = str(surface.get("locator", "")).strip()
        if not locator:
            raise ProductDiscoveryError("F9 inspection surface requires exact locator")
        source_class = surface.get("source_class")
        if source_class not in bound_procedure["allowed_source_classes"]:
            raise ProductDiscoveryError("F9 inspection surface source_class is outside the frozen procedure")
        retrieval_outcome = surface.get("retrieval_outcome")
        if retrieval_outcome not in F9_RETRIEVAL_OUTCOMES:
            raise ProductDiscoveryError("F9 inspection surface retrieval_outcome is invalid")
        roles = surface.get("roles")
        if not isinstance(roles, list) or not roles or not set(roles) <= F9_SURFACE_ROLES:
            raise ProductDiscoveryError("F9 inspection surface roles are invalid")
        if "PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE" in roles and source_class != "MANUFACTURER_VENDOR_OFFICIAL":
            raise ProductDiscoveryError(
                "F9 catalogue/technology inspection requires first-party manufacturer/vendor source"
            )

        if locator == expected_official_locator and "FROZEN_OFFICIAL_LOCATOR" in roles:
            official_locator_seen = official_locator_seen or retrieval_outcome == "RETRIEVED"
        if "PRODUCT_CATALOGUE_OR_TECHNOLOGY_SURFACE" in roles and retrieval_outcome == "RETRIEVED":
            catalogue_surface_retrieved = True

    candidates = record.get("candidate_manifest")
    if not isinstance(candidates, list):
        raise ProductDiscoveryError("F9 actor completion record candidate_manifest must be a list")
    candidate_keys: set[str] = set()
    candidate_capture_ids: set[str] = set()
    all_candidates_captured = True
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ProductDiscoveryError("F9 candidate_manifest entries must be objects")
        candidate_key = str(candidate.get("candidate_key", "")).strip()
        if not candidate_key:
            raise ProductDiscoveryError("F9 candidate_manifest entry requires candidate_key")
        if not candidate_key.startswith(f"{actor_id}::"):
            raise ProductDiscoveryError("F9 candidate_key must remain bound to its frozen actor")
        if candidate_key in candidate_keys:
            raise ProductDiscoveryError(f"Duplicate F9 candidate_key in actor manifest: {candidate_key}")
        candidate_keys.add(candidate_key)
        if candidate.get("object_class") not in F9_CANDIDATE_OBJECT_CLASSES:
            raise ProductDiscoveryError("F9 candidate_manifest object_class is invalid")
        capture_id = str(candidate.get("capture_id") or "").strip()
        capture_outcome = candidate.get("capture_outcome")
        if capture_id and re.fullmatch(r"PDC-[0-9a-f]{64}", capture_id) is None:
            raise ProductDiscoveryError("F9 candidate_manifest capture_id must be an exact PDC identifier")
        if capture_id in candidate_capture_ids:
            raise ProductDiscoveryError(f"Duplicate F9 capture_id in actor manifest: {capture_id}")
        if capture_id:
            candidate_capture_ids.add(capture_id)
        if not capture_id or capture_outcome not in CAPTURE_OUTCOMES:
            all_candidates_captured = False

    no_named_product_evidence = record.get("no_named_product_evidence")
    if not isinstance(no_named_product_evidence, bool):
        raise ProductDiscoveryError("F9 actor completion record requires boolean no_named_product_evidence")
    if no_named_product_evidence == bool(candidates):
        raise ProductDiscoveryError(
            "F9 no_named_product_evidence must be true exactly when the candidate_manifest is empty"
        )

    catalogue_manifest_complete = record.get("catalogue_manifest_complete_under_inspected_surfaces")
    if not isinstance(catalogue_manifest_complete, bool):
        raise ProductDiscoveryError(
            "F9 actor completion record requires boolean catalogue_manifest_complete_under_inspected_surfaces"
        )

    if completion_state == "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL":
        if not official_locator_seen:
            raise ProductDiscoveryError("Complete F9 actor enumeration requires retrieved frozen official locator")
        if not catalogue_surface_retrieved:
            raise ProductDiscoveryError(
                "Complete F9 actor enumeration requires retrieved first-party catalogue surface"
            )
        if not catalogue_manifest_complete:
            raise ProductDiscoveryError(
                "Complete F9 actor enumeration requires complete inspected-surface candidate manifest"
            )
        if not all_candidates_captured:
            raise ProductDiscoveryError(
                "Complete F9 actor enumeration requires a capture disposition for every candidate"
            )


def f9_actor_completion_ledger_digest(ledger: Mapping[str, Any]) -> str:
    """Return the deterministic SHA-256 for an F9 actor completion ledger."""

    material = {key: value for key, value in ledger.items() if key != "ledger_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_f9_actor_completion_ledger(
    ledger: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any] | None = None,
    procedure: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed on digest, predecessor, growth, duplicate-actor, and capture-reuse faults."""

    bound_procedure = procedure or load_default_f9_actor_enumeration_procedure()
    validate_f9_actor_enumeration_procedure(bound_procedure)

    if ledger.get("ledger_sha256") != f9_actor_completion_ledger_digest(ledger):
        raise ProductDiscoveryError("F9 actor completion ledger_sha256 does not match deterministic content")
    if ledger.get("procedure_id") != bound_procedure["procedure_id"]:
        raise ProductDiscoveryError("F9 actor completion ledger does not bind the frozen procedure ID")
    if ledger.get("procedure_sha256") != bound_procedure["procedure_sha256"]:
        raise ProductDiscoveryError("F9 actor completion ledger does not bind the frozen procedure digest")
    if ledger.get("boundary") != F9_ENUMERATION_BOUNDARY:
        raise ProductDiscoveryError("F9 actor completion ledger boundary drift")

    sequence = ledger.get("ledger_sequence")
    if not isinstance(sequence, int) or sequence < 1:
        raise ProductDiscoveryError("F9 actor completion ledger_sequence must be a positive integer")

    predecessor_id = ledger.get("predecessor_ledger_id")
    predecessor_sha = ledger.get("predecessor_ledger_sha256")
    if sequence == 1:
        if predecessor_id is not None or predecessor_sha is not None:
            raise ProductDiscoveryError("F9 ledger sequence 1 must not declare a predecessor link")
        if predecessor is not None:
            raise ProductDiscoveryError("F9 ledger sequence 1 must not be validated against a predecessor object")
    else:
        if not isinstance(predecessor_id, str) or not predecessor_id.strip():
            raise ProductDiscoveryError("F9 ledger after sequence 1 requires predecessor_ledger_id")
        if not isinstance(predecessor_sha, str) or re.fullmatch(r"[0-9a-f]{64}", predecessor_sha) is None:
            raise ProductDiscoveryError("F9 ledger after sequence 1 requires predecessor_ledger_sha256")
        if predecessor is not None:
            # Validate predecessor self-consistency without requiring its own predecessor object here.
            if predecessor.get("ledger_sha256") != f9_actor_completion_ledger_digest(predecessor):
                raise ProductDiscoveryError("F9 ledger predecessor_ledger_sha256 does not match predecessor digest")
            if predecessor.get("ledger_id") != predecessor_id:
                raise ProductDiscoveryError("F9 ledger predecessor_ledger_id does not match predecessor ledger_id")
            if predecessor.get("ledger_sha256") != predecessor_sha:
                raise ProductDiscoveryError("F9 ledger predecessor_ledger_sha256 does not match predecessor digest")
            if int(predecessor.get("ledger_sequence", -1)) != sequence - 1:
                raise ProductDiscoveryError("F9 ledger predecessor sequence must be exactly prior by one")
            pred_records = predecessor.get("completion_records")
            if not isinstance(pred_records, list):
                raise ProductDiscoveryError("F9 predecessor completion_records must be a list")
            for record in pred_records:
                validate_f9_actor_completion_record(cast(Mapping[str, Any], record), bound_procedure)
        else:
            raise ProductDiscoveryError("F9 ledger after sequence 1 requires the predecessor ledger object")

    records = ledger.get("completion_records")
    if not isinstance(records, list):
        raise ProductDiscoveryError("F9 actor completion ledger completion_records must be a list")
    if int(ledger.get("completion_record_count", -1)) != len(records):
        raise ProductDiscoveryError("F9 actor completion ledger completion_record_count drift")

    completed_actor_ids = ledger.get("completed_actor_ids")
    if not isinstance(completed_actor_ids, list):
        raise ProductDiscoveryError("F9 actor completion ledger completed_actor_ids must be a list")

    records_by_actor: dict[str, Mapping[str, Any]] = {}
    ledger_capture_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ProductDiscoveryError("F9 actor completion ledger records must be objects")
        validate_f9_actor_completion_record(record, bound_procedure)
        actor_id = str(record["actor_organization_id"])
        if actor_id in records_by_actor:
            raise ProductDiscoveryError(f"Duplicate F9 actor completion record: {actor_id}")
        records_by_actor[actor_id] = record
        for candidate in cast(list[Mapping[str, Any]], record["candidate_manifest"]):
            capture_id = str(candidate.get("capture_id") or "")
            if not capture_id:
                continue
            if capture_id in ledger_capture_ids:
                raise ProductDiscoveryError(f"F9 capture_id reused across actor completion records: {capture_id}")
            ledger_capture_ids.add(capture_id)

    if len(completed_actor_ids) != len(set(str(actor_id) for actor_id in completed_actor_ids)):
        raise ProductDiscoveryError("F9 completed_actor_ids contains duplicate actor identities")
    if set(str(actor_id) for actor_id in completed_actor_ids) != set(records_by_actor):
        raise ProductDiscoveryError("F9 completed_actor_ids must exactly match completion_records actors")

    expected_remaining = int(bound_procedure["actor_count"]) - len(records_by_actor)
    if int(ledger.get("actor_completion_records_remaining", -1)) != expected_remaining:
        raise ProductDiscoveryError("F9 actor_completion_records_remaining drift")

    exhaustion = f9_bounded_exhaustion_state(cast(list[Mapping[str, Any]], records), bound_procedure)
    if ledger.get("f9_exhaustion_state") != exhaustion:
        raise ProductDiscoveryError("F9 ledger f9_exhaustion_state does not match bounded exhaustion function")

    if sequence > 1 and predecessor is not None:
        prior_actors = cast(list[str], predecessor["completed_actor_ids"])
        if not set(prior_actors) <= set(completed_actor_ids):
            raise ProductDiscoveryError("F9 successor ledger shrunk completed_actor_ids versus predecessor")
        prior_records = {
            str(record["actor_organization_id"]): record
            for record in cast(list[Mapping[str, Any]], predecessor["completion_records"])
        }
        for actor_id, prior_record in prior_records.items():
            if records_by_actor.get(actor_id) != prior_record:
                raise ProductDiscoveryError(f"F9 successor ledger mutated predecessor completion record for {actor_id}")


def f9_bounded_exhaustion_state(
    records: Sequence[Mapping[str, Any]],
    procedure: Mapping[str, Any] | None = None,
) -> str:
    """Return the protocol stop state without converting F9 exhaustion into global completeness."""

    bound_procedure = procedure or load_default_f9_actor_enumeration_procedure()
    validate_f9_actor_enumeration_procedure(bound_procedure)

    records_by_actor: dict[str, Mapping[str, Any]] = {}
    ledger_capture_ids: set[str] = set()
    for record in records:
        validate_f9_actor_completion_record(record, bound_procedure)
        actor_id = str(record["actor_organization_id"])
        if actor_id in records_by_actor:
            raise ProductDiscoveryError(f"Duplicate F9 actor completion record: {actor_id}")
        records_by_actor[actor_id] = record
        for candidate in cast(list[Mapping[str, Any]], record["candidate_manifest"]):
            capture_id = str(candidate.get("capture_id") or "")
            if not capture_id:
                continue
            if capture_id in ledger_capture_ids:
                raise ProductDiscoveryError(f"F9 capture_id reused across actor completion records: {capture_id}")
            ledger_capture_ids.add(capture_id)

    expected_actor_ids = set(cast(list[str], bound_procedure["actor_identity_ids"]))
    if set(records_by_actor) != expected_actor_ids:
        return "CONTINUE"
    if any(record["completion_state"] == "ACTOR_ENUMERATION_BLOCKED" for record in records_by_actor.values()):
        return "UNRESOLVED_SOURCE_BARRIER"
    if any(
        record["completion_state"] != "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL"
        for record in records_by_actor.values()
    ):
        return "CONTINUE"
    return "BOUNDED_FRAME_EXHAUSTED"
