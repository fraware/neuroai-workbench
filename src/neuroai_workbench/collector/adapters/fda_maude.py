"""FDA MAUDE adverse-event adapter scaffold (not complete)."""

from __future__ import annotations

from .structured import ScaffoldAdapter

FDA_MAUDE_ADAPTER_ID = "fda_maude"


class FdaMaudeAdapter(ScaffoldAdapter):
    adapter_id = FDA_MAUDE_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"FDA_MAUDE_RECORD"})
