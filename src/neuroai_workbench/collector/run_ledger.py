from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_json, canonical_json_bytes, load_json, safe_join, sha256_bytes, utc_now

RUN_LEDGER_SCHEMA_VERSION = "1"
RUN_LEDGER_BOUNDARY = (
    "Collector run ledgers record operational execution and recovery state over exact monitoring-plan, registry, "
    "configuration, and retrieval-target bindings. They do not modify canonical evidence, establish source truth, "
    "convert retrieval failure into assessment failure, or authorize governance or release decisions."
)
TERMINAL_TARGET_STATES = frozenset({"RESULT", "FAILURE", "POLICY_BLOCK"})
TARGET_STATES = frozenset({"PENDING", "ATTEMPTING", "RETRY_WAIT", "INTERNAL_ERROR", *TERMINAL_TARGET_STATES})


def _hash_record(record: dict[str, Any], hash_field: str) -> str:
    controlled = {key: value for key, value in record.items() if key != hash_field}
    return sha256_bytes(canonical_json_bytes(controlled))


def _assert_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a 64-character lowercase hexadecimal SHA-256 digest")
    return value


def _run_root(quarantine_root: Path, run_id: str) -> Path:
    return safe_join(quarantine_root, "run-ledgers", run_id)


def _manifest_path(quarantine_root: Path, run_id: str) -> Path:
    return safe_join(_run_root(quarantine_root, run_id), "manifest.json")


def _summary_path(quarantine_root: Path, run_id: str) -> Path:
    return safe_join(_run_root(quarantine_root, run_id), "summary.json")


def _target_path(quarantine_root: Path, run_id: str, target_id: str) -> Path:
    return safe_join(_run_root(quarantine_root, run_id), "targets", f"{target_id}.json")


def build_run_binding(
    *,
    plan: dict[str, Any],
    registry_sha256: str,
    collector_configuration: dict[str, Any],
    scheduler_configuration: dict[str, Any],
    targets: list[dict[str, Any]],
    pre_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build deterministic operational inputs for one due-cycle execution."""
    _assert_sha256(registry_sha256, "registry_sha256")
    normalized_targets = sorted(
        [dict(target) for target in targets],
        key=lambda item: str(item["retrieval_target_id"]),
    )
    normalized_outcomes = sorted(
        [dict(item) for item in pre_outcomes],
        key=lambda item: (str(item.get("source_id", "")), str(item.get("status", ""))),
    )
    return {
        "plan_id": plan.get("plan_id"),
        "plan_sha256": sha256_bytes(canonical_json_bytes(plan)),
        "registry_sha256": registry_sha256,
        "collector_configuration": collector_configuration,
        "collector_configuration_sha256": sha256_bytes(canonical_json_bytes(collector_configuration)),
        "scheduler_configuration": scheduler_configuration,
        "scheduler_configuration_sha256": sha256_bytes(canonical_json_bytes(scheduler_configuration)),
        "retrieval_targets": normalized_targets,
        "pre_outcomes": normalized_outcomes,
    }


def deterministic_run_id(binding: dict[str, Any]) -> tuple[str, str]:
    binding_sha256 = sha256_bytes(canonical_json_bytes(binding))
    return f"CRUN-{binding_sha256[:32]}", binding_sha256


def deterministic_request_id(run_id: str, retrieval_target_id: str, attempt_count: int) -> str:
    if attempt_count < 1:
        raise ValueError("attempt_count must be >= 1")
    digest = sha256_bytes(
        canonical_json_bytes(
            {
                "run_id": run_id,
                "retrieval_target_id": retrieval_target_id,
                "attempt_count": attempt_count,
            }
        )
    )
    return f"CREQ-{digest[:32]}"


def ensure_run_manifest(
    quarantine_root: Path,
    *,
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Create or verify the immutable manifest for a deterministic run."""
    run_id, binding_sha256 = deterministic_run_id(binding)
    path = _manifest_path(quarantine_root, run_id)
    if path.exists():
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError("Collector run manifest must be a JSON object")
        manifest = value
        verify_run_manifest(value, expected_binding=binding)
        return value

    manifest: dict[str, Any] = {
        "schema_version": RUN_LEDGER_SCHEMA_VERSION,
        "run_id": run_id,
        "binding_sha256": binding_sha256,
        "binding": binding,
        "created_at": utc_now(),
        "boundary": RUN_LEDGER_BOUNDARY,
    }
    manifest["manifest_sha256"] = _hash_record(manifest, "manifest_sha256")
    atomic_write_json(path, manifest)
    return manifest


def verify_run_manifest(manifest: dict[str, Any], *, expected_binding: dict[str, Any] | None = None) -> None:
    if manifest.get("schema_version") != RUN_LEDGER_SCHEMA_VERSION:
        raise ValueError("Collector run manifest has unsupported schema version")
    if manifest.get("boundary") != RUN_LEDGER_BOUNDARY:
        raise ValueError("Collector run manifest authority boundary mismatch")
    binding = manifest.get("binding")
    if not isinstance(binding, dict):
        raise ValueError("Collector run manifest is missing binding")
    run_id, binding_sha256 = deterministic_run_id(binding)
    if manifest.get("run_id") != run_id:
        raise ValueError("Collector run manifest run_id does not match binding")
    if manifest.get("binding_sha256") != binding_sha256:
        raise ValueError("Collector run manifest binding hash mismatch")
    if manifest.get("manifest_sha256") != _hash_record(manifest, "manifest_sha256"):
        raise ValueError("Collector run manifest hash mismatch")
    if expected_binding is not None and canonical_json_bytes(binding) != canonical_json_bytes(expected_binding):
        raise ValueError("Collector run manifest does not match requested execution binding")


def new_target_checkpoint(
    *,
    run_id: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RUN_LEDGER_SCHEMA_VERSION,
        "run_id": run_id,
        "retrieval_target_id": target["retrieval_target_id"],
        "target": dict(target),
        "state": "PENDING",
        "attempts": [],
        "outcome": None,
        "updated_at": utc_now(),
        "boundary": RUN_LEDGER_BOUNDARY,
    }


def load_target_checkpoint(
    quarantine_root: Path,
    *,
    run_id: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    path = _target_path(quarantine_root, run_id, str(target["retrieval_target_id"]))
    if not path.exists():
        return new_target_checkpoint(run_id=run_id, target=target)
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Collector target checkpoint {target['retrieval_target_id']} must be a JSON object")
    verify_target_checkpoint(value, run_id=run_id, expected_target=target)
    return value


def verify_target_checkpoint(
    checkpoint: dict[str, Any],
    *,
    run_id: str,
    expected_target: dict[str, Any],
) -> None:
    target_id = str(expected_target["retrieval_target_id"])
    if checkpoint.get("schema_version") != RUN_LEDGER_SCHEMA_VERSION:
        raise ValueError(f"Collector target checkpoint {target_id} has unsupported schema version")
    if checkpoint.get("run_id") != run_id:
        raise ValueError(f"Collector target checkpoint {target_id} run binding mismatch")
    if checkpoint.get("retrieval_target_id") != target_id:
        raise ValueError(f"Collector target checkpoint {target_id} identity mismatch")
    if checkpoint.get("boundary") != RUN_LEDGER_BOUNDARY:
        raise ValueError(f"Collector target checkpoint {target_id} authority boundary mismatch")
    if canonical_json_bytes(checkpoint.get("target")) != canonical_json_bytes(expected_target):
        raise ValueError(f"Collector target checkpoint {target_id} target binding mismatch")
    if checkpoint.get("checkpoint_sha256") != _hash_record(checkpoint, "checkpoint_sha256"):
        raise ValueError(f"Collector target checkpoint {target_id} hash mismatch")
    state = checkpoint.get("state")
    if state not in TARGET_STATES:
        raise ValueError(f"Collector target checkpoint {target_id} has invalid state {state!r}")
    attempts = checkpoint.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError(f"Collector target checkpoint {target_id} attempts must be a list")


def write_target_checkpoint(quarantine_root: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    record = {key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"}
    record["updated_at"] = utc_now()
    record["checkpoint_sha256"] = _hash_record(record, "checkpoint_sha256")
    path = _target_path(
        quarantine_root,
        str(record["run_id"]),
        str(record["retrieval_target_id"]),
    )
    atomic_write_json(path, record)
    return record


def scan_persisted_attempt_records(quarantine_root: Path) -> dict[str, dict[str, Any]]:
    """Index already-durable collector results/failures by deterministic request ID."""
    records: dict[str, dict[str, Any]] = {}
    for directory in ("results", "failures"):
        root = safe_join(quarantine_root, directory)
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            value = load_json(path)
            if not isinstance(value, dict):
                continue
            request_id = value.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                continue
            if request_id in records:
                raise ValueError(f"Multiple durable collector records found for request_id {request_id}")
            records[request_id] = value
    return records


def write_run_summary(quarantine_root: Path, summary: dict[str, Any]) -> dict[str, Any]:
    record = {key: value for key, value in summary.items() if key != "summary_sha256"}
    record["summary_sha256"] = _hash_record(record, "summary_sha256")
    atomic_write_json(_summary_path(quarantine_root, str(record["run_id"])), record)
    return record


def load_run_summary(quarantine_root: Path, run_id: str) -> dict[str, Any] | None:
    path = _summary_path(quarantine_root, run_id)
    if not path.exists():
        return None
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError("Collector run summary must be a JSON object")
    if value.get("summary_sha256") != _hash_record(value, "summary_sha256"):
        raise ValueError("Collector run summary hash mismatch")
    if value.get("run_id") != run_id:
        raise ValueError("Collector run summary run_id mismatch")
    if value.get("run_ledger_boundary") != RUN_LEDGER_BOUNDARY:
        raise ValueError("Collector run summary ledger boundary mismatch")
    return value
