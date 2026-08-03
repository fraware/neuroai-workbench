"""FDA device recall / enforcement adapter scaffold (not complete)."""

from __future__ import annotations

from .structured import ScaffoldAdapter

FDA_RECALL_ADAPTER_ID = "fda_recall"


class FdaRecallAdapter(ScaffoldAdapter):
    adapter_id = FDA_RECALL_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"FDA_RECALL_RECORD"})
