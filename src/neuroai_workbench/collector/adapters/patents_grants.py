"""Patents / grants adapter scaffold (EPO OPS / NIH RePORTER) — not complete."""

from __future__ import annotations

from .structured import ScaffoldAdapter

PATENTS_GRANTS_ADAPTER_ID = "patents_grants"


class PatentsGrantsAdapter(ScaffoldAdapter):
    adapter_id = PATENTS_GRANTS_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"PATENT_OR_GRANT_RECORD"})
