"""Controlled online-first Phase 3 live/replay proof semantics.

This module verifies operational capture/replay determinism for one exact structured
ClinicalTrials.gov study capture. It consumes durable collector/run-ledger records
only and performs no network I/O. Equality of projection digests is a software
reproducibility claim, not a source-truth, clinical, assessment, S2, release, or
publication claim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..util import (
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    safe_join,
    sha256_bytes,
    utc_now,
)
from .acquisition_policy import ONLINE_PREFERRED, ONLINE_REQUIRED, REPLAY_ONLY
from .adapters.clinicaltrials import CTGOV_ADAPTER_ID, ClinicalTrialsGovAdapter
from .prior_capture_replay import (
    LIVE_ROUTE,
    REPLAY_ROUTE,
    PriorCaptureError,
    PriorCaptureReference,
    _reference_from_result,
    verify_prior_capture_reference,
)
from .run_ledger import load_run_summary, load_target_checkpoint, verify_run_manifest

RUNTIME_PROOF_SCHEMA_VERSION = "1"
RUNTIME_PROOF_BOUNDARY = (
    "Phase 3 runtime proofs establish bounded operational capture identity, replay zero-network accounting, "
    "and deterministic projection equivalence for exact stored bytes. They do not establish source truth, "
    "clinical or scientific validity, evidence adjudication, assessment mutation, canonical S2 admission, "
    "G0/G1/G2 passage, release authorization, publication, legal authority, or production readiness."
)
RUNTIME_PROOF_NON_CLAIMS = (
    "SOURCE_TRUTH",
    "CLINICAL_VALIDITY",
    "SCIENTIFIC_VALIDITY",
    "SOURCE_COMPLETENESS",
    "EVIDENCE_ADJUDICATION",
    "ASSESSMENT_MUTATION",
    "CANONICAL_S2_ADMISSION",
    "G0_G1_G2_PASSAGE",
    "RELEASE_AUTHORIZATION",
    "PUBLICATION",
    "LEGAL_AUTHORITY",
    "PRODUCTION_READINESS",
)
_REQUIRED_PROOF_KEYS = frozenset(
    {
        "schema_version",
        "proof_id",
        "created_at",
        "semantic",
        "proof_semantic_sha256",
        "boundary",
        "non_claims",
    }
)
_SUMMARY_SEMANTIC_KEYS = (
    "run_id",
    "plan_id",
    "execution_status",
    "counts",
    "slo",
    "retrieval_targets",
    "outcomes",
    "per_host",
    "acquisition",
)


class RuntimeProofError(ValueError):
    """Raised when Phase 3 proof evidence cannot satisfy the bounded proof contract."""


def _sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeProofError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeProofError(f"{field} must be an object")
    return value


def _load_result_reference(quarantine_root: Path, result_id: str) -> PriorCaptureReference:
    try:
        ensure_identifier(result_id, "result_id")
        result_path = safe_join(quarantine_root, "results", f"{result_id}.json")
    except ValueError as exc:
        raise RuntimeProofError("result_id is invalid") from exc
    if not result_path.is_file():
        raise RuntimeProofError("bound collector result record is missing")
    try:
        value = load_json(result_path)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeProofError("bound collector result record is unreadable") from exc
    if not isinstance(value, dict):
        raise RuntimeProofError("bound collector result record is not an object")
    try:
        reference = _reference_from_result(quarantine_root, value)
        verify_prior_capture_reference(quarantine_root, reference)
    except PriorCaptureError as exc:
        raise RuntimeProofError(f"bound collector capture failed integrity validation: {exc}") from exc
    if reference.result_id != result_id:
        raise RuntimeProofError("collector result identity does not match requested proof result_id")
    return reference


def _capture_bytes(quarantine_root: Path, reference: PriorCaptureReference) -> bytes:
    try:
        path = safe_join(quarantine_root, reference.quarantine_path)
        body = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise RuntimeProofError("bound collector capture bytes are unavailable") from exc
    if len(body) != reference.size_bytes:
        raise RuntimeProofError("bound collector capture byte size changed")
    if sha256_bytes(body) != reference.content_sha256:
        raise RuntimeProofError("bound collector capture SHA-256 changed")
    return body


def project_clinicaltrials_capture(
    quarantine_root: Path,
    *,
    result_id: str,
    expected_source_id: str | None = None,
) -> dict[str, Any]:
    """Project one hash-verified stored CT.gov study capture without network I/O."""
    reference = _load_result_reference(quarantine_root, result_id)
    if expected_source_id is not None and reference.source_id != expected_source_id:
        raise RuntimeProofError("collector capture source_id does not match proof source binding")
    body = _capture_bytes(quarantine_root, reference)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeProofError("ClinicalTrials.gov capture is not valid UTF-8 JSON") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeProofError("ClinicalTrials.gov capture is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeProofError("ClinicalTrials.gov single-study capture must decode to an object")
    adapter = ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter)
    try:
        projection = adapter.normalize_study(payload)
    except (TypeError, ValueError) as exc:
        raise RuntimeProofError(f"ClinicalTrials.gov capture cannot be normalized: {exc}") from exc
    projection_sha256 = sha256_bytes(canonical_json_bytes(projection))
    return {
        "adapter_id": CTGOV_ADAPTER_ID,
        "result_id": reference.result_id,
        "source_id": reference.source_id,
        "monitor_id": reference.monitor_id,
        "requested_url": reference.requested_url,
        "retrieved_at": reference.retrieved_at,
        "content_sha256": reference.content_sha256,
        "size_bytes": reference.size_bytes,
        "projection": projection,
        "projection_sha256": projection_sha256,
    }


def _source_outcome(summary: dict[str, Any], source_id: str) -> dict[str, Any]:
    outcomes = summary.get("outcomes")
    if not isinstance(outcomes, list):
        raise RuntimeProofError("run summary outcomes must be an array")
    matches = [item for item in outcomes if isinstance(item, dict) and item.get("source_id") == source_id]
    if len(matches) != 1:
        raise RuntimeProofError(f"run summary must contain exactly one outcome for source {source_id!r}")
    return matches[0]


def _verify_summary_semantic_digest(summary: dict[str, Any]) -> str:
    semantic = {key: summary.get(key) for key in _SUMMARY_SEMANTIC_KEYS}
    expected = sha256_bytes(canonical_json_bytes(semantic))
    observed = _sha256(summary.get("semantic_summary_sha256"), "semantic_summary_sha256")
    if observed != expected:
        raise RuntimeProofError("run summary semantic digest does not match semantic content")
    return observed


def _load_manifest(quarantine_root: Path, run_id: str) -> dict[str, Any]:
    try:
        path = safe_join(quarantine_root, "run-ledgers", run_id, "manifest.json")
        value = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeProofError(f"run manifest {run_id!r} is unavailable or unreadable") from exc
    if not isinstance(value, dict):
        raise RuntimeProofError("run manifest must be an object")
    try:
        verify_run_manifest(value)
    except ValueError as exc:
        raise RuntimeProofError(f"run manifest validation failed: {exc}") from exc
    return value


def _binding_value(configuration: dict[str, Any], prefixed_key: str, replay_key: str) -> Any:
    value = configuration.get(prefixed_key)
    return configuration.get(replay_key) if value is None else value


def _assert_summary_binding(
    quarantine_root: Path,
    summary: dict[str, Any],
    *,
    run_id: str,
    programme_id: str,
    source_id: str,
    policy_sha256: str,
    expected_route: str,
    reference: PriorCaptureReference,
    zero_network: bool,
) -> dict[str, Any]:
    if summary.get("run_id") != run_id:
        raise RuntimeProofError("run summary identity mismatch")
    if summary.get("status") != "COMPLETED":
        raise RuntimeProofError(f"proof run {run_id} is not operationally completed")
    semantic_digest = _verify_summary_semantic_digest(summary)
    acquisition = _object(summary.get("acquisition"), "run summary acquisition")
    if acquisition.get("programme_id") != programme_id:
        raise RuntimeProofError("run summary programme_id mismatch")
    if acquisition.get("policy_sha256") != policy_sha256:
        raise RuntimeProofError("run summary acquisition-policy digest mismatch")
    if acquisition.get("route") != expected_route:
        raise RuntimeProofError(
            f"run summary acquisition route {acquisition.get('route')!r} does not match {expected_route!r}"
        )

    manifest = _load_manifest(quarantine_root, run_id)
    if summary.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise RuntimeProofError("run summary manifest digest does not match durable manifest")
    if summary.get("binding_sha256") != manifest.get("binding_sha256"):
        raise RuntimeProofError("run summary binding digest does not match durable manifest")
    binding = _object(manifest.get("binding"), "run manifest binding")
    scheduler_configuration = _object(
        binding.get("scheduler_configuration"),
        "run manifest scheduler configuration",
    )
    bound_policy_sha256 = _binding_value(
        scheduler_configuration,
        "acquisition_policy_sha256",
        "policy_sha256",
    )
    bound_programme_id = _binding_value(
        scheduler_configuration,
        "acquisition_programme_id",
        "programme_id",
    )
    execution_mode = _binding_value(
        scheduler_configuration,
        "acquisition_execution_mode",
        "execution_mode",
    )
    if bound_policy_sha256 != policy_sha256:
        raise RuntimeProofError("run manifest acquisition-policy digest mismatch")
    if bound_programme_id != programme_id:
        raise RuntimeProofError("run manifest programme binding mismatch")
    if expected_route == REPLAY_ROUTE:
        if execution_mode != REPLAY_ONLY:
            raise RuntimeProofError("REPLAY proof run is not bound to REPLAY_ONLY")
    elif execution_mode not in {ONLINE_REQUIRED, ONLINE_PREFERRED}:
        raise RuntimeProofError("LIVE proof run is not bound to an online acquisition mode")

    targets = binding.get("retrieval_targets")
    if not isinstance(targets, list) or len(targets) != 1 or not isinstance(targets[0], dict):
        raise RuntimeProofError("Phase 3 reference run manifest must bind exactly one retrieval target")
    target = targets[0]
    if target.get("source_ids") != [source_id]:
        raise RuntimeProofError("Phase 3 reference target does not bind exactly the proof source")
    if target.get("normalized_url") != reference.normalized_url:
        raise RuntimeProofError("run target URL does not match the bound collector capture")
    try:
        checkpoint = load_target_checkpoint(quarantine_root, run_id=run_id, target=target)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeProofError(f"run target checkpoint validation failed: {exc}") from exc
    if checkpoint.get("state") != "RESULT":
        raise RuntimeProofError("Phase 3 proof target checkpoint did not reach RESULT")
    checkpoint_outcome = _object(checkpoint.get("outcome"), "run target checkpoint outcome")
    if checkpoint_outcome.get("record_id") != reference.result_id:
        raise RuntimeProofError("run checkpoint result_id does not match bound collector capture")

    outcome = _source_outcome(summary, source_id)
    if outcome.get("status") != "RESULT":
        raise RuntimeProofError(f"proof source {source_id!r} did not reach RESULT")
    if outcome.get("record_id") != reference.result_id:
        raise RuntimeProofError("run outcome result_id does not match bound proof capture")
    source_route = outcome.get("acquisition_route")
    if source_route is not None and source_route != expected_route:
        raise RuntimeProofError("run outcome route does not match proof route")

    retrieval_targets = summary.get("retrieval_targets")
    if not isinstance(retrieval_targets, list) or len(retrieval_targets) != 1:
        raise RuntimeProofError("run summary must contain exactly one retrieval target")
    retrieval_target = _object(retrieval_targets[0], "run summary retrieval target")
    if retrieval_target.get("retrieval_target_id") != target.get("retrieval_target_id"):
        raise RuntimeProofError("run summary retrieval target identity mismatch")
    if retrieval_target.get("acquisition_route") != expected_route:
        raise RuntimeProofError("run summary retrieval target route mismatch")

    slo = _object(summary.get("slo"), "run summary slo")
    if slo.get("source_accountability_coverage") != 1.0 or slo.get("target_execution_coverage") != 1.0:
        raise RuntimeProofError("bounded proof run does not have full source/target operational accountability")
    counts = _object(summary.get("counts"), "run summary counts")
    if counts.get("total") != 1 or counts.get("retrieval_target_groups") != 1:
        raise RuntimeProofError("Phase 3 reference proof must contain exactly one logical source and target")

    attempts = checkpoint.get("attempts")
    if not isinstance(attempts, list):
        raise RuntimeProofError("run checkpoint attempts must be an array")
    if zero_network:
        if counts.get("collection_attempts") != 0 or counts.get("unique_retrievals") != 0 or counts.get("retries") != 0:
            raise RuntimeProofError("REPLAY proof run contains non-zero network/attempt accounting")
        if summary.get("per_host") != {} or attempts:
            raise RuntimeProofError("REPLAY proof run contains network or per-host accounting")
        replay = _object(checkpoint.get("replay"), "REPLAY checkpoint provenance")
        if replay.get("route") != REPLAY_ROUTE or replay.get("result_id") != reference.result_id:
            raise RuntimeProofError("REPLAY checkpoint does not reuse the exact bound result identity")
        if replay.get("content_sha256") != reference.content_sha256:
            raise RuntimeProofError("REPLAY checkpoint content hash does not match bound capture")
        if replay.get("retrieved_at") != reference.retrieved_at:
            raise RuntimeProofError("REPLAY checkpoint changed the original capture timestamp")
        prior_binding = _object(target.get("prior_capture"), "REPLAY target prior capture")
        try:
            prior_reference = PriorCaptureReference.from_binding(prior_binding)
        except PriorCaptureError as exc:
            raise RuntimeProofError(f"REPLAY target prior-capture binding is invalid: {exc}") from exc
        if canonical_json_bytes(prior_reference.binding()) != canonical_json_bytes(reference.binding()):
            raise RuntimeProofError("REPLAY target prior-capture binding differs from exact collector capture")
    else:
        attempt_count = counts.get("collection_attempts")
        if not isinstance(attempt_count, int) or isinstance(attempt_count, bool) or attempt_count < 1:
            raise RuntimeProofError("LIVE proof run does not record a network collection attempt")
        if not attempts:
            raise RuntimeProofError("LIVE proof target checkpoint has no collection attempt")
        if attempts[-1].get("record_id") != reference.result_id:
            raise RuntimeProofError("LIVE terminal attempt does not bind the collector result")
        if acquisition.get("fallback_used") is True:
            raise RuntimeProofError("LIVE equivalence proof cannot be satisfied by prior-capture fallback")

    return {
        "run_id": run_id,
        "semantic_summary_sha256": semantic_digest,
        "manifest_sha256": manifest["manifest_sha256"],
        "binding_sha256": manifest["binding_sha256"],
        "target_checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "execution_status": summary.get("execution_status"),
        "execution_mode": execution_mode,
        "route": expected_route,
        "collection_attempts": counts.get("collection_attempts"),
        "retries": counts.get("retries"),
        "recovered_attempts": counts.get("recovered_attempts"),
        "resumed_targets": counts.get("resumed_targets"),
        "source_accountability_coverage": slo.get("source_accountability_coverage"),
        "target_execution_coverage": slo.get("target_execution_coverage"),
    }


def build_runtime_proof(
    quarantine_root: Path,
    *,
    live_run_id: str,
    replay_run_id: str,
    programme_id: str,
    source_id: str,
    policy_sha256: str,
    result_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build one deterministic semantic proof over durable live and replay run records."""
    try:
        ensure_identifier(programme_id, "programme_id")
        ensure_identifier(source_id, "source_id")
        ensure_identifier(live_run_id, "live_run_id")
        ensure_identifier(replay_run_id, "replay_run_id")
        ensure_identifier(result_id, "result_id")
    except ValueError as exc:
        raise RuntimeProofError(f"invalid Phase 3 proof identifier: {exc}") from exc
    _sha256(policy_sha256, "policy_sha256")
    if live_run_id == replay_run_id:
        raise RuntimeProofError("LIVE and REPLAY proof runs must have distinct run identities")

    try:
        live_summary = load_run_summary(quarantine_root, live_run_id)
        replay_summary = load_run_summary(quarantine_root, replay_run_id)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeProofError(f"run-ledger validation failed: {exc}") from exc
    if live_summary is None or replay_summary is None:
        raise RuntimeProofError("both LIVE and REPLAY durable run summaries are required")

    reference = _load_result_reference(quarantine_root, result_id)
    if reference.source_id != source_id:
        raise RuntimeProofError("bound result source_id does not match Phase 3 proof source")

    live_accounting = _assert_summary_binding(
        quarantine_root,
        live_summary,
        run_id=live_run_id,
        programme_id=programme_id,
        source_id=source_id,
        policy_sha256=policy_sha256,
        expected_route=LIVE_ROUTE,
        reference=reference,
        zero_network=False,
    )
    replay_accounting = _assert_summary_binding(
        quarantine_root,
        replay_summary,
        run_id=replay_run_id,
        programme_id=programme_id,
        source_id=source_id,
        policy_sha256=policy_sha256,
        expected_route=REPLAY_ROUTE,
        reference=reference,
        zero_network=True,
    )

    live_projection = project_clinicaltrials_capture(
        quarantine_root,
        result_id=result_id,
        expected_source_id=source_id,
    )
    replay_projection = project_clinicaltrials_capture(
        quarantine_root,
        result_id=result_id,
        expected_source_id=source_id,
    )
    if live_projection["projection_sha256"] != replay_projection["projection_sha256"]:
        raise RuntimeProofError("LIVE-capture and REPLAY deterministic projection digests differ")

    semantic = {
        "programme_id": programme_id,
        "source_id": source_id,
        "policy_sha256": policy_sha256,
        "capture": {
            "result_id": reference.result_id,
            "monitor_id": reference.monitor_id,
            "requested_url": reference.requested_url,
            "retrieved_at": reference.retrieved_at,
            "content_sha256": reference.content_sha256,
            "size_bytes": reference.size_bytes,
        },
        "projection": {
            "adapter_id": CTGOV_ADAPTER_ID,
            "projection_sha256": live_projection["projection_sha256"],
            "normalized_projection": live_projection["projection"],
            "live_replay_equivalent": True,
        },
        "live": live_accounting,
        "replay": replay_accounting,
        "claims": {
            "capture_before_projection_verified": True,
            "exact_result_identity_reused": True,
            "replay_zero_network_verified": True,
            "deterministic_projection_equivalence_verified": True,
            "full_bounded_accountability_verified": True,
            "canonical_s2_mutation_performed": False,
        },
        "boundary": RUNTIME_PROOF_BOUNDARY,
    }
    proof_semantic_sha256 = sha256_bytes(canonical_json_bytes(semantic))
    return {
        "schema_version": RUNTIME_PROOF_SCHEMA_VERSION,
        "proof_id": f"P3PROOF-{proof_semantic_sha256[:24]}",
        "created_at": created_at or utc_now(),
        "semantic": semantic,
        "proof_semantic_sha256": proof_semantic_sha256,
        "boundary": RUNTIME_PROOF_BOUNDARY,
        "non_claims": list(RUNTIME_PROOF_NON_CLAIMS),
    }


def verify_runtime_proof(quarantine_root: Path, proof: dict[str, Any]) -> dict[str, Any]:
    """Rebuild and verify one Phase 3 proof against current durable controlled records."""
    if not isinstance(proof, dict):
        raise RuntimeProofError("runtime proof must be an object")
    unknown = set(proof) - _REQUIRED_PROOF_KEYS
    missing = _REQUIRED_PROOF_KEYS - set(proof)
    if unknown or missing:
        raise RuntimeProofError(f"runtime proof fields mismatch; missing={sorted(missing)} unknown={sorted(unknown)}")
    if proof.get("schema_version") != RUNTIME_PROOF_SCHEMA_VERSION:
        raise RuntimeProofError("runtime proof schema version mismatch")
    if proof.get("boundary") != RUNTIME_PROOF_BOUNDARY:
        raise RuntimeProofError("runtime proof authority boundary mismatch")
    if proof.get("non_claims") != list(RUNTIME_PROOF_NON_CLAIMS):
        raise RuntimeProofError("runtime proof non-claims mismatch")
    semantic = _object(proof.get("semantic"), "runtime proof semantic")
    if semantic.get("boundary") != RUNTIME_PROOF_BOUNDARY:
        raise RuntimeProofError("runtime proof semantic authority boundary mismatch")
    digest = sha256_bytes(canonical_json_bytes(semantic))
    if proof.get("proof_semantic_sha256") != digest:
        raise RuntimeProofError("runtime proof semantic digest mismatch")
    if proof.get("proof_id") != f"P3PROOF-{digest[:24]}":
        raise RuntimeProofError("runtime proof_id does not match semantic digest")
    capture = _object(semantic.get("capture"), "runtime proof capture")
    live = _object(semantic.get("live"), "runtime proof live")
    replay = _object(semantic.get("replay"), "runtime proof replay")
    expected = build_runtime_proof(
        quarantine_root,
        live_run_id=str(live.get("run_id")),
        replay_run_id=str(replay.get("run_id")),
        programme_id=str(semantic.get("programme_id")),
        source_id=str(semantic.get("source_id")),
        policy_sha256=str(semantic.get("policy_sha256")),
        result_id=str(capture.get("result_id")),
        created_at=str(proof.get("created_at")),
    )
    if canonical_json_bytes(expected["semantic"]) != canonical_json_bytes(semantic):
        raise RuntimeProofError("runtime proof semantic content does not match durable records")
    if expected["proof_semantic_sha256"] != proof["proof_semantic_sha256"]:
        raise RuntimeProofError("runtime proof recomputation digest mismatch")
    return dict(proof)


def write_runtime_proof(path: Path, proof: dict[str, Any]) -> None:
    """Write a proof bundle to one explicit operator-controlled non-canonical path."""
    if not path.name or path.name in {".", ".."}:
        raise RuntimeProofError("runtime proof output path must name a file")
    atomic_write_json(path, proof)
