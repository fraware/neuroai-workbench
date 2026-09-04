from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neuroai_workbench.collector import policy_execution
from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    ONLINE_REQUIRED,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.policy_execution import PolicyBoundCollectionScheduler
from neuroai_workbench.collector.scheduler import CollectionScheduler, SchedulerConfig

CONFIG_HASH = "b" * 64
PROGRAMME_ID = "OBS-PROGRAMME"


@dataclass
class NeverTransport:
    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        del request, connect_timeout, read_timeout
        raise AssertionError("summary tests must not perform network I/O")


def _collector_config() -> CollectorConfig:
    return CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_attempts=1,
        requests_per_host_per_minute=100,
    )


def _policy() -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id="POLICY-2A-SUMMARY",
        programme_id=PROGRAMME_ID,
        approved_by="local-reviewer",
        source_rules=[
            {
                "source_id": "SRC-A",
                "execution_modes": [ONLINE_REQUIRED],
                "allowed_origins": ["https://a.example.org"],
                "fallback_policy": FALLBACK_FORBID,
            }
        ],
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
    )


def _policy_scheduler(tmp_path: Path) -> PolicyBoundCollectionScheduler:
    return PolicyBoundCollectionScheduler(
        acquisition_policy=_policy(),
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
        collector_config=_collector_config(),
        transport=NeverTransport(),
        quarantine_root=tmp_path / "policy",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )


def _summary_inputs() -> dict[str, Any]:
    target = {
        "retrieval_target_id": "TARGET-A",
        "normalized_url": "https://a.example.org/page",
        "source_ids": ["SRC-A"],
        "adapter_id": "html",
        "primary_source_id": "SRC-A",
    }
    checkpoint = {
        "state": "RESULT",
        "attempts": [{"host": "a.example.org"}],
        "outcome": {"record_id": "RESULT-A", "retryable": False},
    }
    return {
        "run_id": "RUN-SUMMARY-A",
        "plan": {"plan_id": "PLAN-SUMMARY-A", "as_of": "2026-09-04"},
        "manifest": {"manifest_sha256": "1" * 64, "binding_sha256": "2" * 64},
        "targets": [target],
        "checkpoints": {"TARGET-A": checkpoint},
        "pre_outcomes": [],
        "resumed_target_ids": set(),
    }


def test_policy_summary_preserves_base_accounting_semantics(tmp_path: Path) -> None:
    inputs = _summary_inputs()
    legacy = CollectionScheduler(
        collector_config=_collector_config(),
        transport=NeverTransport(),
        quarantine_root=tmp_path / "legacy",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )
    policy = _policy_scheduler(tmp_path)

    legacy_summary = legacy._summarize_run(**inputs)
    policy_summary = policy._summarize_run(**inputs)

    for key in ("execution_status", "counts", "slo", "outcomes", "per_host", "status", "boundary", "run_ledger_boundary"):
        assert policy_summary[key] == legacy_summary[key]
    assert [{key: value for key, value in target.items() if key != "acquisition_route"} for target in policy_summary["retrieval_targets"]] == legacy_summary["retrieval_targets"]
    assert policy_summary["retrieval_targets"][0]["acquisition_route"] == "LIVE"
    assert policy_summary["acquisition"]["policy_sha256"] == _policy()["policy_sha256"]


def test_policy_summary_has_one_authoritative_write(tmp_path: Path, monkeypatch: Any) -> None:
    scheduler = _policy_scheduler(tmp_path)
    writes: list[dict[str, Any]] = []

    def record_write(quarantine_root: Path, summary: dict[str, Any]) -> dict[str, Any]:
        del quarantine_root
        writes.append(dict(summary))
        return summary

    monkeypatch.setattr(policy_execution, "write_run_summary", record_write)
    summary = scheduler._summarize_run(**_summary_inputs())

    assert len(writes) == 1
    assert writes[0]["acquisition"] == summary["acquisition"]
    assert writes[0]["retrieval_targets"][0]["acquisition_route"] == "LIVE"
