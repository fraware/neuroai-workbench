"""Public collaborative-review API.

Review assignments, lineage, statements, dispositions, appeals, and reporting remain
implemented in the private record engine. Accepted-proposal application is exported
from the hardened proposal-application module so import order cannot select the
legacy permissive implementation.
"""

from __future__ import annotations

from typing import Any

from . import _review_records as _records
from ._review_records import *  # noqa: F403
from .proposal_application import (
    apply_review_proposal as apply_review_proposal,
    assessment_edit_authority_assignments as assessment_edit_authority_assignments,
)

# The copied record engine predates #122 and contains the superseded proposal-apply
# callable. It is deliberately removed from the private module object after import;
# all supported application paths resolve to proposal_application.py.
if hasattr(_records, "apply_review_proposal"):
    delattr(_records, "apply_review_proposal")


def __getattr__(name: str) -> Any:
    """Preserve private compatibility helpers without re-exporting proposal apply."""
    if name == "apply_review_proposal":
        return apply_review_proposal
    if name == "assessment_edit_authority_assignments":
        return assessment_edit_authority_assignments
    return getattr(_records, name)
