from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    FALLBACK_PRIOR_CAPTURE,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.policy_execution import PolicyBoundCollectionScheduler
from neuroai_workbench.collector.prior_capture_replay import (
    PolicyBoundFallbackCollectionScheduler,
    ReplayOnlyCollectionScheduler,
)
from neuroai_workbench.collector.run_ledger import load_target_checkpoint, write_run_summary
from neuroai_workbench.collector.runtime_proof import (
    RUNTIME_PROOF_BOUNDARY,
    RuntimeProofError,
    build_runtime_proof,
    project_clinicaltrials_capture,
    verify_runtime_proof,
    write_runtime_proof,
)
from neuroai_workbench.collector.scheduler import SchedulerConfig
from neuroai_workbench.collector.url_normalize import RetrievalTargetGroup
from neuroai_workbench.util import sha256_bytes

GLOBAL_IP = "93.184.216.34"
CONFIG_HASH = "b" * 64
REGISTRY_HASH = "a" * 64
PROGRAMME_ID = "P3-CTGOV"
SOURCE_ID = "SRC-P3-CTGOV"
MONITOR_ID = "MON-P3-CTGOV"
NCT_ID = "NCT00000001"
URL = f"https://clinicaltrials.gov/api/v2/studies/{NCT_ID}"


def _study_payload(nct_id: str = NCT_ID, title: str = "Controlled Phase 3 fixture") -> dict[str, Any]:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "briefTitle": title},
            "statusModule": {
                "overallStatus": "RECRUITING",
                "lastUpdatePostDateStruct": {"date": "2026-09-01"},
                "primaryCompletionDateStruct": {"date": "2027-01"},
                "enrollmentInfo": {"count": 20},
            },
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE1"]},
        }
    }


@dataclass
class RecordingTransport:
    body: bytes
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
        return 200, {"content-type": "application/json"}, self.body


@dataclass
class FailingTransport:
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
        raise OSError("injected network failure")


@dataclass
class RecordingResolver:
    hosts: list[str] = field(default_factory=list)

    def __call__(self, host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del port, args, kwargs
        self.hosts.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]


def _source(
    *,
    source_id: str = SOURCE_ID,
    monitor_id: str = MONITOR_ID,
    url: str = URL,
    source_class: str = "OFFICIAL_TRIAL_REGISTRY",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "monitor_id": monitor_id,
        "source_class": source_class,
        "url": url,
    }


def _plan(source: dict[str, Any], *, plan_id: str = "PLAN-P3", as_of: str = "2026-09-05") -> dict[str, Any]:
    return {
        "plan_id": plan_id,
        "as_of": as_of,
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


def _policy(
    *,
    source_id: str = SOURCE_ID,
    origin: str = "https://clinicaltrials.gov",
    modes: tuple[str, ...] = (ONLINE_REQUIRED, REPLAY_ONLY),
    fallback: str = FALLBACK_FORBID,
) -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id="POLICY-P3-CTGOV",
        programme_id=PROGRAMME_ID,
        approved_by="controlled-phase3-test",
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
        source_rules=[
            {
                "source_id": source_id,
                "execution_modes": list(modes),
                "allowed_origins": [origin] if any(mode != REPLAY_ONLY for mode in modes) else [],
                "fallback_policy": fallback,
            }
        ],
    )


def _config(*, max_attempts: int = 1) -> CollectorConfig:
    return CollectorConfig(
        collector_version="0.3.0.dev0-phase3-test",
        configuration_hash=CONFIG_HASH,
        max_attempts=max_attempts,
        retry_initial_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
        requests_per_host_per_minute=10_000,
    )


def _live_scheduler(
    tmp_path: Path,
    transport: Any,
    policy: dict[str, Any],
) -> PolicyBoundCollectionScheduler:
    return PolicyBoundCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
        collector_config=_config(),
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
        dns_guard=DnsGuard(getaddrinfo=RecordingResolver()),
        sleeper=lambda _seconds: None,
    )


def _replay_scheduler(tmp_path: Path, policy: dict[str, Any]) -> ReplayOnlyCollectionScheduler:
    return ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        collector_config=_config(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )


def _run_live_replay_pair(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    source = _source()
    policy = _policy()
    transport = RecordingTransport(json.dumps(_study_payload()).encode("utf-8"))
    live = _live_scheduler(tmp_path, transport, policy).run_plan(
        _plan(source),
        registry_sha256=REGISTRY_HASH,
        source_index={SOURCE_ID: source},
    )
    assert len(transport.calls) == 1
    assert live["execution_status"] == "COMPLETE"
    result_id = str(live["outcomes"][0]["record_id"])
    replay = _replay_scheduler(tmp_path, policy).run_plan(
        _plan(source, plan_id="PLAN-P3-REPLAY"),
        registry_sha256=REGISTRY_HASH,
        source_index={SOURCE_ID: source},
    )
    assert replay["counts"]["collection_attempts"] == 0
    assert replay["outcomes"][0]["record_id"] == result_id
    return policy, live, replay, result_id


def _build_pair_proof(tmp_path: Path) -> dict[str, Any]:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    return build_runtime_proof(
        tmp_path / "quarantine",
        live_run_id=str(live["run_id"]),
        replay_run_id=str(replay["run_id"]),
        programme_id=PROGRAMME_ID,
        source_id=SOURCE_ID,
        policy_sha256=str(policy["policy_sha256"]),
        result_id=result_id,
        created_at="2026-09-05T00:00:00Z",
    )


def _seed_capture(
    quarantine_root: Path,
    *,
    result_id: str,
    body: bytes,
    source_id: str = SOURCE_ID,
    url: str = URL,
    retrieved_at: str = "2026-09-04T00:00:00Z",
    quarantine_path: str | None = None,
) -> dict[str, Any]:
    digest = sha256_bytes(body)
    relative = quarantine_path or f"incoming/{source_id}/{digest[:12]}/capture.json"
    if ".." not in relative:
        body_path = quarantine_root / relative
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(body)
    record = {
        "result_id": result_id,
        "source_id": source_id,
        "monitor_id": f"MON-{source_id}",
        "requested_url": url,
        "retrieved_at": retrieved_at,
        "sha256": digest,
        "quarantine_path": relative,
        "size_bytes": len(body),
        "media_type": "application/json",
        "original_filename": "capture.json",
    }
    results = quarantine_root / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{result_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_build_and_verify_exact_live_replay_proof(tmp_path: Path) -> None:
    proof = _build_pair_proof(tmp_path)

    verified = verify_runtime_proof(tmp_path / "quarantine", proof)

    assert verified == proof
    assert proof["boundary"] == RUNTIME_PROOF_BOUNDARY
    assert proof["semantic"]["projection"]["live_replay_equivalent"] is True
    assert proof["semantic"]["claims"]["replay_zero_network_verified"] is True
    assert proof["semantic"]["claims"]["canonical_s2_mutation_performed"] is False
    assert proof["semantic"]["replay"]["collection_attempts"] == 0
    assert proof["semantic"]["live"]["collection_attempts"] == 1


def test_recurrence_digest_excludes_creation_timestamp(tmp_path: Path) -> None:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    kwargs = {
        "live_run_id": str(live["run_id"]),
        "replay_run_id": str(replay["run_id"]),
        "programme_id": PROGRAMME_ID,
        "source_id": SOURCE_ID,
        "policy_sha256": str(policy["policy_sha256"]),
        "result_id": result_id,
    }
    first = build_runtime_proof(tmp_path / "quarantine", created_at="2026-09-05T00:00:00Z", **kwargs)
    second = build_runtime_proof(tmp_path / "quarantine", created_at="2026-09-05T01:00:00Z", **kwargs)

    assert first["proof_id"] == second["proof_id"]
    assert first["proof_semantic_sha256"] == second["proof_semantic_sha256"]
    assert first["semantic"] == second["semantic"]
    assert first["created_at"] != second["created_at"]


def test_build_and_verify_do_not_mutate_controlled_quarantine(tmp_path: Path) -> None:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    root = tmp_path / "quarantine"
    before = _tree_snapshot(root)

    proof = build_runtime_proof(
        root,
        live_run_id=str(live["run_id"]),
        replay_run_id=str(replay["run_id"]),
        programme_id=PROGRAMME_ID,
        source_id=SOURCE_ID,
        policy_sha256=str(policy["policy_sha256"]),
        result_id=result_id,
    )
    verify_runtime_proof(root, proof)

    assert _tree_snapshot(root) == before
    output = tmp_path / "proof-output" / "phase3-proof.json"
    write_runtime_proof(output, proof)
    assert output.is_file()
    assert _tree_snapshot(root) == before


def test_project_capture_rejects_invalid_utf8_json_and_non_object(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-P3-UTF8", body=b"\xff")
    with pytest.raises(RuntimeProofError, match="UTF-8"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-UTF8")

    _seed_capture(root, result_id="CRES-P3-JSON", body=b"{")
    with pytest.raises(RuntimeProofError, match="valid JSON"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-JSON")

    _seed_capture(root, result_id="CRES-P3-LIST", body=b"[]")
    with pytest.raises(RuntimeProofError, match="must decode to an object"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-LIST")


def test_project_capture_rejects_structurally_invalid_study_and_source_substitution(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-P3-NONSTUDY", body=b"{}")
    with pytest.raises(RuntimeProofError, match="cannot be normalized"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-NONSTUDY")

    body = json.dumps(_study_payload()).encode("utf-8")
    _seed_capture(root, result_id="CRES-P3-SOURCE", body=body)
    with pytest.raises(RuntimeProofError, match="source_id"):
        project_clinicaltrials_capture(
            root,
            result_id="CRES-P3-SOURCE",
            expected_source_id="SRC-SUBSTITUTED",
        )


def test_project_capture_rejects_missing_tampered_and_escaping_bytes(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    body = json.dumps(_study_payload()).encode("utf-8")
    record = _seed_capture(root, result_id="CRES-P3-TAMPER", body=body)
    (root / record["quarantine_path"]).write_bytes(body + b" ")
    with pytest.raises(RuntimeProofError, match="integrity validation"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-TAMPER")

    record = _seed_capture(root, result_id="CRES-P3-MISSING", body=body)
    (root / record["quarantine_path"]).unlink()
    with pytest.raises(RuntimeProofError, match="integrity validation"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-MISSING")

    _seed_capture(
        root,
        result_id="CRES-P3-ESCAPE",
        body=body,
        quarantine_path="../outside/capture.json",
    )
    with pytest.raises(RuntimeProofError, match="integrity validation"):
        project_clinicaltrials_capture(root, result_id="CRES-P3-ESCAPE")


def test_runtime_proof_rejects_semantic_and_top_level_tampering(tmp_path: Path) -> None:
    proof = _build_pair_proof(tmp_path)
    tampered = json.loads(json.dumps(proof))
    tampered["semantic"]["capture"]["size_bytes"] += 1
    with pytest.raises(RuntimeProofError, match="semantic digest mismatch"):
        verify_runtime_proof(tmp_path / "quarantine", tampered)

    unknown = dict(proof)
    unknown["unexpected"] = True
    with pytest.raises(RuntimeProofError, match="fields mismatch"):
        verify_runtime_proof(tmp_path / "quarantine", unknown)


def test_runtime_proof_rejects_policy_and_source_substitution(tmp_path: Path) -> None:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    with pytest.raises(RuntimeProofError, match="policy"):
        build_runtime_proof(
            tmp_path / "quarantine",
            live_run_id=str(live["run_id"]),
            replay_run_id=str(replay["run_id"]),
            programme_id=PROGRAMME_ID,
            source_id=SOURCE_ID,
            policy_sha256="0" * 64,
            result_id=result_id,
        )
    with pytest.raises(RuntimeProofError, match="source"):
        build_runtime_proof(
            tmp_path / "quarantine",
            live_run_id=str(live["run_id"]),
            replay_run_id=str(replay["run_id"]),
            programme_id=PROGRAMME_ID,
            source_id="SRC-SUBSTITUTED",
            policy_sha256=str(policy["policy_sha256"]),
            result_id=result_id,
        )


def test_runtime_proof_rejects_manifest_tampering(tmp_path: Path) -> None:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    root = tmp_path / "quarantine"
    manifest_path = root / "run-ledgers" / str(live["run_id"]) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["binding"]["plan_id"] = "SUBSTITUTED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeProofError, match="manifest validation failed"):
        build_runtime_proof(
            root,
            live_run_id=str(live["run_id"]),
            replay_run_id=str(replay["run_id"]),
            programme_id=PROGRAMME_ID,
            source_id=SOURCE_ID,
            policy_sha256=str(policy["policy_sha256"]),
            result_id=result_id,
        )


def test_runtime_proof_rejects_rehashed_summary_with_stale_semantic_digest(tmp_path: Path) -> None:
    policy, live, replay, result_id = _run_live_replay_pair(tmp_path)
    root = tmp_path / "quarantine"
    summary_path = root / "run-ledgers" / str(live["run_id"]) / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["retrieval_targets"][0]["acquisition_route"] = "REPLAY"
    write_run_summary(root, summary)

    with pytest.raises(RuntimeProofError, match="semantic digest"):
        build_runtime_proof(
            root,
            live_run_id=str(live["run_id"]),
            replay_run_id=str(replay["run_id"]),
            programme_id=PROGRAMME_ID,
            source_id=SOURCE_ID,
            policy_sha256=str(policy["policy_sha256"]),
            result_id=result_id,
        )


def test_live_crash_after_durable_result_resumes_without_duplicate_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    policy = _policy()
    transport = RecordingTransport(json.dumps(_study_payload()).encode("utf-8"))
    scheduler = _live_scheduler(tmp_path, transport, policy)
    plan = _plan(source, plan_id="PLAN-P3-CRASH")
    original = scheduler._apply_attempt_outcome  # noqa: SLF001
    injected = {"raised": False}

    def interrupt_once(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("recovered") is False and not injected["raised"]:
            injected["raised"] = True
            raise RuntimeError("injected after durable result persistence")
        return original(*args, **kwargs)

    monkeypatch.setattr(scheduler, "_apply_attempt_outcome", interrupt_once)
    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index={SOURCE_ID: source})
    assert first["status"] == "INCOMPLETE"
    assert len(transport.calls) == 1

    resumed = _live_scheduler(tmp_path, transport, policy).run_plan(
        plan,
        registry_sha256=REGISTRY_HASH,
        source_index={SOURCE_ID: source},
    )
    assert resumed["execution_status"] == "COMPLETE"
    assert resumed["counts"]["recovered_attempts"] == 1
    assert len(transport.calls) == 1


def test_fallback_pending_resume_uses_prebound_capture_after_newer_capture_arrives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "quarantine"
    fallback_url = "https://fallback.example.org/data"
    source = _source(
        source_id="SRC-P3-FALLBACK",
        monitor_id="MON-P3-FALLBACK",
        url=fallback_url,
        source_class="OFFICIAL_COMPANY_PAGE",
    )
    old_body = b"old capture"
    _seed_capture(
        root,
        result_id="CRES-P3-OLD",
        body=old_body,
        source_id="SRC-P3-FALLBACK",
        url=fallback_url,
        retrieved_at="2026-09-03T00:00:00Z",
    )
    policy = _policy(
        source_id="SRC-P3-FALLBACK",
        origin="https://fallback.example.org",
        modes=(ONLINE_PREFERRED,),
        fallback=FALLBACK_PRIOR_CAPTURE,
    )
    transport = FailingTransport()
    scheduler = PolicyBoundFallbackCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_PREFERRED,
        collector_config=_config(),
        transport=transport,
        quarantine_root=root,
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
        dns_guard=DnsGuard(getaddrinfo=RecordingResolver()),
        sleeper=lambda _seconds: None,
    )

    def interrupt_pending(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise RuntimeError("injected at fallback-pending boundary")

    monkeypatch.setattr(scheduler, "_apply_bound_fallback", interrupt_pending)
    plan = _plan(source, plan_id="PLAN-P3-FALLBACK", as_of="2026-09-05")
    with pytest.raises(RuntimeError, match="fallback-pending"):
        scheduler.run_plan(
            plan,
            registry_sha256=REGISTRY_HASH,
            source_index={"SRC-P3-FALLBACK": source},
        )
    assert len(transport.calls) == 1

    run_dirs = sorted((root / "run-ledgers").iterdir())
    assert len(run_dirs) == 1
    run_id = run_dirs[0].name
    manifest = json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))
    target = manifest["binding"]["retrieval_targets"][0]
    checkpoint = load_target_checkpoint(root, run_id=run_id, target=target)
    assert checkpoint["fallback_pending"]["result_id"] == "CRES-P3-OLD"

    _seed_capture(
        root,
        result_id="CRES-P3-NEW",
        body=b"new capture",
        source_id="SRC-P3-FALLBACK",
        url=fallback_url,
        retrieved_at="2026-09-04T00:00:00Z",
    )
    resumed_transport = FailingTransport()
    resumed = PolicyBoundFallbackCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_PREFERRED,
        collector_config=_config(),
        transport=resumed_transport,
        quarantine_root=root,
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
        dns_guard=DnsGuard(getaddrinfo=RecordingResolver()),
        sleeper=lambda _seconds: None,
    )
    resumed._fallback_as_of = "2026-09-05"  # noqa: SLF001
    group = RetrievalTargetGroup(
        retrieval_target_id=str(target["retrieval_target_id"]),
        normalized_url=str(target["normalized_url"]),
        requested_url=str(target["requested_url"]),
        source_ids=("SRC-P3-FALLBACK",),
        primary_source_id="SRC-P3-FALLBACK",
        primary_monitor_id="MON-P3-FALLBACK",
        primary_item={
            "source_id": "SRC-P3-FALLBACK",
            "monitor_id": "MON-P3-FALLBACK",
            "url": fallback_url,
        },
    )
    resolved = resumed._execute_target(  # noqa: SLF001
        run_id=run_id,
        group=group,
        checkpoint=checkpoint,
        adapter=None,
        source_record=source,
        registry_sha256=REGISTRY_HASH,
        persisted_records={},
    )

    assert resumed_transport.calls == []
    assert resolved["state"] == "RESULT"
    assert resolved["fallback"]["result_id"] == "CRES-P3-OLD"
