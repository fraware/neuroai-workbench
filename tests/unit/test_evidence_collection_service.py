from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector.authorization import (
    CollectionAuthorizationError,
    build_authorization_packet,
)
from neuroai_workbench.collector.collection_service import EvidenceCollectionService, QuarantineService
from neuroai_workbench.collector.handoff import (
    HandoffBlockedError,
    load_quarantine_record,
    prepare_monitoring_handoff,
)
from neuroai_workbench.collector.http_client import TransportResponse
from neuroai_workbench.collector.pinned_transport import PinnedSocketHttpTransport
from neuroai_workbench.collector.scan import FailClosedContentSafetyScanner
from tests.unit.test_collector_http import FakeTransport, _collector
from tests.unit.test_collector_schemas import valid_collection_request


def test_authorization_packet_required_and_env_is_not_sufficient(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NEUROAI_LIVE_COLLECTION", raising=False)
    collector = _collector(
        tmp_path, FakeTransport(responses={"https://example.org/source": (200, {"Content-Type": "text/html"}, b"ok")})
    )
    service = EvidenceCollectionService(collector)
    packet = build_authorization_packet(
        authorization_id="AUTH-1",
        authorized_by="local-operator",
        purpose="unit-test",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
    )
    with pytest.raises(CollectionAuthorizationError, match="authorization packet"):
        service.collect(packet, valid_collection_request())
    monkeypatch.setenv("NEUROAI_LIVE_COLLECTION", "1")
    outcome = service.collect(packet, valid_collection_request())
    assert outcome.kind == "result"
    assert outcome.record["evidence_state"] == "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED"
    scan_path = tmp_path / "quarantine" / "scans" / f"{outcome.quarantine_record['quarantine_id']}.json"
    assert json.loads(scan_path.read_text(encoding="utf-8"))["state"] == "NOT_EXECUTED_FAIL_CLOSED"


def test_offline_authorization_does_not_require_live_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NEUROAI_LIVE_COLLECTION", raising=False)
    collector = _collector(
        tmp_path, FakeTransport(responses={"https://example.org/source": (200, {"Content-Type": "text/html"}, b"ok")})
    )
    packet = build_authorization_packet(
        authorization_id="AUTH-OFF",
        authorized_by="local-operator",
        purpose="fixture",
        network_mode="OFFLINE",
        network_permitted=False,
    )
    outcome = EvidenceCollectionService(collector).collect(packet, valid_collection_request())
    assert outcome.kind == "result"


def test_fail_closed_scanner_never_reports_clean() -> None:
    result = FailClosedContentSafetyScanner().scan(sha256="a" * 64, media_type="text/html", size_bytes=2)
    assert result.state != "CLEAN_NOT_ADJUDICATION"
    assert "fail-closed" in result.detail.lower() or result.state.endswith("FAIL_CLOSED")


def test_quarantine_approval_is_append_only_successor(tmp_path: Path) -> None:
    collector = _collector(
        tmp_path, FakeTransport(responses={"https://example.org/source": (200, {"Content-Type": "text/html"}, b"ok")})
    )
    outcome = collector.collect(valid_collection_request())
    original_id = str(outcome.quarantine_record["quarantine_id"])
    original = json.loads((tmp_path / "quarantine" / "records" / f"{original_id}.json").read_text(encoding="utf-8"))
    service = QuarantineService(tmp_path / "quarantine")
    successor = service.dispose(
        original_id,
        decision="APPROVE",
        actor="reviewer",
        rationale="synthetic fixture review",
        rights_redistribution={"state": "PUBLIC_REGISTRY_PAGE", "notes": None},
        retention_policy={"policy_id": "QUARANTINE-DEFAULT", "retain_until": None, "notes": None},
    )
    assert successor["quarantine_id"] != original_id
    assert successor["predecessor_quarantine_id"] == original_id
    unchanged = load_quarantine_record(tmp_path / "quarantine", original_id)
    assert unchanged == original
    assert unchanged["approval_state"] == "PENDING_HUMAN_APPROVAL"
    payload = prepare_monitoring_handoff(tmp_path / "quarantine", original_id)
    assert payload.quarantine_id == successor["quarantine_id"]
    with pytest.raises(HandoffBlockedError):
        service.dispose(original_id, decision="APPROVE", actor="reviewer", rationale="again")


def test_connected_address_is_per_response_not_mutable_transport_state() -> None:
    transport = PinnedSocketHttpTransport()
    assert not hasattr(transport, "last_connected_address")
    response = TransportResponse(
        status=200, headers={"content-type": "text/plain"}, body=b"x", connected_address="93.184.216.34"
    )
    status, headers, body = response
    assert status == 200 and body == b"x" and headers["content-type"] == "text/plain"
    assert response.connected_address == "93.184.216.34"


def test_quarantine_reject_and_unsupported_decision(tmp_path: Path) -> None:
    collector = _collector(
        tmp_path, FakeTransport(responses={"https://example.org/source": (200, {"Content-Type": "text/html"}, b"ok")})
    )
    outcome = collector.collect(valid_collection_request())
    original_id = str(outcome.quarantine_record["quarantine_id"])
    service = QuarantineService(tmp_path / "quarantine")
    rejected = service.dispose(original_id, decision="REJECT", actor="reviewer", rationale="synthetic reject")
    assert rejected["approval_state"] == "REJECTED"
    assert rejected["predecessor_quarantine_id"] == original_id
    with pytest.raises(ValueError, match="Unsupported quarantine decision"):
        service.dispose(original_id, decision="MAYBE", actor="reviewer", rationale="no")


def test_scanner_incomplete_identity_fail_closed() -> None:
    result = FailClosedContentSafetyScanner().scan(sha256="", media_type="text/html", size_bytes=1)
    assert result.state == "SCANNER_UNAVAILABLE_FAIL_CLOSED"
    with pytest.raises(ValueError, match="Unknown scan state"):
        from neuroai_workbench.collector.scan import ScanResult

        ScanResult(state="CLEAN", scanner_id="x", detail="no").as_dict()


def test_authorization_packet_validation_failures() -> None:
    from neuroai_workbench.collector.authorization import (
        AUTHORIZATION_BOUNDARY,
        LIVE_AUTHORIZATION_ENV,
        LIVE_COLLECTION_ENV,
        load_live_authorization_from_environment,
        require_network_authorization,
        validate_authorization_packet,
    )

    with pytest.raises(CollectionAuthorizationError):
        validate_authorization_packet("not-an-object")
    with pytest.raises(CollectionAuthorizationError, match="missing fields"):
        validate_authorization_packet({"authorization_id": "AUTH-X"})
    with pytest.raises(CollectionAuthorizationError, match="network_mode"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "WIFI_CAFE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="boundary"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": "wrong",
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="authorization_id"):
        validate_authorization_packet(
            {
                "authorization_id": " ",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="authorized_by"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "  ",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="authorized_at"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="purpose"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="boolean"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": "yes",
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="network_permitted=true"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "AUTHORIZED_NETWORK",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="OFFLINE authorization"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": True,
                "boundary": AUTHORIZATION_BOUNDARY,
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="64-character hex digest"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
                "authorization_sha256": "short",
            }
        )
    with pytest.raises(CollectionAuthorizationError, match="hexadecimal"):
        validate_authorization_packet(
            {
                "authorization_id": "AUTH-X",
                "authorized_by": "local-operator",
                "authorized_at": "2026-08-31T00:00:00Z",
                "purpose": "unit-test",
                "network_mode": "OFFLINE",
                "network_permitted": False,
                "boundary": AUTHORIZATION_BOUNDARY,
                "authorization_sha256": "g" * 64,
            }
        )
    packet = build_authorization_packet(
        authorization_id="AUTH-BAD",
        authorized_by="local-operator",
        purpose="unit-test",
        network_mode="OFFLINE",
        network_permitted=False,
    )
    with pytest.raises(CollectionAuthorizationError):
        require_network_authorization(packet)
    digestless = dict(packet)
    digestless.pop("authorization_sha256")
    with pytest.raises(CollectionAuthorizationError, match="digest-bound authorization packet"):
        require_network_authorization({**digestless, "network_mode": "AUTHORIZED_NETWORK", "network_permitted": True})

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
        monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, "{not-json")
        with pytest.raises(CollectionAuthorizationError, match="not valid JSON"):
            load_live_authorization_from_environment()
        monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, "[]")
        with pytest.raises(CollectionAuthorizationError, match="must decode to an object"):
            load_live_authorization_from_environment()
    finally:
        monkeypatch.undo()


def test_require_network_authorization_rechecks_digest_under_live_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroai_workbench.collector import authorization as authorization_module

    packet = build_authorization_packet(
        authorization_id="AUTH-RECHECK",
        authorized_by="local-operator",
        purpose="unit-test",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-03T00:00:00Z",
    )
    monkeypatch.setenv("NEUROAI_LIVE_COLLECTION", "1")
    monkeypatch.setattr(authorization_module, "authorization_digest", lambda _: "0" * 64)
    with pytest.raises(CollectionAuthorizationError, match="digest mismatch"):
        authorization_module.require_network_authorization(packet)
