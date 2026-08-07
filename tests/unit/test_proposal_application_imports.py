from __future__ import annotations

import neuroai_workbench.review as review
from neuroai_workbench.proposal_application import apply_review_proposal, assessment_edit_authority_assignments


def test_review_compatibility_exports_use_hardened_implementations() -> None:
    assert review.apply_review_proposal is apply_review_proposal
    assert getattr(review, "assessment_edit_authority_assignments") is assessment_edit_authority_assignments
