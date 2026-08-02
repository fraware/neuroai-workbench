"""Hardened HTTP collector core with quarantine-only writes."""

from .config import CollectorConfig
from .service import CollectionOutcome, HttpCollector, PriorCapture

__all__ = [
    "CollectorConfig",
    "CollectionOutcome",
    "HttpCollector",
    "PriorCapture",
]
