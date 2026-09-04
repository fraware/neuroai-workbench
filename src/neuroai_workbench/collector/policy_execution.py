from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..util import canonical_json_bytes, ensure_identifier, sha256_bytes, utc_now
from .acquisition_policy import (
    EXECUTION_MODES,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    require_acquisition_policy,
    validate_acquisition_policy,
)
from .adapters.base import CollectorAdapter
from .adapters.registry import adapter_for_source
from .config import CollectorConfig
from .credentials import CredentialProvider
from .dns import DnsGuard, DnsResolutionRecord
from .http_client import HttpRequest, HttpTransport, TransportResult
from .run_ledger import TERMINAL_TARGET_STATES, write_run_summary, write_target_checkpoint
from .scheduler import CollectionScheduler, SchedulerConfig
from .service import CollectionOutcome
from .url_normalize import RetrievalTargetGroup
from .url_policy import public_url_error

POLICY_EXECUTION_BOUNDARY = (
    "Policy-bound collection constrains operational network acquisition only. It does not establish source truth, "
    "adjudicate evidence, mutate assessments, authorize release or publication, or replace the independent live "
    "authorization, DNS, pinned-peer, quarantine, scanning, rights, and retention controls."
)


class PolicyExecutionBlocked(RuntimeError):
    """A request-scoped acquisition-policy refusal, distinct from collector/network failure."""


@dataclass(frozen=True)
class _PolicyBoundSchedulerConfig(SchedulerConfig):
    acquisition_policy_id: str = ""
    acquisition_policy_sha256: str = ""
    acquisition_programme_id: str = ""
    acquisition_execution_mode: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.acquisition_policy_id:
            raise ValueError("acquisition_policy_id must be present")
        if len(self.acquisition_policy_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.acquisition_policy_sha256
        ):
            raise ValueError("acquisition_policy_sha256 must be a lowercase SHA-256 digest")
        ensure_identifier(self.acquisition_programme_id, "acquisition_programme_id")
        if self.acquisition_execution_mode not in {ONLINE_REQUIRED, ONLINE_PREFERRED}:
            raise ValueError("Policy-bound HTTP execution mode must be ONLINE_REQUIRED or ONLINE_PREFERRED")


class AcquisitionPolicyRuntimeGuard:
    """Request-scoped policy guard shared by DNS and transport enforcement.

    The source binding is held in a ``ContextVar`` so concurrent scheduler worker
    threads cannot overwrite one another's logical-source scope. Both the DNS
    wrapper and transport wrapper use the same guard: policy is checked before
    DNS resolution and again immediately before every transport send.
    """

    def __init__(self, *, policy: dict[str, Any], programme_id: str, execution_mode: str) -> None:
        validated = validate_acquisition_policy(policy)
        ensure_identifier(programme_id, "programme_id")
        if validated["programme_id"] != programme_id:
            raise AcquisitionPolicyError("Acquisition policy programme_id does not match the executor programme")
        if execution_mode not in EXECUTION_MODES:
            raise AcquisitionPolicyError(f"Unsupported execution_mode {execution_mode!r}")
        if execution_mode == REPLAY_ONLY:
            raise AcquisitionPolicyError("REPLAY_ONLY cannot enter the HTTP due-cycle executor")
        self.policy = validated
        self.programme_id = programme_id
        self.execution_mode = execution_mode
        self._source_ids: ContextVar[tuple[str, ...] | None] = ContextVar(
            f"neuroai_acquisition_policy_sources_{id(self)}",
            default=None,
        )

    @property
    def binding(self) -> dict[str, str]:
        return {
            "policy_id": str(self.policy["policy_id"]),
            "policy_sha256": str(self.policy["policy_sha256"]),
            "programme_id": self.programme_id,
            "execution_mode": self.execution_mode,
        }

    @contextmanager
    def bind_source_ids(self, source_ids: Iterable[str]) -> Iterator[None]:
        normalized = tuple(sorted({ensure_identifier(str(source_id), "source_id") for source_id in source_ids}))
        if not normalized:
            raise AcquisitionPolicyError("Policy-bound network execution requires at least one logical source")
        token = self._source_ids.set(normalized)
        try:
            yield
        finally:
            self._source_ids.reset(token)

    def require_url(self, url: str, *, at: str | None = None) -> None:
        source_ids = self._source_ids.get()
        if not source_ids:
            raise PolicyExecutionBlocked("Policy-bound network operation has no request-scoped logical-source binding")
        checked_at = at or utc_now()
        for source_id in source_ids:
            try:
                require_acquisition_policy(
                    self.policy,
                    programme_id=self.programme_id,
                    source_id=source_id,
                    execution_mode=self.execution_mode,
                    requested_url=url,
                    fallback_to_prior_capture=False,
                    at=checked_at,
                )
            except AcquisitionPolicyError as exc:
                raise PolicyExecutionBlocked(
                    f"Acquisition policy blocked source {source_id!r} for {url!r}: {exc}"
                ) from exc


class PolicyBoundDnsGuard(DnsGuard):
    """Apply acquisition policy before any DNS lookup while preserving DnsGuard semantics."""

    def __init__(self, delegate: DnsGuard, policy_guard: AcquisitionPolicyRuntimeGuard) -> None:
        super().__init__(getaddrinfo=delegate.getaddrinfo)
        self._delegate = delegate
        self._policy_guard = policy_guard

    def new_session(self) -> PolicyBoundDnsGuard:
        return PolicyBoundDnsGuard(self._delegate.new_session(), self._policy_guard)

    def reset(self) -> None:
        self._delegate.reset()

    def resolve(self, url: str) -> DnsResolutionRecord:
        self._policy_guard.require_url(url)
        return self._delegate.resolve(url)


class PolicyBoundTransport:
    """Re-check acquisition policy immediately before every actual HTTP send."""

    def __init__(self, inner: HttpTransport, policy_guard: AcquisitionPolicyRuntimeGuard) -> None:
        self.inner = inner
        self._policy_guard = policy_guard

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> TransportResult:
        self._policy_guard.require_url(request.url)
        return self.inner.send(
            request,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )


class PolicyBoundCollectionScheduler(CollectionScheduler):
    """Explicit Phase-2A scheduler path bound to one validated acquisition policy.

    The legacy ``CollectionScheduler`` remains unchanged. This class is opt-in and
    is intended for controlled migration/proof work before any operational default
    transition. Policy metadata is inserted into the inherited scheduler
    configuration, which is already part of the deterministic run binding and
    manifest hash; changing policy identity, digest, programme, or mode therefore
    changes the deterministic run lineage.
    """

    def __init__(
        self,
        *,
        acquisition_policy: dict[str, Any],
        programme_id: str,
        execution_mode: str,
        collector_config: CollectorConfig,
        transport: HttpTransport,
        quarantine_root: Path,
        scheduler_config: SchedulerConfig | None = None,
        credential_provider: CredentialProvider | None = None,
        dns_guard: DnsGuard | None = None,
        sleeper=None,
        monotonic_clock=None,
    ) -> None:
        self.policy_guard = AcquisitionPolicyRuntimeGuard(
            policy=acquisition_policy,
            programme_id=programme_id,
            execution_mode=execution_mode,
        )
        base_config = scheduler_config or SchedulerConfig()
        base_values = {item.name: getattr(base_config, item.name) for item in fields(SchedulerConfig)}
        binding = self.policy_guard.binding
        bound_scheduler_config = _PolicyBoundSchedulerConfig(
            **base_values,
            acquisition_policy_id=binding["policy_id"],
            acquisition_policy_sha256=binding["policy_sha256"],
            acquisition_programme_id=binding["programme_id"],
            acquisition_execution_mode=binding["execution_mode"],
        )
        policy_transport = PolicyBoundTransport(transport, self.policy_guard)
        policy_dns = PolicyBoundDnsGuard(dns_guard or DnsGuard(), self.policy_guard)

        kwargs: dict[str, Any] = {
            "collector_config": collector_config,
            "transport": policy_transport,
            "quarantine_root": quarantine_root,
            "scheduler_config": bound_scheduler_config,
            "credential_provider": credential_provider,
            "dns_guard": policy_dns,
        }
        if sleeper is not None:
            kwargs["sleeper"] = sleeper
        if monotonic_clock is not None:
            kwargs["monotonic_clock"] = monotonic_clock
        super().__init__(**kwargs)

    @property
    def acquisition_binding(self) -> dict[str, str]:
        return self.policy_guard.binding

    def _precheck_item(
        self,
        item: dict[str, Any],
        *,
        source_index: dict[str, dict[str, Any]],
        adapters: dict[str, CollectorAdapter],
    ) -> dict[str, Any] | None:
        source_id = str(item["source_id"])
        if source_id in self.scheduler_config.disabled_source_ids:
            return None
        source_record = source_index.get(source_id)
        if source_record is None:
            return None
        requested_url = str(item.get("url") or source_record.get("url") or "")
        parsed = urlparse(requested_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if public_url_error(requested_url) is not None:
            return None
        adapter = adapter_for_source(adapters, source_record)
        if adapter.adapter_id in self.scheduler_config.disabled_adapter_ids:
            return None
        try:
            require_acquisition_policy(
                self.policy_guard.policy,
                programme_id=self.policy_guard.programme_id,
                source_id=source_id,
                execution_mode=self.policy_guard.execution_mode,
                requested_url=requested_url,
                fallback_to_prior_capture=False,
                at=utc_now(),
            )
        except AcquisitionPolicyError as exc:
            return {
                "source_id": source_id,
                "status": "FAILURE",
                "reason": "POLICY_BLOCK",
                "failure_class": "POLICY_BLOCK",
                "message": str(exc),
                "acquisition_policy_sha256": self.acquisition_binding["policy_sha256"],
                "acquisition_route": "LIVE",
            }
        return None

    def _prepare_execution(
        self,
        plan: dict[str, Any],
        *,
        source_index: dict[str, dict[str, Any]],
        adapters: dict[str, CollectorAdapter],
    ) -> tuple[list[RetrievalTargetGroup], list[dict[str, Any]], list[dict[str, Any]]]:
        filtered_plan = dict(plan)
        policy_blocks: list[dict[str, Any]] = []
        queues = ("due", "manual") if self.scheduler_config.include_manual_sources else ("due",)
        for queue in queues:
            filtered: list[dict[str, Any]] = []
            for raw_item in plan.get(queue, []):
                item = dict(raw_item)
                block = self._precheck_item(item, source_index=source_index, adapters=adapters)
                if block is None:
                    filtered.append(item)
                else:
                    policy_blocks.append(block)
            filtered_plan[queue] = filtered

        groups, targets, pre_outcomes = super()._prepare_execution(
            filtered_plan,
            source_index=source_index,
            adapters=adapters,
        )
        return groups, targets, [*pre_outcomes, *policy_blocks]

    def _invoke_adapter(
        self,
        adapter: CollectorAdapter,
        request: dict[str, Any],
        *,
        source_record: dict[str, Any],
        attempt_count: int,
    ) -> CollectionOutcome:
        try:
            resolved = adapter.resolve_request(request, source_record=source_record)
            resolved_url = str(resolved.get("requested_url", request["requested_url"]))
            self.policy_guard.require_url(resolved_url)
            return super()._invoke_adapter(
                adapter,
                request,
                source_record=source_record,
                attempt_count=attempt_count,
            )
        except PolicyExecutionBlocked as exc:
            return CollectionOutcome(
                kind="failure",
                record={
                    "request_id": request["request_id"],
                    "failure_class": "POLICY_BLOCK",
                    "failure_message": str(exc),
                },
            )

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
    ) -> dict[str, Any]:
        with self.policy_guard.bind_source_ids(group.source_ids):
            result = super()._execute_target(
                run_id=run_id,
                group=group,
                checkpoint=checkpoint,
                adapter=adapter,
                source_record=source_record,
                registry_sha256=registry_sha256,
                persisted_records=persisted_records,
            )
        changed = False
        for attempt in result.get("attempts", []):
            if not isinstance(attempt, dict):
                continue
            annotations = {
                "acquisition_route": "LIVE",
                "acquisition_policy_sha256": self.acquisition_binding["policy_sha256"],
                "acquisition_execution_mode": self.acquisition_binding["execution_mode"],
            }
            for key, value in annotations.items():
                if attempt.get(key) != value:
                    attempt[key] = value
                    changed = True
        if changed:
            return write_target_checkpoint(self.quarantine_root, result)
        return result

    def _apply_attempt_outcome(
        self,
        checkpoint: dict[str, Any],
        outcome: CollectionOutcome,
        *,
        recovered: bool,
        sleep_before_retry: bool,
    ) -> tuple[dict[str, Any], bool]:
        policy_blocked = outcome.kind == "failure" and outcome.record.get("failure_class") == "POLICY_BLOCK"
        if checkpoint.get("attempts"):
            attempt = checkpoint["attempts"][-1]
            attempt["acquisition_route"] = "LIVE"
            attempt["acquisition_policy_sha256"] = self.acquisition_binding["policy_sha256"]
            attempt["acquisition_execution_mode"] = self.acquisition_binding["execution_mode"]
            if policy_blocked:
                attempt["policy_blocked"] = True
                attempt["policy_block_message"] = outcome.record.get("failure_message")
        checkpoint, terminal = super()._apply_attempt_outcome(
            checkpoint,
            outcome,
            recovered=recovered,
            sleep_before_retry=sleep_before_retry,
        )
        if policy_blocked and isinstance(checkpoint.get("outcome"), dict):
            checkpoint["outcome"]["failure_message"] = outcome.record.get("failure_message")
            checkpoint = write_target_checkpoint(self.quarantine_root, checkpoint)
        return checkpoint, terminal

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
        """Build and atomically persist the policy-complete run summary once.

        This intentionally mirrors the base scheduler's accounting semantics while
        inserting acquisition-policy provenance before the authoritative summary
        write. A policy-bound run therefore cannot leave a valid intermediate
        summary that omits its acquisition binding if the process is interrupted.
        """
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
            checkpoint_outcome: dict[str, Any] = outcome_raw if isinstance(outcome_raw, dict) else {}
            if state == "FAILURE" and checkpoint_outcome.get("retryable") is True:
                retryable_final_failures += 1
            record_id = checkpoint_outcome.get("record_id")
            for source_id in target["source_ids"]:
                if state == "INTERNAL_ERROR":
                    source_outcome = {
                        "source_id": source_id,
                        "adapter_id": target["adapter_id"],
                        "status": "INCOMPLETE",
                        "reason": "internal_execution_error",
                        "retrieval_target_id": target_id,
                        "primary_source_id": target["primary_source_id"],
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
                    }
                    if checkpoint_outcome.get("failure_class") == "POLICY_BLOCK":
                        source_outcome["failure_class"] = "POLICY_BLOCK"
                        source_outcome["reason"] = "acquisition_policy_block"
                        message = checkpoint_outcome.get("failure_message")
                        if message:
                            source_outcome["message"] = message
                outcomes.append(source_outcome)
            retrieval_targets.append(
                {
                    "retrieval_target_id": target_id,
                    "normalized_url": target["normalized_url"],
                    "source_ids": list(target["source_ids"]),
                    "http_calls": len(attempts),
                    "attempt_count": len(attempts),
                    "status": state,
                    "resumed": target_id in resumed_target_ids,
                    "acquisition_route": "LIVE",
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
        acquisition = {
            **self.acquisition_binding,
            "route": "LIVE",
            "fallback_used": False,
            "boundary": POLICY_EXECUTION_BOUNDARY,
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
            "boundary": self.boundary,
            "run_ledger_boundary": self.run_ledger_boundary,
        }
        return write_run_summary(self.quarantine_root, summary)
