"""Public collaborative-review API.

The review-record engine remains private. This typed facade exports the established
review workflow and binds proposal application explicitly to the hardened
implementation. Narrow compatibility hooks preserve deliberate private-hook tests
without package-level or ``sys.modules`` substitution.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from . import _review_records as _records
from . import proposal_application as _proposal_application
from ._review_records import *  # noqa: F403

# Explicit private compatibility hooks used by proposal_application.py and historical
# adversarial tests. Normal production execution leaves these identical to the record
# engine functions and takes the direct fast path below.
_hash_record = _records._hash_record
_load_records = _records._load_records
_review_root = _records._review_root
_review_timestamp = _records._review_timestamp
_scope_allows = _records._scope_allows
_verify_assignment_event_correspondence = _records._verify_assignment_event_correspondence
load_events = _records.load_events

apply_review_proposal = _proposal_application.apply_review_proposal
assessment_edit_authority_assignments = _proposal_application.assessment_edit_authority_assignments

# Once the public facade is imported, the private engine module object also points at
# the hardened callables. The historical source remains private compatibility code;
# supported application paths do not select its superseded implementation.
setattr(_records, "apply_review_proposal", apply_review_proposal)
setattr(_records, "assessment_edit_authority_assignments", assessment_edit_authority_assignments)


def _invoke_with_compat_hooks(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Mirror deliberately patched private hooks only for the duration of one call."""
    if (
        _hash_record is _records._hash_record
        and _review_timestamp is _records._review_timestamp
        and load_events is _records.load_events
    ):
        return function(*args, **kwargs)

    prior_hash = _records._hash_record
    prior_timestamp = _records._review_timestamp
    prior_load_events = _records.load_events
    _records._hash_record = _hash_record
    _records._review_timestamp = _review_timestamp
    _records.load_events = load_events
    try:
        return function(*args, **kwargs)
    finally:
        _records._hash_record = prior_hash
        _records._review_timestamp = prior_timestamp
        _records.load_events = prior_load_events


def _assignment_index(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    return cast(
        tuple[dict[str, dict[str, Any]], dict[str, str]],
        _invoke_with_compat_hooks(_records._assignment_index, records),
    )


def _compat_create_review_assignment(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _invoke_with_compat_hooks(_records.create_review_assignment, *args, **kwargs))


def _compat_submit_review_statement(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _invoke_with_compat_hooks(_records.submit_review_statement, *args, **kwargs))


def _compat_file_review_appeal(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _invoke_with_compat_hooks(_records.file_review_appeal, *args, **kwargs))


def _compat_verify_review_records(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _invoke_with_compat_hooks(_records.verify_review_records, *args, **kwargs))


# Preserve the imported API's static signatures for mypy and install only the runtime
# bridges needed by historical private-hook tests.
globals()["create_review_assignment"] = _compat_create_review_assignment
globals()["submit_review_statement"] = _compat_submit_review_statement
globals()["file_review_appeal"] = _compat_file_review_appeal
globals()["verify_review_records"] = _compat_verify_review_records


def __getattr__(name: str) -> Any:
    """Preserve private compatibility helpers without weakening proposal application."""
    if name == "apply_review_proposal":
        return apply_review_proposal
    if name == "assessment_edit_authority_assignments":
        return assessment_edit_authority_assignments
    return getattr(_records, name)
