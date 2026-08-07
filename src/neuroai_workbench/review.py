"""Public collaborative-review compatibility boundary.

The record engine remains private, and the supported review module object pins
proposal application to the hardened implementation deterministically.
"""

from __future__ import annotations

import sys

from . import _review_records as _records
from . import proposal_application as _proposal_application

setattr(_records, "apply_review_proposal", _proposal_application.apply_review_proposal)
setattr(
    _records,
    "assessment_edit_authority_assignments",
    _proposal_application.assessment_edit_authority_assignments,
)
sys.modules[__name__] = _records
