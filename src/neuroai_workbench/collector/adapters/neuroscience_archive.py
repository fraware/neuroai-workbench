"""Neuroscience archive (DANDI / OpenNeuro / PhysioNet) adapter scaffold."""

from __future__ import annotations

from .structured import ScaffoldAdapter

NEUROSCIENCE_ARCHIVE_ADAPTER_ID = "neuroscience_archive"


class NeuroscienceArchiveAdapter(ScaffoldAdapter):
    adapter_id = NEUROSCIENCE_ARCHIVE_ADAPTER_ID
    _SOURCE_CLASSES = frozenset({"NEUROSCIENCE_DATASET_RECORD"})
