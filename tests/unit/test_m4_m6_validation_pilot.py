from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neuroai_workbench.assessment_validation import (
    export_disagreement_bundle,
    freeze_validation_cohort,
    isolate_reviewer_workspace,
    record_disagreement_metrics,
    validation_export_guard,
    write_cohort_manifest,
)
from neuroai_workbench.institutional import (
    DeploymentMode,
    LocalDevIdentityAdapter,
    OidcProfileAdapter,
    SamlProfileAdapter,
    append_audit_event,
    assert_not_local_case_server_auth,
    assign_rbac_role,
    break_glass_hook,
    s3_tenant_boundary,
)
from neuroai_workbench.operations import (
    invoke_runbook,
    security_hardening_checklist,
    synthetic_canary,
)


class ValidationCohortTests(unittest.TestCase):
    def test_freeze_and_disagreement_without_global_claim(self) -> None:
        case_ids = [f"CASE-{index:02d}" for index in range(1, 25)]
        cohort = freeze_validation_cohort(
            protocol_id="VAL-PROTO-1",
            instrument_version="v4.2",
            case_battery_id="BATTERY-1",
            reviewer_assignment_id="ASSIGN-1",
            evidence_cutoff="2026-08-01",
            study_arm="RELIABILITY",
            case_ids=case_ids,
        )
        self.assertFalse(cohort["global_validation_claim"])
        self.assertFalse(cohort["outcome_collection_authorized"])
        self.assertTrue(cohort["cohort_size_in_target_band"])
        metrics = record_disagreement_metrics(
            cohort_sha256=cohort["cohort_sha256"],
            case_id="CASE-1",
            requirement_id="R-001",
            findings=["PASS", "FAIL"],
            evidence_selection_disagreement=True,
        )
        self.assertTrue(metrics["disagreement"])
        self.assertTrue(metrics["agreement_optimization_forbidden"])
        export = validation_export_guard({"case_id": "CASE-1", "finding": "PASS"})
        self.assertTrue(export["s2_safe"])
        with self.assertRaises(ValueError):
            validation_export_guard({"reviewer_email": "a@b.c"})

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            manifest_path = write_cohort_manifest(workspace, cohort)
            self.assertTrue(manifest_path.is_file())
            reviewer = isolate_reviewer_workspace(workspace, reviewer_slot="R1", cohort_sha256=cohort["cohort_sha256"])
            self.assertTrue((reviewer / "isolation.json").is_file())
            bundle = export_disagreement_bundle(
                cohort=cohort,
                metrics=[metrics],
                output_dir=workspace / "export",
            )
            self.assertFalse(bundle["global_validation_claim"])
            self.assertEqual(bundle["disagreement_count"], 1)


class InstitutionalProfileTests(unittest.TestCase):
    def test_local_dev_not_institutional_and_role_no_release_authority(self) -> None:
        local = LocalDevIdentityAdapter().authenticate("x")
        self.assertFalse(local["authenticated"])
        self.assertFalse(local["institutional"])
        self.assertEqual(local["deployment_mode"], DeploymentMode.LOCAL.value)
        oidc = OidcProfileAdapter(issuer="https://idp.example", audience="neuroai").authenticate("token")
        self.assertFalse(oidc["binds_to_threading_httpserver"])
        self.assertFalse(oidc["authenticated"])
        self.assertEqual(oidc["verification_state"], "FAIL_CLOSED_UNVERIFIED")
        assert_not_local_case_server_auth(oidc)
        with self.assertRaises(ValueError):
            SamlProfileAdapter(entity_id="https://idp.example/saml", acs_url="http://127.0.0.1:8080/acs")
        role = assign_rbac_role(subject="user-1", role="RELEASE_AUTHORIZER", actor="admin")
        self.assertFalse(role["grants_release_authority"])
        sink: list = []
        append_audit_event(sink, action="ROLE_ASSIGNED", actor="admin", resource="user-1")
        self.assertEqual(len(sink), 1)
        with tempfile.TemporaryDirectory() as raw:
            audit_path = Path(raw) / "audit.json"
            append_audit_event(audit_path, action="LOGIN_ATTEMPT", actor="user-1", resource="oidc")
            self.assertTrue(audit_path.is_file())
        tenant = s3_tenant_boundary(tenant_id="t1", object_key="obj/a")
        self.assertTrue(tenant["public_s2_distinct_from_protected_s3"])
        glass = break_glass_hook(actor="sec", rationale="incident")
        self.assertFalse(glass["grants_release_authority"])


class OpsRunbookTests(unittest.TestCase):
    def test_runbooks_and_canary_do_not_claim_readiness(self) -> None:
        rb = invoke_runbook(runbook_id="RELEASE_ROLLBACK", actor="ops", notes="drill")
        self.assertFalse(rb["readiness_claimed"])
        canary = synthetic_canary(name="synthetic-source", actor="ops")
        self.assertFalse(canary["creates_canonical_observation"])
        checklist = security_hardening_checklist()
        self.assertFalse(checklist["software_inferred_pass"])
        self.assertFalse(checklist["institutional_readiness_claimed"])
