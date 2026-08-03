from __future__ import annotations

from .evidence_transactions import evidence_registration_lock

case_mutation_lock = evidence_registration_lock

__all__ = ["case_mutation_lock"]
