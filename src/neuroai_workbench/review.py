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

# Typed compatibility hooks used by proposal_application.py and existing tests.
_hash_record = _records._hash_record
_assignment_index = _records._assignment_index
_load_records = _records._load_records
_review_root = _records._review_root
_review_timestamp = _records._review_timestamp
_scope_allows = _records._scope_allows
_verify_assignment_event_correspondence = _records._verify_assignment_event_correspondence

from .proposal_application import (  # noqa: E402
    apply_review_proposal as apply_review_proposal,
    assessment_edit_authority_assignments as assessment_edit_authority_assignments,
)

# The private record engine predates #122 and contains the superseded proposal-apply
# callable. Remove it from that module object; all supported application paths resolve
# to proposal_application.py.
if hasattr(_records, "apply_review_proposal"):
    delattr(_records, "apply_review_proposal")


def __getattr__(name: str) -> Any:
    """Preserve private compatibility helpers without re-exporting proposal apply."""
    if name == "apply_review_proposal":
        return apply_review_proposal
    if name == "assessment_edit_authority_assignments":
        return assessment_edit_authority_assignments
    return getattr(_records, name)
