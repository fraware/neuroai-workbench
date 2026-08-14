from __future__ import annotations

import inspect
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path
from threading import BoundedSemaphore, Lock
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from ..util import canonical_json_bytes, sha256_bytes, utc_now
from .adapters.base import CollectorAdapter
from .adapters.registry import adapter_for_source, build_adapters
from .boundary import COLLECTOR_BOUNDARY
from .config import CollectorConfig
from .credentials import CredentialProvider
from .dns import DnsGuard
from .handoff import prepare_monitoring_handoff
from .http_client import HttpTransport
from .ids import new_request_id
from .run_ledger import (
    RUN_LEDGER_BOUNDARY,
    TERMINAL_TARGET_STATES,
    build_run_binding,
    deterministic_request_id,
    ensure_run_manifest,
    load_run_summary,
    load_target_checkpoint,
    scan_persisted_attempt_records,
    write_run_summary,
    write_target_checkpoint,
)
from .schemas import REQUEST_SCHEMA, validate_or_raise
from .service import CollectionOutcome
from .url_normalize import RetrievalTargetGroup, group_plan_items_by_retrieval_target
from .url_policy import public_url_error

HTTP_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
RETRYABLE_FAILURE_CLASSES = frozenset({"TIMEOUT", "NETWORK_ERROR"})
_HTTP_STATUS_RE = re.compile(r"\bstatus\s+(\d{3})\b", re.IGNORECASE)


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _dataclass_payload(value: Any) -> dict[str, Any]:
    return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}


def _failure_is_retryable(record: dict[str, Any]) -> bool:
    failure_class = str(record.get("failure_class", ""))
    if failure_class in RETRYABLE_FAILURE_CLASSES:
        return True
    if failure_class != "HTTP_ERROR":
        return False
    match = _HTTP_STATUS_RE.search(str(record.get("failure_message", "")))
    return bool(match and int(match.group(1)) in HTTP_RETRY_STATUSES)


def _outcome_from_persisted(record: dict[str, Any]) -> CollectionOutcome:
    if record.get("result_id"):
        return CollectionOutcome(kind="result", record=record)
    if record.get("failure_id"):
        return CollectionOutcome(kind="failure", record=record)
    raise ValueError("Durable collector record is neither a result nor a failure")


def _record_id(record: dict[str, Any]) -> str | None:
    value = record.get("result_id") or record.get("failure_id")
    return str(value) if value else None


@dataclass(frozen=True)
class SchedulerConfig:
    collection_enabled: bool = True
    handoff_enabled: bool = False
    disabled_source_ids: frozenset[str] = frozenset()
    disabled_adapter_ids: frozenset[str] = frozenset()
    include_manual_sources: bool = False
    max_workers: int = 8
    max_workers_per_host: int = 2
    resume_enabled: bool = True

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.max_workers_per_host < 1:
            raise ValueError("max_workers_per_host must be >= 1")
        if self.max_workers_per_host > self.max_workers:
            raise ValueError("max_workers_per_host cannot exceed max_workers")


class _HostPermitPool:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._lock = Lock()
        self._permits: dict[str, BoundedSemaphore] = {}

    def _host(self, url: str) -> str:
        hostname = urlparse(url).hostname
        return hostname.lower().rstrip(".") if hostname else "unknown"

    def _permit(self, host: str) -> BoundedSemaphore:
        with self._lock:
            permit = self._permits.get(host)
            if permit is None:
                permit = BoundedSemaphore(self.limit)
                self._permits[host] = permit
            return permit

    @contextmanager
    def acquire(self, url: str) -> Iterator[str]:
        host = self._host(url)
        permit = self._permit(host)
        permit.acquire()
        try:
            yield host
        finally:
            permit.release()


@dataclass
class CollectionScheduler:
    collector_config: CollectorConfig
    transport: HttpTransport
    quarantine_root: Path
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)
    credential_provider: CredentialProvider | None = None
    dns_guard: DnsGuard | None = None
    sleeper: Callable[[float], None] = time.sleep
    monotonic_clock: Callable[[], float] = time.monotonic

    def build_collection_request(
        self,
        plan_item: dict[str, Any],
        *,
        registry_sha256: str,
        request_id: str | None = None,
        requested_at: str | None = None,
    ) -> dict[str, Any]:
        request = {
            "request_id": request_id or new_request_id(),
            "source_id": plan_item["source_id"],
            "monitor_id": plan_item["monitor_id"],
            "requested_url": plan_item["url"],
            "requested_at": requested_at or utc_now(),
            "registry_sha256": registry_sha256,
            "collector_version": self.collector_config.collector_version,
            "configuration_hash": self.collector_config.configuration_hash,
            "boundary": COLLECTOR_BOUNDARY,
        }
        validate_or_raise(request, REQUEST_SCHEMA)
        return request

    def _prepare_execution(
        self,
        plan: dict[str, Any],
        *,
        source_index: dict[str, dict[str, Any]],
        adapters: dict[str, CollectorAdapter],
    ) -> tuple[list[RetrievalTargetGroup], list[dict[str, Any]], list[dict[str, Any]]]:
        items = list(plan.get("due", []))
        if self.scheduler_config.include_manual_sources:
            items.extend(plan.get("manual", []))

        eligible: list[dict[str, Any]] = []
        pre_outcomes: list[dict[str, Any]] = []
        for item in items:
            source_id = str(item["source_id"])
            if source_id in self.scheduler_config.disabled_source_ids:
                pre_outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "source_kill_switch"})
                continue
            source_record = source_index.get(source_id)
            if source_record is None:
                pre_outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "unknown_source"})
                continue
            requested_url = str(item.get("url") or source_record.get("url") or "")
            if not _is_http_url(requested_url):
                pre_outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "FAILURE",
                        "reason": "POLICY_BLOCK",
                        "failure_class": "POLICY_BLOCK",
                        "message": (
                            "Non-HTTP URL cannot enter the HTTP collector path; "
                            "use manual queue or LocalContentAddressedAdapter"
                        ),
                    }
                )
                continue
            policy_error = public_url_error(requested_url)
            if policy_error is not None:
                pre_outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "FAILURE",
                        "reason": "POLICY_BLOCK",
                        "failure_class": "POLICY_BLOCK",
                        "message": policy_error,
                    }
                )
                continue
            adapter = adapter_for_source(adapters, source_record)
            if adapter.adapter_id in self.scheduler_config.disabled_adapter_ids:
                pre_outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "SKIPPED",
                        "reason": "adapter_kill_switch",
                        "adapter_id": adapter.adapter_id,
                    }
                )
                continue
            eligible.append({**item, "url": requested_url})

        groups = group_plan_items_by_retrieval_target(eligible, source_index=source_index)
        targets: list[dict[str, Any]] = []
        for group in groups:
            primary_record = source_index[group.primary_source_id]
            adapter = adapter_for_source(adapters, primary_record)
            targets.append(
                {
                    "retrieval_target_id": group.retrieval_target_id,
                    "normalized_url": group.normalized_url,
                    "requested_url": group.requested_url,
                    "source_ids": list(group.source_ids),
                    "primary_source_id": group.primary_source_id,
                    "primary_monitor_id": group.primary_monitor_id,
                    "adapter_id": adapter.adapter_id,
                }
            )
        return groups, targets, pre_outcomes

    def _retry_delay(self, attempt_count: int) -> float:
        return float(
            min(
                self.collector_config.retry_max_delay_seconds,
                self.collector_config.retry_initial_delay_seconds * (2 ** max(0, attempt_count - 1)),
            )
        )

    def _invoke_adapter(
        self,
        adapter: CollectorAdapter,
        request: dict[str, Any],
        *,
        source_record: dict[str, Any],
        attempt_count: int,
    ) -> CollectionOutcome:
        collect = adapter.collect
        parameters = inspect.signature(collect).parameters
        kwargs: dict[str, Any] = {"attempt_count": attempt_count}
        if "source_record" in parameters:
            kwargs["source_record"] = source_record
        return collect(request, **kwargs)

    def _apply_attempt_outcome(
        self,
        checkpoint: dict[str, Any],
        outcome: CollectionOutcome,
        *,
        recovered: bool,
        sleep_before_retry: bool,
    ) -> tuple[dict[str, Any], bool]:
        attempts = checkpoint["attempts"]
        if not attempts:
            raise ValueError("Attempt outcome cannot be applied without an attempt record")
        attempt = attempts[-1]
        attempt_count = int(attempt["attempt_count"])
        record_id = _record_id(outcome.record)
        attempt.update(
            {
                "state": outcome.kind.upper(),
                "record_id": record_id,
                "completed_at": utc_now(),
                "recovered_from_durable_record": recovered,
            }
        )
        if outcome.kind == "failure":
            attempt["failure_class"] = outcome.record.get("failure_class")

        retryable = outcome.kind == "failure" and _failure_is_retryable(outcome.record)
        checkpoint["outcome"] = {
            "kind": outcome.kind.upper(),
            "record_id": record_id,
            "request_id": outcome.record.get("request_id"),
            "failure_class": outcome.record.get("failure_class") if outcome.kind == "failure" else None,
            "retryable": retryable,
        }
        if outcome.kind == "result":
            checkpoint["state"] = "RESULT"
            return write_target_checkpoint(self.quarantine_root, checkpoint), True

        if retryable and attempt_count < self.collector_config.max_attempts:
            delay = self._retry_delay(attempt_count)
            checkpoint["state"] = "RETRY_WAIT"
            checkpoint["retry_delay_seconds"] = delay
            checkpoint = write_target_checkpoint(self.quarantine_root, checkpoint)
            if sleep_before_retry and delay > 0:
                self.sleeper(delay)
            return checkpoint, False

        checkpoint["state"] = "FAILURE"
        checkpoint.pop("retry_delay_seconds", None)
        return write_target_checkpoint(self.quarantine_root, checkpoint), True

    def _execute_target(
        self,
        *,
        run_id: str,
        group: RetrievalTargetGroup,
        checkpoint: dict[str, Any],
        adapter: CollectorAdapter,
        source_record: dict[str, Any],
        registry_sha256: str,
        persisted_records: dict[str, dict[str, Any]],
        host_permits: _HostPermitPool,
    ) -> dict[str, Any]:
        if checkpoint.get("state") in TERMINAL_TARGET_STATES:
            return checkpoint

        try:
            attempts = checkpoint["attempts"]
            if checkpoint.get("state") in {"ATTEMPTING", "INTERNAL_ERROR"} and attempts:
                last_request_id = str(attempts[-1].get("request_id", ""))
                persisted = persisted_records.get(last_request_id)
                if persisted is not None:
                    checkpoint, terminal = self._apply_attempt_outcome(
                        checkpoint,
                        _outcome_from_persisted(persisted),
                        recovered=True,
                        sleep_before_retry=False,
                    )
                    if terminal:
                        return checkpoint
                    attempts = checkpoint["attempts"]

            while True:
                attempts = checkpoint["attempts"]
                reuse_attempt = checkpoint.get("state") in {"ATTEMPTING", "INTERNAL_ERROR"} and bool(attempts)
                if reuse_attempt:
                    attempt = attempts[-1]
                    attempt_count = int(attempt["attempt_count"])
                    request_id = str(attempt["request_id"])
                    requested_at = str(attempt["requested_at"])
                else:
                    attempt_count = len(attempts) + 1
                    if attempt_count > self.collector_config.max_attempts:
                        raise ValueError("Retry state exceeded configured max_attempts")
                    request_id = deterministic_request_id(run_id, group.retrieval_target_id, attempt_count)
                    requested_at = utc_now()
                    attempt = {
                        "attempt_count": attempt_count,
                        "request_id": request_id,
                        "requested_at": requested_at,
                        "state": "ATTEMPTING",
                    }
                    attempts.append(attempt)

                request = self.build_collection_request(
                    {
                        "source_id": group.primary_source_id,
                        "monitor_id": group.primary_monitor_id,
                        "url": group.normalized_url
                        if group.normalized_url.startswith(("http://", "https://"))
                        else group.requested_url,
                    },
                    registry_sha256=registry_sha256,
                    request_id=request_id,
                    requested_at=requested_at,
                )
                resolved = adapter.resolve_request(request, source_record=source_record)
                resolved_url = str(resolved.get("requested_url", request["requested_url"]))
                attempt["resolved_url"] = resolved_url
                checkpoint["state"] = "ATTEMPTING"
                checkpoint.pop("internal_error", None)
                checkpoint = write_target_checkpoint(self.quarantine_root, checkpoint)

                with host_permits.acquire(resolved_url) as host:
                    attempt["host"] = host
                    checkpoint = write_target_checkpoint(self.quarantine_root, checkpoint)
                    outcome = self._invoke_adapter(
                        adapter,
                        request,
                        source_record=source_record,
                        attempt_count=attempt_count,
                    )

                checkpoint, terminal = self._apply_attempt_outcome(
                    checkpoint,
                    outcome,
                    recovered=False,
                    sleep_before_retry=True,
                )
                if terminal:
                    return checkpoint
        except Exception as exc:
            checkpoint["state"] = "INTERNAL_ERROR"
            checkpoint["internal_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return write_target_checkpoint(self.quarantine_root, checkpoint)

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
                str(attempt.get("host")) for attempt in attempts if isinstance(attempt, dict) and attempt.get("host")
            }
            for host in sorted(hosts):
                per_host[host]["targets"] += 1
            for attempt in attempts:
                if isinstance(attempt, dict) and attempt.get("host"):
                    per_host[str(attempt["host"])]["attempts"] += 1

            state = str(checkpoint.get("state"))
            if state in TERMINAL_TARGET_STATES:
                terminal_targets += 1
            outcome_raw = checkpoint.get("outcome")
            outcome: dict[str, Any] = outcome_raw if isinstance(outcome_raw, dict) else {}
            if state == "FAILURE" and outcome.get("retryable") is True:
                retryable_final_failures += 1
            record_id = outcome.get("record_id")
            for source_id in target["source_ids"]:
                if state == "INTERNAL_ERROR":
                    outcomes.append(
                        {
                            "source_id": source_id,
                            "adapter_id": target["adapter_id"],
                            "status": "INCOMPLETE",
                            "reason": "internal_execution_error",
                            "retrieval_target_id": target_id,
                            "primary_source_id": target["primary_source_id"],
                        }
                    )
                else:
                    outcomes.append(
                        {
                            "source_id": source_id,
                            "adapter_id": target["adapter_id"],
                            "status": state,
                            "record_id": record_id,
                            "retrieval_target_id": target_id,
                            "primary_source_id": target["primary_source_id"],
                            "attempt_count": len(attempts),
                        }
                    )
            retrieval_targets.append(
                {
                    "retrieval_target_id": target_id,
                    "normalized_url": target["normalized_url"],
                    "source_ids": list(target["source_ids"]),
                    "http_calls": len(attempts),
                    "attempt_count": len(attempts),
                    "status": state,
                    "resumed": target_id in resumed_target_ids,
                }
            )

        outcomes = sorted(outcomes, key=lambda item: (str(item.get("source_id", "")), str(item.get("status", ""))))
        succeeded = sum(1 for item in outcomes if item["status"] == "RESULT")
        failed = sum(1 for item in outcomes if item["status"] == "FAILURE")
        skipped = sum(1 for item in outcomes if item["status"] == "SKIPPED")
        incomplete = sum(1 for item in outcomes if item["status"] == "INCOMPLETE")
        accountable = len(outcomes) - incomplete
        target_total = len(targets)
        source_total = len(outcomes)
        coalesced_source_count = sum(len(target["source_ids"]) for target in targets if len(target["source_ids"]) > 1)
        execution_status = "COMPLETE" if incomplete == 0 else "INCOMPLETE_INTERNAL_ERROR"
        if execution_status == "COMPLETE" and failed:
            execution_status = "COMPLETE_WITH_SOURCE_FAILURES"

        counts = {
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "incomplete": incomplete,
            "total": source_total,
            "unique_retrievals": sum(1 for checkpoint in checkpoints.values() if checkpoint.get("attempts")),
            "retrieval_target_groups": target_total,
            "completed_retrieval_targets": terminal_targets,
            "coalesced_source_count": coalesced_source_count,
            "logical_sources": source_total - skipped,
            "collection_attempts": total_attempts,
            "retries": max(
                0,
                total_attempts - sum(1 for checkpoint in checkpoints.values() if checkpoint.get("attempts")),
            ),
            "recovered_attempts": recovered_attempts,
            "resumed_targets": len(resumed_target_ids),
            "retryable_failures_exhausted": retryable_final_failures,
        }
        slo = {
            "source_accountability_coverage": 1.0 if source_total == 0 else accountable / source_total,
            "target_execution_coverage": 1.0 if target_total == 0 else terminal_targets / target_total,
            "source_accountability_complete": accountable == source_total,
            "target_execution_complete": terminal_targets == target_total,
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

    def run_plan(
        self,
        plan: dict[str, Any],
        *,
        registry_sha256: str,
        source_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.scheduler_config.collection_enabled:
            return self._killed_run(plan, reason="collection_disabled")

        adapters = build_adapters(
            config=self.collector_config,
            transport=self.transport,
            quarantine_root=self.quarantine_root,
            credential_provider=self.credential_provider,
            dns_guard=self.dns_guard,
            pace_rate_limits=True,
            sleeper=self.sleeper,
            monotonic_clock=self.monotonic_clock,
        )
        groups, targets, pre_outcomes = self._prepare_execution(
            plan,
            source_index=source_index,
            adapters=adapters,
        )
        binding = build_run_binding(
            plan=plan,
            registry_sha256=registry_sha256,
            collector_configuration=_dataclass_payload(self.collector_config),
            scheduler_configuration=_dataclass_payload(self.scheduler_config),
            targets=targets,
            pre_outcomes=pre_outcomes,
        )
        if not self.scheduler_config.resume_enabled:
            binding["execution_nonce"] = uuid4().hex
        manifest = ensure_run_manifest(self.quarantine_root, binding=binding)
        run_id = str(manifest["run_id"])
        existing_summary = load_run_summary(self.quarantine_root, run_id)
        if (
            existing_summary is not None
            and self.scheduler_config.resume_enabled
            and existing_summary.get("execution_status") in {"COMPLETE", "COMPLETE_WITH_SOURCE_FAILURES"}
        ):
            return existing_summary

        persisted_records = scan_persisted_attempt_records(self.quarantine_root)
        group_by_id = {group.retrieval_target_id: group for group in groups}
        target_by_id = {str(target["retrieval_target_id"]): target for target in targets}
        checkpoints: dict[str, dict[str, Any]] = {}
        resumed_target_ids: set[str] = set()
        for target_id, target in target_by_id.items():
            checkpoint = load_target_checkpoint(
                self.quarantine_root,
                run_id=run_id,
                target=target,
            )
            checkpoints[target_id] = checkpoint
            if checkpoint.get("state") in TERMINAL_TARGET_STATES:
                resumed_target_ids.add(target_id)

        host_permits = _HostPermitPool(self.scheduler_config.max_workers_per_host)
        pending_ids = [
            target_id
            for target_id in sorted(target_by_id)
            if checkpoints[target_id].get("state") not in TERMINAL_TARGET_STATES
        ]
        if pending_ids:
            with ThreadPoolExecutor(
                max_workers=self.scheduler_config.max_workers,
                thread_name_prefix="neuroai-collector",
            ) as pool:
                futures = {}
                for target_id in pending_ids:
                    target = target_by_id[target_id]
                    group = group_by_id[target_id]
                    source_record = source_index[group.primary_source_id]
                    adapter = adapters[str(target["adapter_id"])]
                    future = pool.submit(
                        self._execute_target,
                        run_id=run_id,
                        group=group,
                        checkpoint=checkpoints[target_id],
                        adapter=adapter,
                        source_record=source_record,
                        registry_sha256=registry_sha256,
                        persisted_records=persisted_records,
                        host_permits=host_permits,
                    )
                    futures[future] = target_id
                for future in as_completed(futures):
                    target_id = futures[future]
                    checkpoints[target_id] = future.result()

        return self._summarize_run(
            run_id=run_id,
            plan=plan,
            manifest=manifest,
            targets=targets,
            checkpoints=checkpoints,
            pre_outcomes=pre_outcomes,
            resumed_target_ids=resumed_target_ids,
        )

    def attempt_handoff(self, quarantine_id: str) -> dict[str, Any]:
        if not self.scheduler_config.handoff_enabled:
            raise ValueError("Monitoring handoff kill switch is engaged")
        payload = prepare_monitoring_handoff(self.quarantine_root, quarantine_id)
        return payload.as_dict()

    def _killed_run(self, plan: dict[str, Any], *, reason: str) -> dict[str, Any]:
        return {
            "run_id": f"CRUN-{uuid4().hex}",
            "plan_id": plan.get("plan_id"),
            "as_of": plan.get("as_of"),
            "status": "KILLED",
            "execution_status": "KILLED",
            "kill_reason": reason,
            "counts": {
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "incomplete": 0,
                "total": 0,
                "unique_retrievals": 0,
                "retrieval_target_groups": 0,
                "completed_retrieval_targets": 0,
                "coalesced_source_count": 0,
                "logical_sources": 0,
                "collection_attempts": 0,
                "retries": 0,
                "recovered_attempts": 0,
                "resumed_targets": 0,
                "retryable_failures_exhausted": 0,
            },
            "slo": {
                "source_accountability_coverage": 1.0,
                "target_execution_coverage": 1.0,
                "source_accountability_complete": True,
                "target_execution_complete": True,
            },
            "retrieval_targets": [],
            "outcomes": [],
            "boundary": COLLECTOR_BOUNDARY,
        }
