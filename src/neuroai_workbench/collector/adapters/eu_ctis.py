"""EU CTIS adapter scaffold (not complete)."""

from __future__ import annotations

from .structured import ScaffoldAdapter

EU_CTIS_ADAPTER_ID = "eu_ctis"


class EuCtisAdapter(ScaffoldAdapter):
    adapter_id = EU_CTIS_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"EU_CTIS_RECORD"})
