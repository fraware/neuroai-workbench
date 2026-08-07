from __future__ import annotations

import neuroai_workbench._review_records as review_records
import neuroai_workbench.review as review
from neuroai_workbench.proposal_application import apply_review_proposal, assessment_edit_authority_assignments


def test_review_compatibility_exports_use_hardened_implementations() -> None:
    assert review.apply_review_proposal is apply_review_proposal
    assert review.assessment_edit_authority_assignments is assessment_edit_authority_assignments
    assert review_records.apply_review_proposal is apply_review_proposal
    assert review_records.assessment_edit_authority_assignments is assessment_edit_authority_assignments


def test_review_facade_private_fallbacks() -> None:
    assert review.__getattr__("apply_review_proposal") is apply_review_proposal
    assert review.__getattr__("assessment_edit_authority_assignments") is assessment_edit_authority_assignments
    assert review.__getattr__("REVIEW_ROLES") is review.REVIEW_ROLES
