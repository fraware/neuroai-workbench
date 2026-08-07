"""Offline-first NeuroAI evidence and decision workbench."""

__version__ = "0.3.0.dev0"


def _install_proposal_application_hardening() -> None:
    """Install compatibility exports for the legacy review module surface."""
    from . import review
    from .proposal_application import apply_review_proposal, assessment_edit_authority_assignments

    setattr(review, "apply_review_proposal", apply_review_proposal)
    setattr(review, "assessment_edit_authority_assignments", assessment_edit_authority_assignments)


_install_proposal_application_hardening()
del _install_proposal_application_hardening
