from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.product_discovery_frames import (
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
    identity_set_digest,
    validate_discovery_run,
)
from neuroai_workbench.release_a_preregistration import (
    ReleaseAPreregistrationError,
    validate_estimation_universe,
)
from neuroai_workbench.release_a_seed_registry import load_default_seed_artifacts

RESOURCE_PACKAGE = "neuroai_workbench.resources.analysis"
EXECUTION_MANIFEST_SCHEMA = "RELEASE_A_A2_EXECUTION_MANIFEST.schema.json"
EXECUTION_MANIFEST_RESOURCE = "RELEASE_A_A2_EXECUTION_MANIFEST.v1.0.json"

EXECUTION_MANIFEST_VERSION = "RELEASE_A_A2_EXECUTION_MANIFEST_v1.0"
DEFAULT_EXECUTION_MANIFEST_ID = "A2X-4e5d3e5801e480b94c078d02619e82df83b6026a2ed06a0e77ea830a1f68fb82"
DEFAULT_ESTIMATION_UNIVERSE_ID = "RAEU-f98a7ee6f5be7a7ea68d7b20ff5723fc03e23e2f7aafc5186bc2c24e9ae99fb8"
A2_WORKBENCH_BASELINE_SHA = "11c516209fc77dea497fc3bb61012e2f3daecdf7"
A2_KNOWLEDGE_TIME_CUTOFF = "2026-10-08T21:00:00Z"
A2_LANGUAGE_SCOPE_ID = "RELEASE_A_CORE_MULTILINGUAL_v1.0"
A2_NATIVE_LANGUAGE_STRATA = frozenset(
    {
        ("de", "Germany"),
        ("es", "Spain"),
        ("fr", "France"),
        ("ja", "Japan"),
        ("zh-Hans", "China"),
    }
)
A2_EXECUTION_BOUNDARY = (
    "A2 execution binds discovery runs to the frozen A1 seed basis and one exact preregistered estimation "
    "universe. It does not establish global completeness, unseen-population size, market share, effectiveness, "
    "publication authority, or v4.2 assessment effect."
)


class ReleaseAExecutionManifestError(ValueError):
    """Raised when the frozen A2 execution manifest or a bound run drifts."""


def _schema() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(EXECUTION_MANIFEST_SCHEMA).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any) -> list[str]:
    validator = Draft202012Validator(_schema())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _parse_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseAExecutionManifestError(f"{field} requires a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseAExecutionManifestError(f"{field} must be a valid offset-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseAExecutionManifestError(f"{field} must include an explicit timezone")
    return parsed


def execution_manifest_id(manifest: Mapping[str, Any]) -> str:
    """Return the deterministic identity of one frozen A2 execution manifest."""

    material = dict(manifest)
    material.pop("execution_manifest_id", None)
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "A2X-" + hashlib.sha256(encoded).hexdigest()


def load_default_a2_execution_manifest() -> dict[str, Any]:
    """Load and validate the frozen Release-A A2 execution manifest."""

    manifest = cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(EXECUTION_MANIFEST_RESOURCE).read_text(encoding="utf-8")),
    )
    validate_a2_execution_manifest(manifest)
    return manifest


def validate_a2_execution_manifest(manifest: Mapping[str, Any]) -> None:
    """Cross-check the A2 execution freeze against P0.5 and the actual A1 seed artifacts."""

    errors = _schema_errors(manifest)
    if errors:
        raise ReleaseAExecutionManifestError("A2 execution-manifest schema validation failed: " + "; ".join(errors))
    if manifest["manifest_version"] != EXECUTION_MANIFEST_VERSION:
        raise ReleaseAExecutionManifestError(f"manifest_version must be {EXECUTION_MANIFEST_VERSION}")
    if manifest["execution_manifest_id"] != execution_manifest_id(manifest):
        raise ReleaseAExecutionManifestError("execution_manifest_id does not match deterministic manifest material")
    if manifest["status"] != "FROZEN_v1.0":
        raise ReleaseAExecutionManifestError("A2 execution manifest must be FROZEN_v1.0")
    if manifest["workbench_baseline_sha"] != A2_WORKBENCH_BASELINE_SHA:
        raise ReleaseAExecutionManifestError("A2 workbench baseline does not match the frozen execution baseline")
    if manifest["boundary"] != A2_EXECUTION_BOUNDARY:
        raise ReleaseAExecutionManifestError("A2 execution boundary does not match the frozen v1.0 boundary")

    estimation_universe = cast(Mapping[str, Any], manifest["estimation_universe"])
    try:
        validate_estimation_universe(estimation_universe)
    except ReleaseAPreregistrationError as exc:
        raise ReleaseAExecutionManifestError(str(exc)) from exc
    if estimation_universe["universe_id"] != DEFAULT_ESTIMATION_UNIVERSE_ID:
        raise ReleaseAExecutionManifestError("A2 v1.0 must bind the frozen A-P1 estimation universe")
    if estimation_universe["population_view_id"] != "A-P1" or estimation_universe["role"] != "PRIMARY":
        raise ReleaseAExecutionManifestError("A2 v1.0 must execute the primary A-P1 population view")
    if estimation_universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ReleaseAExecutionManifestError("A2 knowledge-time cutoff does not match the frozen collection window")
    if estimation_universe["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ReleaseAExecutionManifestError("A2 estimation universe does not bind the frozen multilingual scope")

    seed = load_default_seed_artifacts()
    seed_manifest = cast(Mapping[str, Any], seed["manifest"])
    seed_registry = cast(Mapping[str, Any], seed["registry"])
    if manifest["a1_seed_manifest_id"] != seed_manifest["manifest_id"]:
        raise ReleaseAExecutionManifestError("A2 manifest does not bind the exact default A1 seed manifest")
    if manifest["a1_seed_registry_sha256"] != seed["registry_sha256"]:
        raise ReleaseAExecutionManifestError("A2 manifest does not bind the exact default A1 seed registry digest")
    if manifest["a1_evidence_index_sha256"] != seed["evidence_index_sha256"]:
        raise ReleaseAExecutionManifestError("A2 manifest does not bind the exact default A1 evidence index")
    if estimation_universe["world_time_cutoff"] != seed_manifest["world_time_cutoff"]:
        raise ReleaseAExecutionManifestError("A2 world-time cutoff must match the frozen A1 snapshot date")
    if estimation_universe["analysis_jurisdiction_scope"] != seed_manifest["jurisdiction_scope"]:
        raise ReleaseAExecutionManifestError("A2 jurisdiction scope must match the frozen A1 protocol scope")

    rows = cast(Sequence[Mapping[str, Any]], seed_registry["rows"])
    expected_known_ids = sorted(str(row["canonical_entity_id"]) for row in rows)
    declared_known_ids = cast(list[str], manifest["initial_known_offering_ids"])
    if declared_known_ids != sorted(declared_known_ids) or declared_known_ids != expected_known_ids:
        raise ReleaseAExecutionManifestError("A2 initial known offering IDs must exactly match the sorted A1 seed registry")
    if int(manifest["initial_known_offering_count"]) != len(expected_known_ids):
        raise ReleaseAExecutionManifestError("A2 initial known offering count does not match the A1 seed registry")
    if manifest["initial_known_identity_set_sha256"] != identity_set_digest(expected_known_ids):
        raise ReleaseAExecutionManifestError("A2 initial known-identity digest does not match the A1 offering set")

    diagnostic_frames = set(cast(list[str], manifest["diagnostic_only_frame_ids"]))
    if diagnostic_frames != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ReleaseAExecutionManifestError("A2 diagnostic-only frame set must remain F7/F9/F11")

    language_design = cast(Mapping[str, Any], manifest["language_design"])
    if language_design["language_scope_id"] != estimation_universe["language_scope_id"]:
        raise ReleaseAExecutionManifestError("A2 language design and estimation universe must use one scope ID")
    if language_design["baseline_language"] != "en":
        raise ReleaseAExecutionManifestError("A2 multilingual design must retain English as the baseline")
    strata = cast(Sequence[Mapping[str, Any]], language_design["native_language_strata"])
    stratum_keys = {(str(item["language"]), str(item["jurisdiction"])) for item in strata}
    if len(strata) != len(stratum_keys) or stratum_keys != A2_NATIVE_LANGUAGE_STRATA:
        raise ReleaseAExecutionManifestError("A2 native-language strata do not match the frozen v1.0 design")

    collection_window = cast(Mapping[str, Any], manifest["collection_window"])
    opened_at = _parse_timestamp(collection_window["opened_at"], field="A2 collection opened_at")
    closes_at = _parse_timestamp(collection_window["closes_at"], field="A2 collection closes_at")
    seed_cutoff = _parse_timestamp(seed_manifest["knowledge_time_cutoff"], field="A1 knowledge_time_cutoff")
    knowledge_cutoff = _parse_timestamp(estimation_universe["knowledge_time_cutoff"], field="A2 knowledge_time_cutoff")
    if opened_at != seed_cutoff:
        raise ReleaseAExecutionManifestError("A2 collection window must open at the A1 knowledge-time cutoff")
    if closes_at != knowledge_cutoff or closes_at <= opened_at:
        raise ReleaseAExecutionManifestError("A2 collection close must equal the later frozen knowledge-time cutoff")

    if manifest["execution_manifest_id"] != DEFAULT_EXECUTION_MANIFEST_ID:
        raise ReleaseAExecutionManifestError("A2 v1.0 execution manifest does not match the frozen default identity")


def validate_run_against_a2_execution_manifest(
    run: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    """Require one discovery run to bind the frozen A2 execution and P0.5 universe identities."""

    validate_a2_execution_manifest(manifest)
    try:
        validate_discovery_run(run)
    except ProductDiscoveryError as exc:
        raise ReleaseAExecutionManifestError(str(exc)) from exc

    universe = cast(Mapping[str, Any], manifest["estimation_universe"])
    if run["execution_manifest_id"] != manifest["execution_manifest_id"]:
        raise ReleaseAExecutionManifestError("Discovery run execution_manifest_id does not match A2 execution")
    if run["estimation_universe_id"] != universe["universe_id"]:
        raise ReleaseAExecutionManifestError("Discovery run estimation_universe_id does not match A2 estimand")
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
            raise ReleaseAExecutionManifestError(f"Discovery run {field} does not match A2 estimation universe")
