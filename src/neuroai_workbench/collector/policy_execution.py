from __future__ import annotations

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
from .run_ledger import write_run_summary, write_target_checkpoint
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

    def _summarize_run(self, **kwargs: Any) -> dict[str, Any]:
        summary = dict(super()._summarize_run(**kwargs))
        checkpoints = kwargs.get("checkpoints")
        if isinstance(checkpoints, dict):
            for outcome in summary.get("outcomes", []):
                if not isinstance(outcome, dict):
                    continue
                target_id = outcome.get("retrieval_target_id")
                checkpoint = checkpoints.get(str(target_id)) if target_id is not None else None
                checkpoint_outcome = checkpoint.get("outcome") if isinstance(checkpoint, dict) else None
                if isinstance(checkpoint_outcome, dict) and checkpoint_outcome.get("failure_class") == "POLICY_BLOCK":
                    outcome["failure_class"] = "POLICY_BLOCK"
                    outcome["reason"] = "acquisition_policy_block"
                    message = checkpoint_outcome.get("failure_message")
                    if message:
                        outcome["message"] = message

        acquisition = {
            **self.acquisition_binding,
            "route": "LIVE",
            "fallback_used": False,
            "boundary": POLICY_EXECUTION_BOUNDARY,
        }
        summary["acquisition"] = acquisition
        summary["retrieval_targets"] = [
            {**dict(target), "acquisition_route": "LIVE"} for target in summary.get("retrieval_targets", [])
        ]
        semantic = {
            key: summary[key]
            for key in (
                "run_id",
                "plan_id",
                "execution_status",
                "counts",
                "slo",
                "retrieval_targets",
                "outcomes",
                "per_host",
            )
        }
        semantic["acquisition"] = acquisition
        summary["semantic_summary_sha256"] = sha256_bytes(canonical_json_bytes(semantic))
        return write_run_summary(self.quarantine_root, summary)
