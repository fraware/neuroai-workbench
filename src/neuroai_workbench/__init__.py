"""Offline-first NeuroAI evidence and decision workbench."""

__version__ = "0.3.0.dev0"


def _install_proposal_application_hardening() -> None:
    """Re-export hardened proposal operations without changing legacy record APIs."""
    from . import review
    from .proposal_application import apply_review_proposal, assessment_edit_authority_assignments

    review.apply_review_proposal = apply_review_proposal
    review.assessment_edit_authority_assignments = assessment_edit_authority_assignments


_install_proposal_application_hardening()
del _install_proposal_application_hardening
