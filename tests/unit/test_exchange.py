from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.exchange import (
    _hash_record,
    create_exchange_request,
    load_exchange_request,
    record_exchange_response,
    render_exchange_markdown,
    verify_exchange_record,
)
from neuroai_workbench.workspace import Workspace

PRIMA = Path("examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json")


def _workspace(tmp_path: Path) -> tuple[Workspace, str]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    workspace.import_case(PRIMA, case_id="PRIMA-EXCHANGE")
    return workspace, "PRIMA-EXCHANGE"


def test_exchange_request_is_metadata_only_and_bounded(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    result = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="PRIMA evidence custodian",
        purpose="Resolve the raw-data and exact-configuration evidence gap.",
        requested_materials=["Controlled raw-data access protocol", "Current commercial configuration record"],
        gap_ids=["GAP-PR-001"],
        disclosure_constraints=["No participant-level data should be transmitted through the workbench."],
        actor="lead-assessor",
    )
    request = result["request"]
    assert request["evidence_bytes_included"] is False
    assert request["local_paths_included"] is False
    assert request["selected_evidence_metadata"][0]["public_url"].startswith("https://")
    assert "url_or_path" not in request["selected_evidence_metadata"][0]
    assert request["related_gaps"][0]["gap_id"] == "GAP-PR-001"
    verification = verify_exchange_record(workspace, case_id, request["request_id"])
    assert verification["valid"] is True
    assert verification["response_recorded"] is False
    assert verification["warnings"] == ["no exchange response recorded"]


def test_exchange_response_records_out_of_band_reference_without_mutation(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    before = (workspace.case_path(case_id) / "assessment.json").read_bytes()
    request = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="PRIMA evidence custodian",
        purpose="Request controlled access metadata.",
        requested_materials=["Access procedure and immutable file digest"],
        actor="lead-assessor",
    )["request"]
    record_exchange_response(
        workspace,
        case_id,
        request["request_id"],
        "AVAILABLE_UNDER_CONDITIONS",
        holder="PRIMA evidence custodian",
        conditions=["Independent review agreement required"],
        materials=[{
            "evidence_id": "EV-PR-001",
            "holder_reference": "custodian-record-2026-001",
            "sha256": "a" * 64,
        }],
        notes="Evidence remains with the holder and has not been transferred.",
        actor="lead-assessor",
    )
    verification = verify_exchange_record(workspace, case_id, request["request_id"])
    assert verification["valid"] is True
    assert verification["response_state"] == "AVAILABLE_UNDER_CONDITIONS"
    assert (workspace.case_path(case_id) / "assessment.json").read_bytes() == before
    markdown = render_exchange_markdown(workspace, case_id, request["request_id"])
    assert "metadata and holder representations only" in markdown
    assert "AVAILABLE_UNDER_CONDITIONS" in markdown
    assert "custodian-record-2026-001" not in markdown


def test_exchange_rejects_unknown_records_sensitive_text_and_invalid_materials(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    with pytest.raises(ValueError, match="At least one evidence ID"):
        create_exchange_request(
            workspace,
            case_id,
            [],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=["Record"],
        )
    with pytest.raises(ValueError, match="At least one requested material"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-PR-001"],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=[],
        )
    with pytest.raises(ValueError, match="Invalid actor ID"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-PR-001"],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=["Record"],
            actor="not valid",
        )
    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-UNKNOWN"],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=["Record"],
        )
    with pytest.raises(ValueError, match="Unknown gap IDs"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-PR-001"],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=["Record"],
            gap_ids=["GAP-UNKNOWN"],
        )
    with pytest.raises(ValueError, match="blocked sensitive patterns"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-PR-001"],
            recipient="Custodian",
            purpose="api_key=123456789-secret",
            requested_materials=["Record"],
        )

    request = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="Custodian",
        purpose="Request metadata.",
        requested_materials=["Record"],
    )["request"]
    with pytest.raises(FileNotFoundError, match="Unknown evidence exchange request"):
        load_exchange_request(workspace, case_id, "EX-NOT-THERE")
    with pytest.raises(ValueError, match="Unsupported exchange response state"):
        record_exchange_response(
            workspace, case_id, request["request_id"], "RECEIVED", holder="Custodian"
        )
    with pytest.raises(ValueError, match="requires at least one material"):
        record_exchange_response(
            workspace, case_id, request["request_id"], "PROVIDED_OUT_OF_BAND", holder="Custodian"
        )
    with pytest.raises(ValueError, match="cannot include material references"):
        record_exchange_response(
            workspace,
            case_id,
            request["request_id"],
            "DECLINED",
            holder="Custodian",
            materials=[{"evidence_id": "EV-PR-001", "holder_reference": "reference-1"}],
        )
    with pytest.raises(ValueError, match=r"materials\[0\] must be an object"):
        record_exchange_response(
            workspace,
            case_id,
            request["request_id"],
            "PROVIDED_OUT_OF_BAND",
            holder="Custodian",
            materials=["not-an-object"],  # type: ignore[list-item]
        )
    with pytest.raises(ValueError, match="unrequested evidence ID"):
        record_exchange_response(
            workspace,
            case_id,
            request["request_id"],
            "PROVIDED_OUT_OF_BAND",
            holder="Custodian",
            materials=[{"evidence_id": "EV-UNKNOWN", "holder_reference": "reference-1"}],
        )
    with pytest.raises(ValueError, match="local path"):
        record_exchange_response(
            workspace,
            case_id,
            request["request_id"],
            "PROVIDED_OUT_OF_BAND",
            holder="Custodian",
            materials=[{"evidence_id": "EV-PR-001", "holder_reference": "/private/evidence.pdf"}],
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        record_exchange_response(
            workspace,
            case_id,
            request["request_id"],
            "PROVIDED_OUT_OF_BAND",
            holder="Custodian",
            materials=[{
                "evidence_id": "EV-PR-001",
                "holder_reference": "reference-1",
                "sha256": "NOT-A-DIGEST",
            }],
        )


def test_exchange_detects_tampering_duplicate_response_and_stale_assessment(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    request_result = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="Custodian",
        purpose="Request metadata.",
        requested_materials=["Record"],
    )
    request = request_result["request"]
    response_result = record_exchange_response(
        workspace,
        case_id,
        request["request_id"],
        "DECLINED",
        holder="Custodian",
        notes="The holder declined the request.",
    )
    with pytest.raises(ValueError, match="already recorded"):
        record_exchange_response(
            workspace, case_id, request["request_id"], "DECLINED", holder="Custodian"
        )

    assessment = workspace.load_case(case_id)
    assessment["assessment_metadata"]["title"] = "Updated after exchange request"
    workspace.save_case(case_id, assessment, actor="lead-assessor", require_valid=True)
    stale = verify_exchange_record(workspace, case_id, request["request_id"])
    assert stale["valid"] is True
    assert any("assessment has changed" in warning for warning in stale["warnings"])

    response_path = Path(response_result["path"])
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["response_state"] = "PROVIDED_OUT_OF_BAND"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    tampered = verify_exchange_record(workspace, case_id, request["request_id"])
    assert tampered["valid"] is False
    assert "response hash mismatch" in tampered["errors"]

    request_path = Path(request_result["path"])
    request_record = json.loads(request_path.read_text(encoding="utf-8"))
    request_record["evidence_bytes_included"] = True
    request_path.write_text(json.dumps(request_record), encoding="utf-8")
    tampered_request = verify_exchange_record(workspace, case_id, request["request_id"])
    assert tampered_request["valid"] is False
    assert "request hash mismatch" in tampered_request["errors"]
    assert any("no-evidence-bytes boundary" in error for error in tampered_request["errors"])


def test_exchange_omits_non_public_source_locations_and_rejects_duplicate_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, case_id = _workspace(tmp_path)
    assessment = workspace.load_case(case_id)
    assessment["evidence_register"][0]["url_or_path"] = "/private/custodian/evidence.pdf"
    workspace.save_case(case_id, assessment, actor="lead-assessor", require_valid=True)
    monkeypatch.setattr("neuroai_workbench.exchange.utc_now", lambda: "2026-07-30T12:00:00Z")

    request = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="Custodian",
        purpose="Request metadata.",
        requested_materials=["Record"],
    )["request"]
    assert "public_url" not in request["selected_evidence_metadata"][0]
    with pytest.raises(ValueError, match="identical exchange request"):
        create_exchange_request(
            workspace,
            case_id,
            ["EV-PR-001"],
            recipient="Custodian",
            purpose="Request metadata.",
            requested_materials=["Record"],
        )


def test_exchange_response_rejects_tampered_request(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    result = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="Custodian",
        purpose="Request metadata.",
        requested_materials=["Record"],
    )
    path = Path(result["path"])
    request = json.loads(path.read_text(encoding="utf-8"))
    request["purpose"] = "Tampered purpose"
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="request hash is invalid"):
        record_exchange_response(
            workspace, case_id, result["request"]["request_id"], "DECLINED", holder="Custodian"
        )


def test_exchange_verifier_reports_boundary_corruption_and_event_tampering(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    request_result = create_exchange_request(
        workspace,
        case_id,
        ["EV-PR-001"],
        recipient="Custodian",
        purpose="Request metadata.",
        requested_materials=["Record"],
    )
    request_id = request_result["request"]["request_id"]
    response_result = record_exchange_response(
        workspace,
        case_id,
        request_id,
        "PROVIDED_OUT_OF_BAND",
        holder="Custodian",
        materials=[{"evidence_id": "EV-PR-001", "holder_reference": "reference-1"}],
    )

    request_path = Path(request_result["path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["local_paths_included"] = True
    request["selected_evidence_metadata"][0]["url_or_path"] = "/private/evidence.pdf"
    request["selected_evidence_metadata"][0]["public_url"] = "file:///private/evidence.pdf"
    request["request_sha256"] = _hash_record(request, "request_sha256")
    request_path.write_text(json.dumps(request), encoding="utf-8")

    response_path = Path(response_result["path"])
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["request_sha256"] = "0" * 64
    response["response_state"] = "RECEIVED"
    response["evidence_bytes_received"] = True
    response["materials"][0]["bytes_received_by_workbench"] = True
    response["materials"][0]["holder_reference"] = "/private/evidence.pdf"
    response["materials"][0]["verification_state"] = "VERIFIED"
    response["response_sha256"] = _hash_record(response, "response_sha256")
    response_path.write_text(json.dumps(response), encoding="utf-8")

    event_path = workspace.case_path(case_id) / "events.jsonl"
    lines = event_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[-1])
    event["payload"]["response_state"] = "TAMPERED"
    lines[-1] = json.dumps(event)
    event_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = verify_exchange_record(workspace, case_id, request_id)
    assert report["valid"] is False
    expected = (
        "no-local-paths boundary",
        "prohibited url_or_path",
        "non-public URL",
        "does not reference the current request hash",
        "unsupported state",
        "no-evidence-bytes boundary",
        "claims bytes were received",
        "local path or file URI",
        "overstates workbench verification",
        "event chain",
    )
    for fragment in expected:
        assert any(fragment in error for error in report["errors"]), fragment
    markdown = render_exchange_markdown(workspace, case_id, request_id)
    assert "Integrity errors" in markdown
