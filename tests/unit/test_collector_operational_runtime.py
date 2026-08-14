from __future__ import annotations

import json
import socket
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from neuroai_workbench.collector import CollectionScheduler, CollectorConfig, SchedulerConfig, StaticCredentialProvider
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.rate_limit import RateLimiter

CONFIG_HASH = "b" * 64
REGISTRY_HASH = "a" * 64
GLOBAL_IP = "93.184.216.34"


def global_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    if host.endswith(".example.org"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]
    raise socket.gaierror("unknown host")


@dataclass
class ConcurrentTransport:
    delay_seconds: float = 0.0
    transient_failures: dict[str, int] = field(default_factory=dict)
    permanent_statuses: dict[str, int] = field(default_factory=dict)
    redirects: dict[str, str] = field(default_factory=dict)
    internal_error_urls: set[str] = field(default_factory=set)
    calls: list[HttpRequest] = field(default_factory=list)
    call_counts: Counter[str] = field(default_factory=Counter)
    max_active: int = 0
    max_active_by_host: dict[str, int] = field(default_factory=dict)
    _active: int = 0
    _active_by_host: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        del connect_timeout, read_timeout
        host = urlparse(request.url).hostname or "unknown"
        with self._lock:
            self.calls.append(request)
            self.call_counts[request.url] += 1
            call_number = self.call_counts[request.url]
            self._active += 1
            self._active_by_host[host] += 1
            self.max_active = max(self.max_active, self._active)
            self.max_active_by_host[host] = max(
                self.max_active_by_host.get(host, 0),
                self._active_by_host[host],
            )
        try:
            if self.delay_seconds:
                time.sleep(self.delay_seconds)
            if request.url in self.redirects:
                return 302, {"Location": self.redirects[request.url]}, b""
            if request.url in self.internal_error_urls:
                raise RuntimeError("injected internal transport defect")
            if call_number <= self.transient_failures.get(request.url, 0):
                raise TimeoutError("injected transient timeout")
            if request.url in self.permanent_statuses:
                return self.permanent_statuses[request.url], {"Content-Type": "application/json"}, b"{}"
            return 200, {"Content-Type": "application/json"}, b'{"ok":true}'
        finally:
            with self._lock:
                self._active -= 1
                self._active_by_host[host] -= 1


def _source(source_id: str, url: str, *, source_class: str = "PUBLIC_JSON_API") -> dict[str, Any]:
    return {
        "source_id": source_id,
        "monitor_id": f"MON-{source_id}",
        "source_class": source_class,
        "url": url,
    }


def _plan(records: list[dict[str, Any]], *, plan_id: str = "PLAN-OPERATIONAL") -> dict[str, Any]:
    return {
        "plan_id": plan_id,
        "as_of": "2026-08-14",
        "due": [
            {
                "source_id": record["source_id"],
                "monitor_id": record["monitor_id"],
                "url": record["url"],
            }
            for record in records
        ],
        "manual": [],
        "not_due": [],
    }


def _scheduler(
    tmp_path: Path,
    transport: ConcurrentTransport,
    *,
    max_workers: int = 8,
    per_host: int = 2,
    max_attempts: int = 3,
    credential_provider: StaticCredentialProvider | None = None,
) -> CollectionScheduler:
    return CollectionScheduler(
        collector_config=CollectorConfig(
            collector_version="0.3.0.dev0-operational-test",
            configuration_hash=CONFIG_HASH,
            requests_per_host_per_minute=10_000,
            max_attempts=max_attempts,
            retry_initial_delay_seconds=0.0,
            retry_max_delay_seconds=0.0,
        ),
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(
            max_workers=max_workers,
            max_workers_per_host=per_host,
        ),
        credential_provider=credential_provider,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        sleeper=lambda _seconds: None,
    )


def _index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record["source_id"]): record for record in records}


def test_scheduler_executes_targets_concurrently_with_per_host_bound(tmp_path: Path) -> None:
    records = [_source(f"SRC-{index:04d}", f"https://host{index % 4}.example.org/item/{index}") for index in range(32)]
    transport = ConcurrentTransport(delay_seconds=0.02)
    scheduler = _scheduler(tmp_path, transport, max_workers=8, per_host=2)

    run = scheduler.run_plan(_plan(records), registry_sha256=REGISTRY_HASH, source_index=_index(records))

    assert run["status"] == "COMPLETED"
    assert run["execution_status"] == "COMPLETE"
    assert run["slo"]["source_accountability_coverage"] == 1.0
    assert run["slo"]["target_execution_coverage"] == 1.0
    assert transport.max_active > 1
    assert transport.max_active <= 8
    assert transport.max_active_by_host
    assert max(transport.max_active_by_host.values()) <= 2


def test_redirect_convergence_respects_actual_destination_host_limit(tmp_path: Path) -> None:
    records = []
    redirects = {}
    for index in range(12):
        initial = f"https://entry{index}.example.org/start/{index}"
        final = f"https://shared.example.org/final/{index}"
        records.append(_source(f"SRC-REDIRECT-{index:02d}", initial))
        redirects[initial] = final
    transport = ConcurrentTransport(delay_seconds=0.02, redirects=redirects)
    scheduler = _scheduler(tmp_path, transport, max_workers=8, per_host=2)

    run = scheduler.run_plan(_plan(records), registry_sha256=REGISTRY_HASH, source_index=_index(records))

    assert run["execution_status"] == "COMPLETE"
    assert transport.max_active > 2
    assert transport.max_active_by_host["shared.example.org"] <= 2
    assert sum(transport.call_counts.values()) == 24


def test_retry_policy_retries_transient_timeout_and_not_permanent_404(tmp_path: Path) -> None:
    transient_url = "https://retry.example.org/transient"
    permanent_url = "https://retry.example.org/not-found"
    records = [_source("SRC-TRANSIENT", transient_url), _source("SRC-PERMANENT", permanent_url)]
    transport = ConcurrentTransport(
        transient_failures={transient_url: 2},
        permanent_statuses={permanent_url: 404},
    )
    scheduler = _scheduler(tmp_path, transport, max_workers=2, per_host=2, max_attempts=3)

    run = scheduler.run_plan(_plan(records), registry_sha256=REGISTRY_HASH, source_index=_index(records))
    outcomes = {item["source_id"]: item for item in run["outcomes"]}

    assert transport.call_counts[transient_url] == 3
    assert transport.call_counts[permanent_url] == 1
    assert outcomes["SRC-TRANSIENT"]["status"] == "RESULT"
    assert outcomes["SRC-TRANSIENT"]["attempt_count"] == 3
    assert outcomes["SRC-PERMANENT"]["status"] == "FAILURE"
    assert outcomes["SRC-PERMANENT"]["attempt_count"] == 1
    assert run["counts"]["retries"] == 2
    assert run["execution_status"] == "COMPLETE_WITH_SOURCE_FAILURES"


def test_resume_skips_terminal_targets_and_retries_only_internal_incomplete_work(tmp_path: Path) -> None:
    stable_url = "https://resume-a.example.org/stable"
    unstable_url = "https://resume-b.example.org/unstable"
    records = [_source("SRC-STABLE", stable_url), _source("SRC-UNSTABLE", unstable_url)]
    transport = ConcurrentTransport(internal_error_urls={unstable_url})
    scheduler = _scheduler(tmp_path, transport, max_workers=2, per_host=1)
    plan = _plan(records, plan_id="PLAN-RESUME")

    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert first["status"] == "INCOMPLETE"
    assert first["execution_status"] == "INCOMPLETE_INTERNAL_ERROR"
    assert transport.call_counts[stable_url] == 1
    assert transport.call_counts[unstable_url] == 1

    transport.internal_error_urls.clear()
    second = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert second["status"] == "COMPLETED"
    assert second["execution_status"] == "COMPLETE"
    assert transport.call_counts[stable_url] == 1
    assert transport.call_counts[unstable_url] == 2
    assert second["counts"]["resumed_targets"] == 1


def test_resume_recovers_durable_result_after_post_persist_checkpoint_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://recovery.example.org/item"
    records = [_source("SRC-RECOVERY", url)]
    transport = ConcurrentTransport()
    scheduler = _scheduler(tmp_path, transport, max_workers=1, per_host=1)
    plan = _plan(records, plan_id="PLAN-POST-PERSIST")
    original = scheduler._apply_attempt_outcome
    injected = {"raised": False}

    def explode_after_persist(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("recovered") is False and not injected["raised"]:
            injected["raised"] = True
            raise RuntimeError("injected interruption after durable result")
        return original(*args, **kwargs)

    monkeypatch.setattr(scheduler, "_apply_attempt_outcome", explode_after_persist)
    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert first["status"] == "INCOMPLETE"
    assert transport.call_counts[url] == 1

    resumed = _scheduler(tmp_path, transport, max_workers=1, per_host=1)
    second = resumed.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert second["status"] == "COMPLETED"
    assert transport.call_counts[url] == 1
    assert second["counts"]["recovered_attempts"] == 1


def test_completed_run_is_idempotent_and_performs_zero_duplicate_network_work(tmp_path: Path) -> None:
    url = "https://idempotent.example.org/item"
    records = [_source("SRC-IDEMPOTENT", url)]
    transport = ConcurrentTransport()
    scheduler = _scheduler(tmp_path, transport, max_workers=1, per_host=1)
    plan = _plan(records, plan_id="PLAN-IDEMPOTENT")

    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    second = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))

    assert first["run_id"] == second["run_id"]
    assert first["summary_sha256"] == second["summary_sha256"]
    assert transport.call_counts[url] == 1


def test_manifest_tampering_fails_closed_before_new_network_work(tmp_path: Path) -> None:
    url = "https://tamper.example.org/item"
    records = [_source("SRC-TAMPER", url)]
    transport = ConcurrentTransport()
    scheduler = _scheduler(tmp_path, transport, max_workers=1, per_host=1)
    plan = _plan(records, plan_id="PLAN-TAMPER")
    run = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    manifest = tmp_path / "quarantine" / "run-ledgers" / run["run_id"] / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["binding"]["plan_id"] = "SUBSTITUTED"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest"):
        scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert transport.call_counts[url] == 1


def test_authenticated_and_public_requests_do_not_share_mutated_transport(tmp_path: Path) -> None:
    auth_a = "https://auth-a.example.org/report"
    auth_b = "https://auth-b.example.org/report"
    public = "https://public.example.org/data"
    records = [
        _source("SRC-AUTH-A", auth_a, source_class="CONTROLLED_AUTHENTICATED_DOWNLOAD"),
        _source("SRC-AUTH-B", auth_b, source_class="CONTROLLED_AUTHENTICATED_DOWNLOAD"),
        _source("SRC-PUBLIC", public),
    ]
    transport = ConcurrentTransport(delay_seconds=0.02)
    credentials = StaticCredentialProvider(
        {
            "SRC-AUTH-A": "Bearer token-a",
            "SRC-AUTH-B": "Bearer token-b",
        }
    )
    scheduler = _scheduler(
        tmp_path,
        transport,
        max_workers=3,
        per_host=1,
        credential_provider=credentials,
    )

    run = scheduler.run_plan(_plan(records), registry_sha256=REGISTRY_HASH, source_index=_index(records))
    assert run["status"] == "COMPLETED"
    headers_by_url = {request.url: request.headers for request in transport.calls}
    assert headers_by_url[auth_a]["Authorization"] == "Bearer token-a"
    assert headers_by_url[auth_b]["Authorization"] == "Bearer token-b"
    assert "Authorization" not in headers_by_url[public]


def test_248_source_due_cycle_is_fully_accountable_deduplicated_and_fast(tmp_path: Path) -> None:
    records: list[dict[str, Any]] = []
    unique_targets = 62
    for index in range(248):
        target = index % unique_targets
        records.append(
            _source(
                f"SRC-{index:04d}",
                f"https://bulk{target % 16}.example.org/resource/{target}",
            )
        )
    transport = ConcurrentTransport()
    scheduler = _scheduler(tmp_path, transport, max_workers=16, per_host=2)
    started = time.perf_counter()

    run = scheduler.run_plan(
        _plan(records, plan_id="PLAN-248-SOURCE-STRESS"),
        registry_sha256=REGISTRY_HASH,
        source_index=_index(records),
    )
    elapsed = time.perf_counter() - started

    assert run["status"] == "COMPLETED"
    assert run["execution_status"] == "COMPLETE"
    assert run["counts"]["total"] == 248
    assert run["counts"]["retrieval_target_groups"] == unique_targets
    assert run["counts"]["unique_retrievals"] == unique_targets
    assert run["counts"]["collection_attempts"] == unique_targets
    assert run["counts"]["coalesced_source_count"] == 248
    assert len(transport.calls) == unique_targets
    assert run["slo"]["source_accountability_coverage"] == 1.0
    assert run["slo"]["target_execution_coverage"] == 1.0
    assert run["slo"]["source_accountability_complete"] is True
    assert run["slo"]["target_execution_complete"] is True
    assert elapsed < 15.0


def test_thread_safe_rate_limiter_never_overadmits_concurrent_immediate_checks() -> None:
    limiter = RateLimiter(10)
    successes = 0
    failures = 0
    lock = threading.Lock()

    def check() -> None:
        nonlocal successes, failures
        try:
            limiter.check("https://rate.example.org/item", now=100.0)
        except ValueError:
            with lock:
                failures += 1
        else:
            with lock:
                successes += 1

    threads = [threading.Thread(target=check) for _ in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert successes == 10
    assert failures == 90


def test_output_order_is_deterministic_despite_concurrent_completion(tmp_path: Path) -> None:
    records = [
        _source("SRC-Z", "https://order-z.example.org/item"),
        _source("SRC-A", "https://order-a.example.org/item"),
        _source("SRC-M", "https://order-m.example.org/item"),
    ]
    transport = ConcurrentTransport(delay_seconds=0.01)
    scheduler = _scheduler(tmp_path, transport, max_workers=3, per_host=1)

    run = scheduler.run_plan(
        _plan(records, plan_id="PLAN-ORDER"), registry_sha256=REGISTRY_HASH, source_index=_index(records)
    )

    assert [item["source_id"] for item in run["outcomes"]] == ["SRC-A", "SRC-M", "SRC-Z"]
    target_ids = [item["retrieval_target_id"] for item in run["retrieval_targets"]]
    assert target_ids == sorted(target_ids)
