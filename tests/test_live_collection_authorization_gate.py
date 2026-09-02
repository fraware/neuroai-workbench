from __future__ import annotations

import json

import pytest

from neuroai_workbench.collector.authorization import (
    LIVE_AUTHORIZATION_ENV,
    LIVE_COLLECTION_ENV,
    CollectionAuthorizationError,
    build_authorization_packet,
)
from neuroai_workbench.shadow_refresh import live


class _SchedulerStub:
    last_kwargs = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs

    def run_plan(self, plan, *, registry_sha256, source_index):
        assert registry_sha256 == "a" * 64
        assert source_index == {}
        return {
            "run_id": "CRUN-test",
            "status": "COMPLETE",
            "counts": {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0},
            "outcomes": [],
        }


def _packet() -> dict:
    return build_authorization_packet(
        authorization_id="AUTH-TEST-001",
        authorized_by="test-operator",
        purpose="Controlled unit test of live authorization provenance.",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-02T10:00:00Z",
    )


def test_live_environment_flag_alone_is_insufficient(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.delenv(LIVE_AUTHORIZATION_ENV, raising=False)
    with pytest.raises(CollectionAuthorizationError, match="authorization packet"):
        live.run_live_cohort_collection(
            plan={"due": [], "manual": [], "not_due": []},
            registry={"sources": []},
            registry_sha256="a" * 64,
            quarantine_root=tmp_path,
        )


def test_tampered_authorization_packet_fails_closed(monkeypatch, tmp_path) -> None:
    packet = _packet()
    packet["purpose"] = "tampered after digest"
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, json.dumps(packet))
    with pytest.raises(CollectionAuthorizationError, match="digest mismatch"):
        live.run_live_cohort_collection(
            plan={"due": [], "manual": [], "not_due": []},
            registry={"sources": []},
            registry_sha256="a" * 64,
            quarantine_root=tmp_path,
        )


def test_valid_packet_reaches_scheduler_with_secure_defaults_and_provenance(monkeypatch, tmp_path) -> None:
    packet = _packet()
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, json.dumps(packet))
    monkeypatch.setattr(live, "CollectionScheduler", _SchedulerStub)

    result = live.run_live_cohort_collection(
        plan={"due": [], "manual": [], "not_due": []},
        registry={"sources": []},
        registry_sha256="a" * 64,
        quarantine_root=tmp_path,
    )

    kwargs = _SchedulerStub.last_kwargs
    assert kwargs is not None
    assert type(kwargs["transport"]).__name__ == "PinnedSocketHttpTransport"
    assert type(kwargs["dns_guard"]).__name__ == "DnsGuard"
    assert result["metadata"]["authorization"]["authorization_id"] == packet["authorization_id"]
    assert result["metadata"]["authorization"]["authorization_sha256"] == packet["authorization_sha256"]
    assert result["collector"]["default_transport"] == "PinnedSocketHttpTransport"
    assert result["collector"]["dns_guard"] == "DnsGuard"
    assert result["collector"]["handoff_enabled"] is False
