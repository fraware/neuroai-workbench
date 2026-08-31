"""Authority-boundary tests for institutional, ops, validation, monitoring, reopening."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.assessment_validation import (
    export_disagreement_bundle,
    freeze_validation_cohort,
    isolate_reviewer_workspace,
    record_disagreement_metrics,
    validation_export_guard,
    write_cohort_manifest,
)
from neuroai_workbench.institutional import (
    LocalDevIdentityAdapter,
    OidcProfileAdapter,
    SamlProfileAdapter,
    append_audit_event,
    assert_deployment_mode_separation,
    assert_not_local_case_server_auth,
    assign_rbac_role,
    break_glass_hook,
    s3_tenant_boundary,
)
from neuroai_workbench.monitoring_lifecycle import (
    advance_onboarding,
    assert_no_monitor_from_source_acceptance,
    initial_onboarding_record,
)
from neuroai_workbench.monitoring_service import MonitoringService
from neuroai_workbench.operations import invoke_runbook
from neuroai_workbench.reopening_service import ReopeningService
from neuroai_workbench.util import atomic_write_json


def test_institutional_fail_closed_and_no_local_server_auth(tmp_path: Path) -> None:
    local = LocalDevIdentityAdapter().authenticate("")
    assert local["authenticated"] is False
    assert local["institutional"] is False
    assert local["fail_closed"] is True

    with pytest.raises(ValueError, match="issuer"):
        OidcProfileAdapter(issuer=" ", audience="aud")
    oidc = OidcProfileAdapter(issuer="https://idp.example", audience="neuroai")
    with pytest.raises(ValueError, match="bearer"):
        oidc.authenticate("   ")
    verified_stub = OidcProfileAdapter(
        issuer="https://idp.example",
        audience="neuroai",
        require_verified_token=False,
    ).authenticate("token")
    assert verified_stub["authenticated"] is False
    assert verified_stub["verification_state"] == "ADAPTER_STUB_NOT_PRODUCTION_VERIFIER"
    assert verified_stub["binds_to_threading_httpserver"] is False

    with pytest.raises(ValueError, match="entity_id"):
        SamlProfileAdapter(entity_id="", acs_url="https://acs.example/acs")
    with pytest.raises(ValueError, match="ThreadingHTTPServer"):
        SamlProfileAdapter(entity_id="https://idp.example/saml", acs_url="http://localhost:9000/acs")
    saml = SamlProfileAdapter(entity_id="https://idp.example/saml", acs_url="https://acs.example/acs")
    with pytest.raises(ValueError, match="assertion"):
        saml.authenticate("")
    saml_auth = saml.authenticate("assertion")
    assert saml_auth["authenticated"] is False
    assert saml_auth["fail_closed"] is True
    assert_not_local_case_server_auth(saml_auth)

    with pytest.raises(ValueError, match="cannot be marked institutional"):
        assert_deployment_mode_separation({"deployment_mode": "LOCAL", "institutional": True})
    with pytest.raises(ValueError, match="must not bind"):
        assert_deployment_mode_separation({"deployment_mode": "INSTITUTIONAL", "binds_to_threading_httpserver": True})
    with pytest.raises(ValueError, match="authenticated=true"):
        assert_deployment_mode_separation(
            {
                "deployment_mode": "INSTITUTIONAL",
                "binds_to_threading_httpserver": False,
                "authenticated": True,
                "verification_state": "FAIL_CLOSED_UNVERIFIED",
            }
        )
    with pytest.raises(ValueError, match="must not bind"):
        assert_not_local_case_server_auth({"binds_to_threading_httpserver": True})

    with pytest.raises(ValueError, match="Unsupported RBAC"):
        assign_rbac_role(subject="u", role="ROOT", actor="a")
    role = assign_rbac_role(subject="u", role="RELEASE_AUTHORIZER", actor="a")
    assert role["grants_release_authority"] is False

    bad_audit = tmp_path / "audit.json"
    atomic_write_json(bad_audit, {"not": "array"})
    with pytest.raises(ValueError, match="JSON array"):
        append_audit_event(bad_audit, action="X", actor="a", resource="r")

    with pytest.raises(ValueError, match="tenant_id"):
        s3_tenant_boundary(tenant_id=" ", object_key="a")
    with pytest.raises(ValueError, match="relative"):
        s3_tenant_boundary(tenant_id="t1", object_key="../escape")
    with pytest.raises(ValueError, match="rationale"):
        break_glass_hook(actor="sec", rationale="  ")


def test_ops_unknown_runbook_refused() -> None:
    with pytest.raises(ValueError, match="Unknown runbook"):
        invoke_runbook(runbook_id="MAKE_EVERYTHING_READY", actor="ops", notes="no")


def test_validation_cohort_guards_and_export(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one"):
        freeze_validation_cohort(
            protocol_id="P",
            instrument_version="v4.2",
            case_battery_id="B",
            reviewer_assignment_id="A",
            evidence_cutoff="2026-01-01",
            study_arm="RELIABILITY",
            case_ids=[],
        )
    with pytest.raises(ValueError, match="protocol_id"):
        freeze_validation_cohort(
            protocol_id=" ",
            instrument_version="v4.2",
            case_battery_id="B",
            reviewer_assignment_id="A",
            evidence_cutoff="2026-01-01",
            study_arm="RELIABILITY",
            case_ids=["C1"],
        )
    with pytest.raises(ValueError, match="outside"):
        freeze_validation_cohort(
            protocol_id="P",
            instrument_version="v4.2",
            case_battery_id="B",
            reviewer_assignment_id="A",
            evidence_cutoff="2026-01-01",
            study_arm="RELIABILITY",
            case_ids=["C1"],
            allow_undersized_for_tooling=False,
        )

    cohort = freeze_validation_cohort(
        protocol_id="P-VAL",
        instrument_version="v4.2",
        case_battery_id="B",
        reviewer_assignment_id="A",
        evidence_cutoff="2026-01-01",
        study_arm="RELIABILITY",
        case_ids=[f"C{i}" for i in range(22)],
    )
    path = write_cohort_manifest(tmp_path, cohort)
    assert write_cohort_manifest(tmp_path, cohort) == path
    divergent = {**cohort, "study_arm": "OTHER"}
    with pytest.raises(ValueError, match="divergent"):
        write_cohort_manifest(tmp_path, divergent)

    with pytest.raises(ValueError, match="reviewer_slot"):
        isolate_reviewer_workspace(tmp_path, reviewer_slot="../x", cohort_sha256=cohort["cohort_sha256"])

    metrics = [
        record_disagreement_metrics(
            cohort_sha256=cohort["cohort_sha256"],
            case_id="C0",
            requirement_id="R-1",
            findings=["PASS", "FAIL"],
            evidence_selection_disagreement=True,
            time_burden_minutes=12.5,
            uncertainty_flagged=True,
            reopening_triggered=True,
        )
    ]
    with pytest.raises(ValueError, match="global validation"):
        export_disagreement_bundle(
            cohort={**cohort, "global_validation_claim": True},
            metrics=metrics,
            output_dir=tmp_path / "export-bad",
        )
    bundle = export_disagreement_bundle(cohort=cohort, metrics=metrics, output_dir=tmp_path / "export")
    assert bundle["global_validation_claim"] is False
    assert validation_export_guard({"case_id": "C0"})["s2_safe"] is True


def test_onboarding_quarantine_and_release_authority_gates() -> None:
    record = initial_onboarding_record(source_candidate_id="CAND-H", actor="tester")
    stages = [
        "REPLAY_PROJECTION",
        "CURRENT_SOURCE_IDENTITY_CHECK",
        "PENDING_HUMAN_ACCEPTANCE",
        "HUMAN_DISPOSITION_RECORDED",
        "DRAFT_SOURCE_NAMESPACE_SUCCESSOR",
        "DISCOVERY_ORIGIN_SOURCE_CANDIDATE",
        "PENDING_MONITOR_REVIEW",
        "MONITORING_REVIEW_RECORDED",
        "DRAFT_ONBOARDING_PLAN",
        "AUTHORIZED_FIRST_CAPTURE_PENDING",
        "QUARANTINE_HELD",
        "QUARANTINE_APPROVED",
        "MONITORING_HANDOFF",
        "DRAFT_MONITOR_REGISTRY_SUCCESSOR",
        "AWAITING_RELEASE_AUTHORITY",
    ]
    for stage in stages:
        record = advance_onboarding(record, next_stage=stage, actor="tester", note=stage)
    assert record["quarantine_approved"] is True
    assert record["monitor_created"] is False
    assert record["live_monitor_authorized"] is False
    assert record["release_authorized"] is False

    poisoned = {
        **initial_onboarding_record(source_candidate_id="CAND-X", actor="t"),
        "stage": "HUMAN_DISPOSITION_RECORDED",
        "monitor_created": True,
    }
    with pytest.raises(ValueError, match="must not create a live monitor"):
        assert_no_monitor_from_source_acceptance(poisoned)

    service = MonitoringService()
    typed = service.classify({"classification": "WEIRD_UPSTREAM"}, comparison_scope="bytes")
    assert typed["typed_change_class"] == "CONTENT_CHANGED_REQUIRES_REVIEW"
    assert typed["high_materiality_review_required"] is True


def test_monitoring_service_evaluate_and_compare(tmp_path: Path) -> None:
    from neuroai_workbench.monitoring import initialize_monitoring, record_snapshot
    from neuroai_workbench.util import atomic_write_json

    registry = [
        {
            "monitor_id": "MON-SRC-H1",
            "source_id": "SRC-H1",
            "url": "https://example.org/regulatory",
            "publisher": "Example regulator",
            "source_class": "REGULATORY_RECORD",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": "fixture",
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        }
    ]
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, registry)
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, registry_path, actor="tester")
    older = record_snapshot(
        workspace,
        "SRC-H1",
        b"alpha",
        media_type="text/plain",
        retrieved_at="2026-08-01T00:00:00Z",
        actor="tester",
    )
    newer = record_snapshot(
        workspace,
        "SRC-H1",
        b"beta",
        media_type="text/plain",
        retrieved_at="2026-08-08T00:00:00Z",
        actor="tester",
    )
    service = MonitoringService()
    plan = service.evaluate_due(workspace, as_of="2026-08-15")
    assert plan["service_boundary"]
    plan_default = service.evaluate_due(workspace)
    assert plan_default["service_boundary"]
    compared = service.compare(
        workspace,
        "SRC-H1",
        str(older["snapshot_id"]),
        str(newer["snapshot_id"]),
    )
    assert compared["typed_change_class"]
    assert compared["service_boundary"]


def test_reopening_service_requires_input_and_never_mutates(tmp_path: Path) -> None:
    service = ReopeningService()
    with pytest.raises(ValueError, match="requires delta"):
        service.analyze()
    sealed = service.analyze(
        {
            "operations": [],
            "metadata": {"delta_id": "DELTA-" + "b" * 32},
        },
        manifests={},
    )
    assert sealed["assessment_mutated"] is False
    assert sealed["empty_basis_no_reopening_is_not_nothing_changed"] is True
    # Path form still requires a structurally valid observatory delta document.
    delta_path = tmp_path / "delta.json"
    atomic_write_json(delta_path, {"not": "a delta"})
    with pytest.raises(ValueError):
        service.analyze(observatory_delta_path=delta_path, manifests={})
