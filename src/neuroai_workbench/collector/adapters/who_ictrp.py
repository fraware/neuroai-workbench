"""WHO ICTRP adapter scaffold (not complete)."""

from __future__ import annotations

from .structured import ScaffoldAdapter

WHO_ICTRP_ADAPTER_ID = "who_ictrp"


class WhoIctrpAdapter(ScaffoldAdapter):
    adapter_id = WHO_ICTRP_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"WHO_ICTRP_RECORD"})
