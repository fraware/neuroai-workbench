from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..util import canonical_json_bytes, load_json, safe_join, sha256_bytes
from .acquisition_policy import (
    ONLINE_PREFERRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    require_acquisition_policy,
    validate_acquisition_policy,
)
from .boundary import COLLECTOR_BOUNDARY
from .config import CollectorConfig
from .policy_execution import POLICY_EXECUTION_BOUNDARY, PolicyBoundCollectionScheduler
from .run_ledger import (
    RUN_LEDGER_BOUNDARY,
    TERMINAL_TARGET_STATES,
    build_run_binding,
    ensure_run_manifest,
    load_run_summary,
    load_target_checkpoint,
    write_run_summary,
    write_target_checkpoint,
)
from .scheduler import SchedulerConfig
from .url_normalize import RetrievalTargetGroup, group_plan_items_by_retrieval_target, normalize_retrieval_url
from .url_policy import public_url_error

PRIOR_CAPTURE_BOUNDARY = (
    "Prior-capture fallback and replay reuse immutable captured bytes for operational continuity. "
    "They do not represent a current live observation, establish source truth, adjudicate evidence, "
    "mutate assessments, authorize canonical S2 admission, release, or publication."
)
FALLBACK_ROUTE = "PRIOR_CAPTURE_FALLBACK"
REPLAY_ROUTE = "REPLAY"
LIVE_ROUTE = "LIVE"
FALLBACK_PENDING = "FALLBACK_PENDING"


class PriorCaptureError(ValueError):
    """Raised when a stored capture cannot satisfy immutable replay requirements."""


def _parse_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PriorCaptureError(f"{field} must be a non-empty timestamp string")
    if len(value) == 10:
        try:
            day = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise PriorCaptureError(f"{field} must be ISO-8601") from exc
        return datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise PriorCaptureError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PriorCaptureError(f"{field} must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _capture_age_seconds(*, as_of: str, retrieved_at: str) -> int:
    age = int(
        (
            _parse_timestamp(as_of, field="as_of")
            - _parse_timestamp(retrieved_at, field="retrieved_at")
        ).total_seconds()
    )
    if age < 0:
        raise PriorCaptureError("prior capture retrieved_at is later than the replay cutoff")
    return age


@dataclass(frozen=True)
class PriorCaptureReference:
    result_id: str
    source_id: str
    monitor_id: str
    requested_url: str
    normalized_url: str
    retrieved_at: str
    content_sha256: str
    quarantine_path: str
    size_bytes: int
    media_type: str
    original_filename: str

    def binding(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "source_id": self.source_id,
            "monitor_id": self.monitor_id,
            "requested_url": self.requested_url,
            "normalized_url": self.normalized_url,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "quarantine_path": self.quarantine_path,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "original_filename": self.original_filename,
        }

    @classmethod
    def from_binding(cls, value: dict[str, Any]) -> PriorCaptureReference:
        try:
            return cls(
                result_id=str(value["result_id"]),
                source_id=str(value["source_id"]),
                monitor_id=str(value["monitor_id"]),
                requested_url=str(value["requested_url"]),
                normalized_url=str(value["normalized_url"]),
                retrieved_at=str(value["retrieved_at"]),
                content_sha256=str(value["content_sha256"]),
                quarantine_path=str(value["quarantine_path"]),
                size_bytes=int(value["size_bytes"]),
                media_type=str(value["media_type"]),
                original_filename=str(value["original_filename"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PriorCaptureError("prior capture binding is malformed") from exc


@dataclass(frozen=True)
class PriorCaptureSnapshot:
    captures: tuple[PriorCaptureReference, ...]
    snapshot_sha256: str

    def select(self, normalized_url: str, *, as_of: str) -> PriorCaptureReference | None:
        cutoff = _parse_timestamp(as_of, field="as_of")
        candidates = [
            item
            for item in self.captures
            if item.normalized_url == normalized_url
            and _parse_timestamp(item.retrieved_at, field="retrieved_at") <= cutoff
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (_parse_timestamp(item.retrieved_at, field="retrieved_at"), item.result_id),
        )


def _reference_from_result(quarantine_root: Path, result: dict[str, Any]) -> PriorCaptureReference:
    required = (
        "result_id",
        "source_id",
        "monitor_id",
        "requested_url",
        "retrieved_at",
        "sha256",
        "quarantine_path",
        "size_bytes",
        "media_type",
        "original_filename",
    )
    if any(key not in result for key in required):
        raise PriorCaptureError("result record is missing prior-capture fields")
    requested_url = str(result["requested_url"])
    normalized_url = normalize_retrieval_url(requested_url)
    if not normalized_url.startswith(("http://", "https://")):
        raise PriorCaptureError("prior capture requested_url is not HTTP(S)")
    _parse_timestamp(str(result["retrieved_at"]), field="retrieved_at")
    content_sha256 = str(result["sha256"])
    if len(content_sha256) != 64 or any(character not in "0123456789abcdef" for character in content_sha256):
        raise PriorCaptureError("prior capture content SHA-256 is malformed")
    size_bytes = result["size_bytes"]
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
        raise PriorCaptureError("prior capture size_bytes is invalid")
    quarantine_path = str(result["quarantine_path"])
    path = safe_join(quarantine_root, quarantine_path)
    if not path.is_file():
        raise PriorCaptureError("prior capture bytes are missing")
    body = path.read_bytes()
    if len(body) != size_bytes:
        raise PriorCaptureError("prior capture byte size does not match result record")
    if sha256_bytes(body) != content_sha256:
        raise PriorCaptureError("prior capture bytes do not match result SHA-256")
    result_id = str(result["result_id"])
    if not result_id:
        raise PriorCaptureError("prior capture result_id is empty")
    return PriorCaptureReference(
        result_id=result_id,
        source_id=str(result["source_id"]),
        monitor_id=str(result["monitor_id"]),
        requested_url=requested_url,
        normalized_url=normalized_url,
        retrieved_at=str(result["retrieved_at"]),
        content_sha256=content_sha256,
        quarantine_path=quarantine_path,
        size_bytes=size_bytes,
        media_type=str(result["media_type"]),
        original_filename=str(result["original_filename"]),
    )


def build_prior_capture_snapshot(quarantine_root: Path) -> PriorCaptureSnapshot:
    root = safe_join(quarantine_root, "results")
    captures: list[PriorCaptureReference] = []
    if root.exists():
        for path in sorted(root.glob("*.json")):
            try:
                value = load_json(path)
            except (OSError, json.JSONDecodeError, UnicodeError):
                continue
            if not isinstance(value, dict):
                continue
            try:
                captures.append(_reference_from_result(quarantine_root, value))
            except PriorCaptureError:
                continue
    captures.sort(key=lambda item: (item.normalized_url, item.retrieved_at, item.result_id))
    payload = [item.binding() for item in captures]
    return PriorCaptureSnapshot(
        captures=tuple(captures),
        snapshot_sha256=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_prior_capture_reference(quarantine_root: Path, reference: PriorCaptureReference) -> None:
    result_path = safe_join(quarantine_root, "results", f"{reference.result_id}.json")
    if not result_path.is_file():
        raise PriorCaptureError("bound prior result record is missing")
    value = load_json(result_path)
    if not isinstance(value, dict):
        raise PriorCaptureError("bound prior result record is not an object")
    current = _reference_from_result(quarantine_root, value)
    if canonical_json_bytes(current.binding()) != canonical_json_bytes(reference.binding()):
        raise PriorCaptureError("bound prior capture identity changed after run binding")


def _fallback_binding_digest(targets: list[dict[str, Any]]) -> str:
    payload = [
        {
            "retrieval_target_id": str(target["retrieval_target_id"]),
            "prior_capture": target.get("prior_capture"),
        }
        for target in sorted(targets, key=lambda item: str(item["retrieval_target_id"]))
    ]
    return sha256_bytes(canonical_json_bytes(payload))


class PolicyBoundFallbackCollectionScheduler(PolicyBoundCollectionScheduler):
    """Phase-2B live-first scheduler with explicit policy-authorized prior-capture fallback."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._fallback_as_of = ""

    def _fallback_permitted_for_target(self, target: dict[str, Any], *, as_of: str) -> bool:
        if self.policy_guard.execution_mode != ONLINE_PREFERRED:
            return False
        for source_id in target["source_ids"]:
            try:
                require_acquisition_policy(
                    self.policy_guard.policy,
                    programme_id=self.policy_guard.programme_id,
                    source_id=str(source_id),
                    execution_mode=ONLINE_PREFERRED,
                    requested_url=str(target["normalized_url"]),
                    fallback_to_prior_capture=True,
                    at=_parse_timestamp(as_of, field="as_of").isoformat().replace("+00:00", "Z"),
                )
            except AcquisitionPolicyError:
                return False
        return True

    def _prepare_execution(
        self,
        plan: dict[str, Any],
        *,
        source_index: dict[str, dict[str, Any]],
        adapters: dict[str, Any],
    ) -> tuple[list[RetrievalTargetGroup], list[dict[str, Any]], list[dict[str, Any]]]:
        groups, targets, pre_outcomes = super()._prepare_execution(plan, source_index=source_index, adapters=adapters)
        as_of = str(plan.get("as_of") or "")
        _parse_timestamp(as_of, field="as_of")
        self._fallback_as_of = as_of
        snapshot = build_prior_capture_snapshot(self.quarantine_root)
        for target in targets:
            capture = snapshot.select(str(target["normalized_url"]), as_of=as_of)
            if capture is not None and self._fallback_permitted_for_target(target, as_of=as_of):
                target["prior_capture"] = capture.binding()
            else:
                target["prior_capture"] = None
        digest = _fallback_binding_digest(targets)
        for target in targets:
            target["fallback_snapshot_sha256"] = digest
        return groups, targets, pre_outcomes

    def _apply_bound_fallback(self, checkpoint: dict[str, Any], group: RetrievalTargetGroup) -> dict[str, Any]:
        binding = checkpoint.get("target", {}).get("prior_capture")
        if not isinstance(binding, dict):
            checkpoint["state"] = "FAILURE"
            checkpoint.pop("fallback_pending", None)
            return write_target_checkpoint(self.quarantine_root, checkpoint)
        reference = PriorCaptureReference.from_binding(binding)
        try:
            verify_prior_capture_reference(self.quarantine_root, reference)
            at = _parse_timestamp(self._fallback_as_of, field="as_of").isoformat().replace("+00:00", "Z")
            for source_id in group.source_ids:
                require_acquisition_policy(
                    self.policy_guard.policy,
                    programme_id=self.policy_guard.programme_id,
                    source_id=source_id,
                    execution_mode=ONLINE_PREFERRED,
                    requested_url=group.normalized_url,
                    fallback_to_prior_capture=True,
                    at=at,
                )
            age = _capture_age_seconds(as_of=self._fallback_as_of, retrieved_at=reference.retrieved_at)
        except (PriorCaptureError, AcquisitionPolicyError) as exc:
            checkpoint["state"] = "FAILURE"
            checkpoint["fallback_rejected"] = {"type": type(exc).__name__, "message": str(exc)}
            checkpoint.pop("fallback_pending", None)
            return write_target_checkpoint(self.quarantine_root, checkpoint)

        live_outcome = checkpoint.get("outcome")
        checkpoint["live_terminal_outcome"] = dict(live_outcome) if isinstance(live_outcome, dict) else None
        checkpoint["fallback"] = {
            "route": FALLBACK_ROUTE,
            "result_id": reference.result_id,
            "retrieved_at": reference.retrieved_at,
            "content_sha256": reference.content_sha256,
            "capture_age_seconds": age,
            "original_source_id": reference.source_id,
            "boundary": PRIOR_CAPTURE_BOUNDARY,
        }
        checkpoint["outcome"] = {
            "kind": "RESULT",
            "record_id": reference.result_id,
            "request_id": None,
            "failure_class": None,
            "retryable": False,
            "acquisition_route": FALLBACK_ROUTE,
        }
        checkpoint["state"] = "RESULT"
        checkpoint.pop("fallback_pending", None)
        return write_target_checkpoint(self.quarantine_root, checkpoint)

    def _execute_target(
        self,
        *,
        run_id: str,
        group: RetrievalTargetGroup,
        checkpoint: dict[str, Any],
        adapter: Any,
        source_record: dict[str, Any],
        registry_sha256: str,
        persisted_records: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if checkpoint.get("state") == FALLBACK_PENDING:
            return self._apply_bound_fallback(checkpoint, group)
        result = super()._execute_target(
            run_id=run_id,
            group=group,
            checkpoint=checkpoint,
            adapter=adapter,
            source_record=source_record,
            registry_sha256=registry_sha256,
            persisted_records=persisted_records,
        )
        if result.get("state") != "FAILURE":
            return result
        outcome = result.get("outcome")
        target = result.get("target")
        if (
            self.policy_guard.execution_mode != ONLINE_PREFERRED
            or not isinstance(outcome, dict)
            or outcome.get("retryable") is not True
            or not isinstance(target, dict)
            or not isinstance(target.get("prior_capture"), dict)
        ):
            return result
        result["state"] = FALLBACK_PENDING
        result["fallback_pending"] = dict(target["prior_capture"])
        result = write_target_checkpoint(self.quarantine_root, result)
        return self._apply_bound_fallback(result, group)

    def _summarize_run(
        self,
        *,
        run_id: str,
        plan: dict[str, Any],
        manifest: dict[str, Any],
        targets: list[dict[str, Any]],
        checkpoints: dict[str, dict[str, Any]],
        pre_outcomes: list[dict[str, Any]],
        resumed_target_ids: set[str],
    ) -> dict[str, Any]:
        outcomes = [dict(item) for item in pre_outcomes]
        retrieval_targets: list[dict[str, Any]] = []
        per_host: dict[str, dict[str, int]] = defaultdict(lambda: {"targets": 0, "attempts": 0})
        total_attempts = 0
        recovered_attempts = 0
        terminal_targets = 0
        retryable_final_failures = 0
        fallback_count = 0

        for target in sorted(targets, key=lambda item: str(item["retrieval_target_id"])):
            target_id = str(target["retrieval_target_id"])
            checkpoint = checkpoints[target_id]
            attempts = checkpoint.get("attempts", [])
            total_attempts += len(attempts)
            recovered_attempts += sum(
                1
                for attempt in attempts
                if isinstance(attempt, dict) and attempt.get("recovered_from_durable_record") is True
            )
            hosts = {
                str(attempt.get("host"))
                for attempt in attempts
                if isinstance(attempt, dict) and attempt.get("host")
            }
            for host in sorted(hosts):
                per_host[host]["targets"] += 1
            for attempt in attempts:
                if isinstance(attempt, dict) and attempt.get("host"):
                    per_host[str(attempt["host"])]["attempts"] += 1

            state = str(checkpoint.get("state"))
            if state in TERMINAL_TARGET_STATES:
                terminal_targets += 1
            checkpoint_outcome = checkpoint.get("outcome") if isinstance(checkpoint.get("outcome"), dict) else {}
            if state == "FAILURE" and checkpoint_outcome.get("retryable") is True:
                retryable_final_failures += 1
            fallback = checkpoint.get("fallback") if isinstance(checkpoint.get("fallback"), dict) else None
            route = FALLBACK_ROUTE if fallback is not None else LIVE_ROUTE
            if fallback is not None:
                fallback_count += 1
            record_id = checkpoint_outcome.get("record_id")
            for source_id in target["source_ids"]:
                if state == "INTERNAL_ERROR" or state == FALLBACK_PENDING:
                    source_outcome = {
                        "source_id": source_id,
                        "adapter_id": target["adapter_id"],
                        "status": "INCOMPLETE",
                        "reason": "internal_execution_error" if state == "INTERNAL_ERROR" else "fallback_interrupted",
                        "retrieval_target_id": target_id,
                        "primary_source_id": target["primary_source_id"],
                        "acquisition_route": route,
                    }
                else:
                    source_outcome = {
                        "source_id": source_id,
                        "adapter_id": target["adapter_id"],
                        "status": state,
                        "record_id": record_id,
                        "retrieval_target_id": target_id,
                        "primary_source_id": target["primary_source_id"],
                        "attempt_count": len(attempts),
                        "acquisition_route": route,
                    }
                    if fallback is not None:
                        source_outcome["prior_capture"] = dict(fallback)
                    if checkpoint_outcome.get("failure_class") == "POLICY_BLOCK":
                        source_outcome["failure_class"] = "POLICY_BLOCK"
                        source_outcome["reason"] = "acquisition_policy_block"
                outcomes.append(source_outcome)
            retrieval_target = {
                "retrieval_target_id": target_id,
                "normalized_url": target["normalized_url"],
                "source_ids": list(target["source_ids"]),
                "http_calls": len(attempts),
                "attempt_count": len(attempts),
                "status": state,
                "resumed": target_id in resumed_target_ids,
                "acquisition_route": route,
            }
            if fallback is not None:
                retrieval_target["prior_capture"] = dict(fallback)
            retrieval_targets.append(retrieval_target)

        outcomes = sorted(outcomes, key=lambda item: (str(item.get("source_id", "")), str(item.get("status", ""))))
        succeeded = sum(1 for item in outcomes if item["status"] == "RESULT")
        failed = sum(1 for item in outcomes if item["status"] == "FAILURE")
        skipped = sum(1 for item in outcomes if item["status"] == "SKIPPED")
        incomplete = sum(1 for item in outcomes if item["status"] == "INCOMPLETE")
        source_total = len(outcomes)
        target_total = len(targets)
        accountable = source_total - incomplete
        terminal_attempted_targets = sum(1 for checkpoint in checkpoints.values() if checkpoint.get("attempts"))
        execution_status = "COMPLETE" if incomplete == 0 else "INCOMPLETE_INTERNAL_ERROR"
        if execution_status == "COMPLETE" and failed:
            execution_status = "COMPLETE_WITH_SOURCE_FAILURES"
        counts = {
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "incomplete": incomplete,
            "total": source_total,
            "unique_retrievals": terminal_attempted_targets,
            "retrieval_target_groups": target_total,
            "completed_retrieval_targets": terminal_targets,
            "coalesced_source_count": sum(
                len(target["source_ids"]) for target in targets if len(target["source_ids"]) > 1
            ),
            "logical_sources": source_total - skipped,
            "collection_attempts": total_attempts,
            "retries": max(0, total_attempts - terminal_attempted_targets),
            "recovered_attempts": recovered_attempts,
            "resumed_targets": len(resumed_target_ids),
            "retryable_failures_exhausted": retryable_final_failures,
            "prior_capture_fallbacks": fallback_count,
            "replays": 0,
        }
        slo = {
            "source_accountability_coverage": 1.0 if source_total == 0 else accountable / source_total,
            "target_execution_coverage": 1.0 if target_total == 0 else terminal_targets / target_total,
            "source_accountability_complete": accountable == source_total,
            "target_execution_complete": terminal_targets == target_total,
        }
        acquisition = {
            **self.acquisition_binding,
            "route": "MIXED_LIVE_AND_PRIOR_CAPTURE" if fallback_count else LIVE_ROUTE,
            "fallback_used": fallback_count > 0,
            "fallback_count": fallback_count,
            "boundary": POLICY_EXECUTION_BOUNDARY,
            "prior_capture_boundary": PRIOR_CAPTURE_BOUNDARY,
        }
        semantic = {
            "run_id": run_id,
            "plan_id": plan.get("plan_id"),
            "execution_status": execution_status,
            "counts": counts,
            "slo": slo,
            "retrieval_targets": retrieval_targets,
            "outcomes": outcomes,
            "per_host": {host: dict(values) for host, values in sorted(per_host.items())},
            "acquisition": acquisition,
        }
        summary = {
            **semantic,
            "semantic_summary_sha256": sha256_bytes(canonical_json_bytes(semantic)),
            "as_of": plan.get("as_of"),
            "status": "COMPLETED" if incomplete == 0 else "INCOMPLETE",
            "manifest_sha256": manifest["manifest_sha256"],
            "binding_sha256": manifest["binding_sha256"],
            "boundary": COLLECTOR_BOUNDARY,
            "run_ledger_boundary": RUN_LEDGER_BOUNDARY,
        }
        return write_run_summary(self.quarantine_root, summary)


class ReplayOnlyCollectionScheduler:
    """Deterministic replay executor with no network/DNS/adapter construction path."""

    def __init__(
        self,
        *,
        acquisition_policy: dict[str, Any],
        programme_id: str,
        collector_config: CollectorConfig,
        quarantine_root: Path,
        scheduler_config: SchedulerConfig | None = None,
    ) -> None:
        self.policy = validate_acquisition_policy(acquisition_policy)
        if self.policy["programme_id"] != programme_id:
            raise AcquisitionPolicyError("Acquisition policy programme_id does not match the replay programme")
        self.programme_id = programme_id
        self.collector_config = collector_config
        self.quarantine_root = quarantine_root
        self.scheduler_config = scheduler_config or SchedulerConfig()

    @property
    def acquisition_binding(self) -> dict[str, str]:
        return {
            "policy_id": str(self.policy["policy_id"]),
            "policy_sha256": str(self.policy["policy_sha256"]),
            "programme_id": self.programme_id,
            "execution_mode": REPLAY_ONLY,
        }

    def _prepare(
        self,
        plan: dict[str, Any],
        *,
        source_index: dict[str, dict[str, Any]],
    ) -> tuple[list[RetrievalTargetGroup], list[dict[str, Any]], list[dict[str, Any]]]:
        as_of = str(plan.get("as_of") or "")
        at = _parse_timestamp(as_of, field="as_of").isoformat().replace("+00:00", "Z")
        items = list(plan.get("due", []))
        if self.scheduler_config.include_manual_sources:
            items.extend(plan.get("manual", []))
        eligible: list[dict[str, Any]] = []
        pre_outcomes: list[dict[str, Any]] = []
        for raw in items:
            item = dict(raw)
            source_id = str(item["source_id"])
            if source_id in self.scheduler_config.disabled_source_ids:
                pre_outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "source_kill_switch"})
                continue
            source = source_index.get(source_id)
            if source is None:
                pre_outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "unknown_source"})
                continue
            requested_url = str(item.get("url") or source.get("url") or "")
            parsed = urlparse(requested_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or public_url_error(requested_url) is not None
            ):
                pre_outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "FAILURE",
                        "reason": "POLICY_BLOCK",
                        "failure_class": "POLICY_BLOCK",
                    }
                )
                continue
            try:
                require_acquisition_policy(
                    self.policy,
                    programme_id=self.programme_id,
                    source_id=source_id,
                    execution_mode=REPLAY_ONLY,
                    requested_url=None,
                    fallback_to_prior_capture=False,
                    at=at,
                )
            except AcquisitionPolicyError as exc:
                pre_outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "FAILURE",
                        "reason": "POLICY_BLOCK",
                        "failure_class": "POLICY_BLOCK",
                        "message": str(exc),
                    }
                )
                continue
            eligible.append({**item, "url": requested_url})
        groups = group_plan_items_by_retrieval_target(eligible, source_index=source_index)
        snapshot = build_prior_capture_snapshot(self.quarantine_root)
        targets: list[dict[str, Any]] = []
        for group in groups:
            capture = snapshot.select(group.normalized_url, as_of=as_of)
            targets.append(
                {
                    "retrieval_target_id": group.retrieval_target_id,
                    "normalized_url": group.normalized_url,
                    "requested_url": group.requested_url,
                    "source_ids": list(group.source_ids),
                    "primary_source_id": group.primary_source_id,
                    "primary_monitor_id": group.primary_monitor_id,
                    "adapter_id": "replay_only",
                    "prior_capture": capture.binding() if capture is not None else None,
                }
            )
        digest = _fallback_binding_digest(targets)
        for target in targets:
            target["fallback_snapshot_sha256"] = digest
        return groups, targets, pre_outcomes

    def run_plan(
        self,
        plan: dict[str, Any],
        *,
        registry_sha256: str,
        source_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.scheduler_config.collection_enabled:
            raise ValueError("Replay execution is disabled by scheduler configuration")
        groups, targets, pre_outcomes = self._prepare(plan, source_index=source_index)
        collector_configuration = {
            "collector_version": self.collector_config.collector_version,
            "configuration_hash": self.collector_config.configuration_hash,
            "replay_only": True,
        }
        scheduler_configuration = {
            "collection_enabled": self.scheduler_config.collection_enabled,
            "include_manual_sources": self.scheduler_config.include_manual_sources,
            "disabled_source_ids": sorted(self.scheduler_config.disabled_source_ids),
            "resume_enabled": self.scheduler_config.resume_enabled,
            **self.acquisition_binding,
        }
        binding = build_run_binding(
            plan=plan,
            registry_sha256=registry_sha256,
            collector_configuration=collector_configuration,
            scheduler_configuration=scheduler_configuration,
            targets=targets,
            pre_outcomes=pre_outcomes,
        )
        manifest = ensure_run_manifest(self.quarantine_root, binding=binding)
        run_id = str(manifest["run_id"])
        existing = load_run_summary(self.quarantine_root, run_id)
        if (
            existing is not None
            and self.scheduler_config.resume_enabled
            and existing.get("execution_status") in {"COMPLETE", "COMPLETE_WITH_SOURCE_FAILURES"}
        ):
            return existing

        target_by_id = {str(target["retrieval_target_id"]): target for target in targets}
        group_by_id = {group.retrieval_target_id: group for group in groups}
        checkpoints: dict[str, dict[str, Any]] = {}
        resumed: set[str] = set()
        as_of = str(plan.get("as_of") or "")
        for target_id, target in target_by_id.items():
            checkpoint = load_target_checkpoint(self.quarantine_root, run_id=run_id, target=target)
            if checkpoint.get("state") in TERMINAL_TARGET_STATES:
                resumed.add(target_id)
                checkpoints[target_id] = checkpoint
                continue
            capture_binding = target.get("prior_capture")
            if not isinstance(capture_binding, dict):
                checkpoint["state"] = "FAILURE"
                checkpoint["outcome"] = {
                    "kind": "FAILURE",
                    "record_id": None,
                    "request_id": None,
                    "failure_class": "REPLAY_CAPTURE_MISSING",
                    "retryable": False,
                    "acquisition_route": REPLAY_ROUTE,
                }
            else:
                reference = PriorCaptureReference.from_binding(capture_binding)
                verify_prior_capture_reference(self.quarantine_root, reference)
                age = _capture_age_seconds(as_of=as_of, retrieved_at=reference.retrieved_at)
                checkpoint["state"] = "RESULT"
                checkpoint["replay"] = {
                    "route": REPLAY_ROUTE,
                    "result_id": reference.result_id,
                    "retrieved_at": reference.retrieved_at,
                    "content_sha256": reference.content_sha256,
                    "capture_age_seconds": age,
                    "original_source_id": reference.source_id,
                    "boundary": PRIOR_CAPTURE_BOUNDARY,
                }
                checkpoint["outcome"] = {
                    "kind": "RESULT",
                    "record_id": reference.result_id,
                    "request_id": None,
                    "failure_class": None,
                    "retryable": False,
                    "acquisition_route": REPLAY_ROUTE,
                }
            checkpoints[target_id] = write_target_checkpoint(self.quarantine_root, checkpoint)
        return self._summarize_replay(
            run_id=run_id,
            plan=plan,
            manifest=manifest,
            targets=targets,
            checkpoints=checkpoints,
            pre_outcomes=pre_outcomes,
            resumed=resumed,
        )

    def _summarize_replay(
        self,
        *,
        run_id: str,
        plan: dict[str, Any],
        manifest: dict[str, Any],
        targets: list[dict[str, Any]],
        checkpoints: dict[str, dict[str, Any]],
        pre_outcomes: list[dict[str, Any]],
        resumed: set[str],
    ) -> dict[str, Any]:
        outcomes = [dict(item) for item in pre_outcomes]
        retrieval_targets: list[dict[str, Any]] = []
        for target in sorted(targets, key=lambda item: str(item["retrieval_target_id"])):
            target_id = str(target["retrieval_target_id"])
            checkpoint = checkpoints[target_id]
            state = str(checkpoint["state"])
            outcome = checkpoint.get("outcome") if isinstance(checkpoint.get("outcome"), dict) else {}
            replay = checkpoint.get("replay") if isinstance(checkpoint.get("replay"), dict) else None
            for source_id in target["source_ids"]:
                item = {
                    "source_id": source_id,
                    "adapter_id": "replay_only",
                    "status": state,
                    "record_id": outcome.get("record_id"),
                    "retrieval_target_id": target_id,
                    "primary_source_id": target["primary_source_id"],
                    "attempt_count": 0,
                    "acquisition_route": REPLAY_ROUTE,
                }
                if replay is not None:
                    item["prior_capture"] = dict(replay)
                if outcome.get("failure_class"):
                    item["failure_class"] = outcome["failure_class"]
                outcomes.append(item)
            entry = {
                "retrieval_target_id": target_id,
                "normalized_url": target["normalized_url"],
                "source_ids": list(target["source_ids"]),
                "http_calls": 0,
                "attempt_count": 0,
                "status": state,
                "resumed": target_id in resumed,
                "acquisition_route": REPLAY_ROUTE,
            }
            if replay is not None:
                entry["prior_capture"] = dict(replay)
            retrieval_targets.append(entry)
        outcomes = sorted(outcomes, key=lambda item: (str(item.get("source_id", "")), str(item.get("status", ""))))
        succeeded = sum(1 for item in outcomes if item["status"] == "RESULT")
        failed = sum(1 for item in outcomes if item["status"] == "FAILURE")
        skipped = sum(1 for item in outcomes if item["status"] == "SKIPPED")
        incomplete = sum(1 for item in outcomes if item["status"] == "INCOMPLETE")
        source_total = len(outcomes)
        target_total = len(targets)
        execution_status = "COMPLETE_WITH_SOURCE_FAILURES" if failed else "COMPLETE"
        counts = {
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "incomplete": incomplete,
            "total": source_total,
            "unique_retrievals": 0,
            "retrieval_target_groups": target_total,
            "completed_retrieval_targets": sum(
                1 for checkpoint in checkpoints.values() if checkpoint.get("state") in TERMINAL_TARGET_STATES
            ),
            "coalesced_source_count": sum(
                len(target["source_ids"]) for target in targets if len(target["source_ids"]) > 1
            ),
            "logical_sources": source_total - skipped,
            "collection_attempts": 0,
            "retries": 0,
            "recovered_attempts": 0,
            "resumed_targets": len(resumed),
            "retryable_failures_exhausted": 0,
            "prior_capture_fallbacks": 0,
            "replays": sum(1 for checkpoint in checkpoints.values() if isinstance(checkpoint.get("replay"), dict)),
        }
        completed = counts["completed_retrieval_targets"]
        accountable = source_total - incomplete
        slo = {
            "source_accountability_coverage": 1.0 if source_total == 0 else accountable / source_total,
            "target_execution_coverage": 1.0 if target_total == 0 else completed / target_total,
            "source_accountability_complete": accountable == source_total,
            "target_execution_complete": completed == target_total,
        }
        acquisition = {
            **self.acquisition_binding,
            "route": REPLAY_ROUTE,
            "fallback_used": False,
            "boundary": PRIOR_CAPTURE_BOUNDARY,
        }
        semantic = {
            "run_id": run_id,
            "plan_id": plan.get("plan_id"),
            "execution_status": execution_status,
            "counts": counts,
            "slo": slo,
            "retrieval_targets": retrieval_targets,
            "outcomes": outcomes,
            "per_host": {},
            "acquisition": acquisition,
        }
        summary = {
            **semantic,
            "semantic_summary_sha256": sha256_bytes(canonical_json_bytes(semantic)),
            "as_of": plan.get("as_of"),
            "status": "COMPLETED",
            "manifest_sha256": manifest["manifest_sha256"],
            "binding_sha256": manifest["binding_sha256"],
            "boundary": COLLECTOR_BOUNDARY,
            "run_ledger_boundary": RUN_LEDGER_BOUNDARY,
        }
        return write_run_summary(self.quarantine_root, summary)
