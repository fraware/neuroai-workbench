from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phase3-external-proof.yml"
REQUIRED_CHECKS = ROOT / ".github" / "required-checks.json"

CONFIRMATION = "AUTHORIZE_ONE_CT_GOV_PHASE3_LIVE_REQUEST"
SOURCE_ID = "SRC-PR-002"
NCT_ID = "NCT04676854"
ORIGIN = "https://clinicaltrials.gov"
PROGRAMME_ID = "PHASE3-CTGOV-EXTERNAL-PROOF-V1"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _workflow_spec() -> dict[str, object]:
    manifest = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    matches = [item for item in manifest["workflows"] if item["path"] == ".github/workflows/phase3-external-proof.yml"]
    assert len(matches) == 1
    return matches[0]


def test_external_proof_workflow_is_manual_dispatch_only() -> None:
    text = _workflow_text()
    assert text.startswith("name: Phase 3 external proof\n\non:\n  workflow_dispatch:\n")
    assert "  pull_request:" not in text
    assert "  push:" not in text
    assert "  schedule:" not in text
    assert "  pull_request_target:" not in text
    assert "  workflow_run:" not in text
    assert "  repository_dispatch:" not in text
    assert 'test "$GITHUB_EVENT_NAME" = "workflow_dispatch"' in text
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in text
    assert f'test "$CONFIRMATION" = "{CONFIRMATION}"' in text


def test_external_proof_workflow_has_read_only_permissions_and_no_secrets() -> None:
    text = _workflow_text()
    assert "permissions:\n  contents: read\n" in text
    assert "secrets." not in text
    assert "permissions: write-all" not in text
    assert "id-token: write" not in text
    assert "contents: write" not in text


def test_external_proof_identity_is_fixed_to_governed_clinicaltrials_anchor() -> None:
    text = _workflow_text()
    for value in (SOURCE_ID, NCT_ID, ORIGIN, PROGRAMME_ID):
        assert value in text
    assert 'source_id = "SRC-PR-002"' in text
    assert 'nct_id = "NCT04676854"' in text
    assert 'origin = "https://clinicaltrials.gov"' in text
    assert "--nct-id \"$PHASE3_NCT_ID\"" in text
    assert "--source-id \"$PHASE3_SOURCE_ID\"" in text
    assert "query.term" not in text


def test_live_network_requires_both_policy_and_local_authorization_gates() -> None:
    text = _workflow_text()
    assert "ONLINE_REQUIRED" in text
    assert "REPLAY_ONLY" in text
    assert "FALLBACK_FORBID" in text
    assert 'network_mode="AUTHORIZED_NETWORK"' in text
    assert "network_permitted=True" in text
    assert "NEUROAI_LIVE_COLLECTION=1" in text
    assert "NEUROAI_LIVE_COLLECTION_AUTHORIZATION_JSON" in text
    assert "--execute-live" in text
    assert "--confirm-noncanonical-output" in text
    assert "approved_by=f\"github:{actor}\"" in text
    assert "authorized_by=f\"github:{actor}\"" in text
    assert "GITHUB_RUN_ID" in text
    assert "GITHUB_RUN_ATTEMPT" in text


def test_replay_is_bound_to_exact_live_result_and_zero_collection_attempts() -> None:
    text = _workflow_text()
    assert "PHASE3_RESULT_ID" in text
    assert '--result-id "$PHASE3_RESULT_ID"' in text
    assert 'replay["result_id"] != os.environ["PHASE3_RESULT_ID"]' in text
    assert 'replay["expected_result_id"] != os.environ["PHASE3_RESULT_ID"]' in text
    assert 'replay["collection_attempts"] != 0' in text
    assert 'semantic["claims"]["replay_zero_network_verified"] is not True' in text
    assert 'semantic["projection"]["live_replay_equivalent"] is not True' in text


def test_phase3_recovery_suite_and_authority_boundaries_are_enforced() -> None:
    text = _workflow_text()
    assert "python -m pytest tests/unit/test_online_first_runtime_proof.py -q" in text
    assert 'semantic["claims"]["canonical_s2_mutation_performed"] is not False' in text
    assert '"phase3_reviewed_complete": False' in text
    assert '"phase4_authorized": False' in text
    assert '"g0_passed": False' in text
    assert '"g2_passed": False' in text
    assert '"canonical_s2_authority": False' in text
    assert '"publication_authority": False' in text
    assert '"assessment_effect": "NONE"' in text


def test_only_sanitized_bundle_is_uploaded_and_repository_must_remain_clean() -> None:
    text = _workflow_text()
    upload = re.search(
        r"- name: Upload sanitized Phase 3 proof bundle only\n(?P<body>(?:        .*\n|          .*\n)+)$",
        text,
    )
    assert upload is not None
    body = upload.group("body")
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in body
    assert "path: ${{ runner.temp }}/neuroai-phase3/proof-bundle" in body
    assert "quarantine" not in body
    assert 'test ! -e "$BUNDLE/quarantine"' in text
    assert text.count('test -z "$(git status --porcelain)"') == 2
    assert '"capture_bytes_uploaded": False' in text
    assert '"quarantine_directory_uploaded": False' in text


def test_workflow_is_audited_without_becoming_a_required_pr_context() -> None:
    spec = _workflow_spec()
    assert spec == {
        "path": ".github/workflows/phase3-external-proof.yml",
        "name": "Phase 3 external proof",
        "pull_request_required": False,
        "required_trigger_markers": ["  workflow_dispatch:"],
        "permissions": {"contents": "read"},
        "forbid_secrets": True,
        "jobs": [{"id": "proof", "name": "controlled-external-proof", "required_contexts": []}],
    }
    manifest = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    assert not any("external proof" in context.lower() for context in manifest["required_pull_request_contexts"])
