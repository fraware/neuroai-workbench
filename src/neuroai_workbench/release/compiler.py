from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .. import __version__
from ..assistance import scan_sensitive_text
from ..governance_opinions import REVIEW_TRACKS
from ..observatory_graph import OBJECT_CLASSES, persistable, validate_graph_object
from ..util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

CANDIDATE_BOUNDARY = (
    "A candidate release is a mechanically verified layout bound to a manifest digest. "
    "Mechanical PASS does not set release_authorized, infer six-domain PASS, publish, or tag."
)
RECORD_FILES = {
    "Entity": "entities.jsonl",
    "Source": "sources.jsonl",
    "Observation": "observations.jsonl",
    "Assertion": "assertions.jsonl",
    "Event": "events.jsonl",
    "Relationship": "relationships.jsonl",
    "Candidate": "candidates.jsonl",
    "ReopeningDecision": "reopening-decisions.jsonl",
}
ID_FIELDS = {
    "Entity": "entity_id",
    "Source": "source_id",
    "Observation": "observation_id",
    "Assertion": "assertion_id",
    "Event": "event_id",
    "Relationship": "relationship_id",
    "Candidate": "candidate_id",
    "ReopeningDecision": "reopening_decision_id",
}


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    text = "\n".join(lines)
    return (text + ("\n" if records else "")).encode("utf-8")


def _index(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in objects:
        object_class = str(record.get("object_class"))
        field = ID_FIELDS.get(object_class)
        if not field:
            continue
        object_id = str(record.get(field, ""))
        if object_id:
            index[object_id] = record
    return index


def _dangling_refs(objects: list[dict[str, Any]]) -> list[str]:
    index = _index(objects)
    dangling: list[str] = []
    for record in objects:
        object_class = str(record.get("object_class"))
        object_id = str(record.get(ID_FIELDS.get(object_class, ""), ""))
        for field in (
            "source_ids",
            "observation_ids",
            "supersedes_assertion_ids",
            "trigger_assertion_ids",
            "trigger_event_ids",
        ):
            for ref in record.get(field) or []:
                if str(ref) not in index:
                    dangling.append(f"{object_id}.{field}->{ref}")
        if object_class == "Observation" and record.get("source_id") and str(record["source_id"]) not in index:
            dangling.append(f"{object_id}.source_id->{record['source_id']}")
        subject = record.get("subject")
        if isinstance(subject, dict) and subject.get("kind") == "RESOLVED_ENTITY_REFERENCE":
            entity_id = str(subject.get("entity_id") or "")
            if entity_id and entity_id not in index:
                dangling.append(f"{object_id}.subject->{entity_id}")
        object_ref = record.get("object_ref")
        if isinstance(object_ref, dict) and object_ref.get("kind") == "RESOLVED_ENTITY_REFERENCE":
            entity_id = str(object_ref.get("entity_id") or "")
            if entity_id and entity_id not in index:
                dangling.append(f"{object_id}.object_ref->{entity_id}")
    return dangling


def _duplicate_ids(objects: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    duplicates: list[str] = []
    for record in objects:
        object_class = str(record.get("object_class"))
        field = ID_FIELDS.get(object_class)
        if not field:
            continue
        object_id = str(record.get(field, ""))
        if object_id in seen:
            duplicates.append(object_id)
        seen.append(object_id)
    return sorted(set(duplicates))


def _protected_hits(text: str) -> list[dict[str, str]]:
    return scan_sensitive_text(text)


class ReleaseCompiler:
    """Build a candidate observatory-graph release layout. Never authorizes publication."""

    def build(
        self,
        objects: list[dict[str, Any]],
        output_dir: Path,
        *,
        candidate_id: str,
        producer_commit: str | None = None,
        runtime_execution_pin: str | None = None,
        declared_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return compile_candidate_release(
            objects,
            output_dir,
            candidate_id=candidate_id,
            producer_commit=producer_commit,
            runtime_execution_pin=runtime_execution_pin,
            declared_counts=declared_counts,
        )


def compile_candidate_release(
    objects: list[dict[str, Any]],
    output_dir: Path,
    *,
    candidate_id: str,
    producer_commit: str | None = None,
    runtime_execution_pin: str | None = None,
    declared_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    persisted: list[dict[str, Any]] = []
    schema_errors: list[str] = []
    for raw in objects:
        object_class = str(raw.get("object_class"))
        if object_class not in OBJECT_CLASSES:
            schema_errors.append(f"Unknown object_class {object_class!r}")
            continue
        errors = validate_graph_object(
            {key: value for key, value in raw.items() if key != "canonical_sha256"}, object_class
        )
        if errors:
            schema_errors.extend(f"{object_class}: {item}" for item in errors)
            continue
        persisted.append(persistable(raw))

    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in RECORD_FILES}
    for record in persisted:
        grouped[str(record["object_class"])].append(record)

    observed_counts = {name: len(items) for name, items in grouped.items()}
    count_mismatches: list[str] = []
    if declared_counts:
        for name, declared in declared_counts.items():
            if observed_counts.get(name, 0) != declared:
                count_mismatches.append(f"{name}: declared {declared} observed {observed_counts.get(name, 0)}")

    dangling = _dangling_refs(persisted)
    duplicates = _duplicate_ids(persisted)

    output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = output_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    attestation_dir = output_dir / "attestation"
    attestation_dir.mkdir(parents=True, exist_ok=True)

    file_digests: dict[str, str] = {}
    protected: list[dict[str, Any]] = []
    for object_class, filename in RECORD_FILES.items():
        payload = _jsonl_bytes(grouped[object_class])
        relative = f"records/{filename}"
        atomic_write_bytes(output_dir / relative, payload)
        file_digests[relative] = sha256_bytes(payload)
        hits = _protected_hits(payload.decode("utf-8"))
        if hits:
            protected.append({"path": relative, "hits": hits})

    blockers: list[dict[str, Any]] = []
    if schema_errors:
        blockers.append({"code": "SCHEMA_INVALID", "detail": schema_errors})
    if dangling:
        blockers.append({"code": "DANGLING_REF", "detail": dangling})
    if duplicates:
        blockers.append({"code": "DUPLICATE_ID", "detail": duplicates})
    if protected:
        blockers.append({"code": "PROTECTED_BYTE_SCAN", "detail": protected})
    if count_mismatches:
        blockers.append({"code": "SEMANTIC_COUNT_MISMATCH", "detail": count_mismatches})

    mechanical_pass = not blockers
    descriptor = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "state": "CANDIDATE",
        "release_authorized": False,
        "package_version": __version__,
        "runtime_execution_pin": runtime_execution_pin,
        "producer_commit": producer_commit,
        "s2_workbench_version_compatibility": "see templates/neuroai-observatory-data/WORKBENCH_VERSION",
        "observatory_graph_schema_version": "1",
        "mechanical_verification": "PASS" if mechanical_pass else "FAIL",
        "boundary": CANDIDATE_BOUNDARY,
    }
    manifest = {
        "candidate_id": candidate_id,
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "object_counts": observed_counts,
        "release_authorized": False,
        "boundary": CANDIDATE_BOUNDARY,
    }
    manifest_digest = sha256_bytes(canonical_json_bytes(manifest))
    manifest["manifest_sha256"] = manifest_digest

    sums = "".join(f"{digest}  {path}\n" for path, digest in sorted(file_digests.items()))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    atomic_write_bytes(output_dir / "SHA256SUMS", sums.encode("utf-8"))

    verification = {
        "candidate_id": candidate_id,
        "manifest_sha256": manifest_digest,
        "mechanical_verification": "PASS" if mechanical_pass else "FAIL",
        "blockers": blockers,
        "release_authorized": False,
        "software_inferred_attestation_pass": False,
        "boundary": CANDIDATE_BOUNDARY,
    }
    atomic_write_json(output_dir / "verification_report.json", verification)

    pending_attestation = {
        "schema_version": "1",
        "profile": "DEFAULT_RELEASE_ATTESTATION",
        "candidate_id": candidate_id,
        "manifest_sha256": manifest_digest,
        "track_assessments": [
            {"track": track, "state": "PENDING", "rationale": "Human domain attestation not recorded by the compiler."}
            for track in sorted(REVIEW_TRACKS)
        ],
        "decision": "NOT_RECORDED",
        "release_authorized": False,
        "software_inferred_pass": False,
        "reuse": "neuroai_workbench.release_attestation.record_release_attestation remains the human recording path.",
        "boundary": CANDIDATE_BOUNDARY,
    }
    atomic_write_json(attestation_dir / "pending_attestation.json", pending_attestation)

    tamper_check = sha256_bytes(
        canonical_json_bytes({key: value for key, value in manifest.items() if key != "manifest_sha256"})
    )
    if tamper_check != manifest_digest:
        raise RuntimeError("Candidate manifest digest is internally inconsistent")

    return {
        "output_dir": str(output_dir),
        "descriptor": descriptor,
        "manifest": manifest,
        "verification": verification,
        "pending_attestation": pending_attestation,
        "counts": Counter(observed_counts),
    }
