from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    ONLINE_REQUIRED,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.policy_execution import (
    PolicyBoundCollectionScheduler,
    _PolicyBoundSchedulerConfig,
)
from neuroai_workbench.collector.scheduler import SchedulerConfig

CONFIG_HASH = "b" * 64
REGISTRY_HASH = "a" * 64
PROGRAMME_ID = "OBS-PROGRAMME"


@dataclass
class NoNetworkTransport:
    calls: list[HttpRequest] = field(default_factory=list)

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        del connect_timeout, read_timeout
        self.calls.append(request)
        raise AssertionError(f"network send was not expected: {request.url}")


def _policy(source_id: str = "SRC-A") -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id="POLICY-2A-DEFENSIVE",
        programme_id=PROGRAMME_ID,
        approved_by="local-reviewer",
        source_rules=[
            {
                "source_id": source_id,
                "execution_modes": [ONLINE_REQUIRED],
                "allowed_origins": ["https://a.example.org"],
                "fallback_policy": FALLBACK_FORBID,
            }
        ],
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
    )


def _source(url: str = "https://a.example.org/page") -> dict[str, Any]:
    return {
        "source_id": "SRC-A",
        "monitor_id": "MON-A",
        "source_class": "OFFICIAL_COMPANY_PAGE",
        "url": url,
    }


def _plan(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": "PLAN-2A-DEFENSIVE",
        "as_of": "2026-09-04",
        "due": [
            {
                "source_id": source["source_id"],
                "monitor_id": source["monitor_id"],
                "url": source["url"],
            }
        ],
        "manual": [],
        "not_due": [],
    }


def _scheduler(
    tmp_path: Path,
    transport: NoNetworkTransport,
    *,
    scheduler_config: SchedulerConfig | None = None,
) -> PolicyBoundCollectionScheduler:
    return PolicyBoundCollectionScheduler(
        acquisition_policy=_policy(),
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
        collector_config=CollectorConfig(
            collector_version="0.3.0.dev0-collector",
            configuration_hash=CONFIG_HASH,
            max_attempts=1,
            requests_per_host_per_minute=100,
        ),
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=scheduler_config or SchedulerConfig(max_workers=1, max_workers_per_host=1),
        sleeper=lambda _: None,
    )


@pytest.mark.parametrize(
    ("field_overrides", "message"),
    [
        ({"acquisition_policy_id": ""}, "acquisition_policy_id must be present"),
        ({"acquisition_policy_sha256": "not-a-digest"}, "lowercase SHA-256 digest"),
        ({"acquisition_execution_mode": "INVALID"}, "ONLINE_REQUIRED or ONLINE_PREFERRED"),
    ],
)
def test_bound_scheduler_configuration_rejects_invalid_binding_fields(
    field_overrides: dict[str, str],
    message: str,
) -> None:
    values = {
        "acquisition_policy_id": "POLICY-2A",
        "acquisition_policy_sha256": "c" * 64,
        "acquisition_programme_id": PROGRAMME_ID,
        "acquisition_execution_mode": ONLINE_REQUIRED,
    }
    values.update(field_overrides)
    with pytest.raises(ValueError, match=message):
        _PolicyBoundSchedulerConfig(**values)


def test_policy_wrapper_preserves_source_kill_switch(tmp_path: Path) -> None:
    source = _source()
    transport = NoNetworkTransport()
    config = SchedulerConfig(
        disabled_source_ids=frozenset({"SRC-A"}),
        max_workers=1,
        max_workers_per_host=1,
    )
    run = _scheduler(tmp_path, transport, scheduler_config=config).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )
    assert transport.calls == []
    assert run["outcomes"] == [{"source_id": "SRC-A", "status": "SKIPPED", "reason": "source_kill_switch"}]


def test_policy_wrapper_preserves_unknown_source_handling(tmp_path: Path) -> None:
    source = _source()
    transport = NoNetworkTransport()
    run = _scheduler(tmp_path, transport).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={},
    )
    assert transport.calls == []
    assert run["outcomes"] == [{"source_id": "SRC-A", "status": "SKIPPED", "reason": "unknown_source"}]


def test_policy_wrapper_preserves_non_http_rejection(tmp_path: Path) -> None:
    source = _source("file:///tmp/source.html")
    transport = NoNetworkTransport()
    run = _scheduler(tmp_path, transport).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )
    assert transport.calls == []
    outcome = run["outcomes"][0]
    assert outcome["status"] == "FAILURE"
    assert outcome["failure_class"] == "POLICY_BLOCK"
    assert "Non-HTTP URL" in outcome["message"]


def test_policy_wrapper_preserves_public_url_rejection(tmp_path: Path) -> None:
    source = _source("http://127.0.0.1/private")
    transport = NoNetworkTransport()
    run = _scheduler(tmp_path, transport).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )
    assert transport.calls == []
    outcome = run["outcomes"][0]
    assert outcome["status"] == "FAILURE"
    assert outcome["failure_class"] == "POLICY_BLOCK"
    assert outcome["message"]


def test_policy_wrapper_preserves_adapter_kill_switch(tmp_path: Path) -> None:
    source = _source()
    transport = NoNetworkTransport()
    config = SchedulerConfig(
        disabled_adapter_ids=frozenset({"html"}),
        max_workers=1,
        max_workers_per_host=1,
    )
    run = _scheduler(tmp_path, transport, scheduler_config=config).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )
    assert transport.calls == []
    assert run["outcomes"] == [
        {
            "source_id": "SRC-A",
            "status": "SKIPPED",
            "reason": "adapter_kill_switch",
            "adapter_id": "html",
        }
    ]
