"""Hardened HTTP collector core with quarantine-only writes."""

from .config import CollectorConfig
from .service import CollectionOutcome, HttpCollector, PriorCapture
__all__ = [
    "CollectorConfig",
    "CollectionOutcome",
    "HttpCollector",
    "PriorCapture",
from .adapters import (
    AuthenticatedDownloadStub,
    ClinicalRegulatoryRegistryStub,
    CollectorAdapter,
    HtmlPageAdapter,
    JsonApiAdapter,
    XmlFeedAdapter,
    adapter_for_source,
    build_adapters,
    resolve_adapter,
)
from .credentials import CredentialProvider, StaticCredentialProvider
from .handoff import (
    HandoffBlockedError,
    MonitoringHandoffPayload,
    approve_quarantine_record,
    load_quarantine_record,
    prepare_monitoring_handoff,
    reject_quarantine_record,
from .scheduler import CollectionScheduler, SchedulerConfig
    "AuthenticatedDownloadStub",
    "ClinicalRegulatoryRegistryStub",
    "CollectionScheduler",
    "CollectorAdapter",
    "CredentialProvider",
    "HandoffBlockedError",
    "HtmlPageAdapter",
    "JsonApiAdapter",
    "MonitoringHandoffPayload",
    "SchedulerConfig",
    "StaticCredentialProvider",
    "XmlFeedAdapter",
    "adapter_for_source",
    "approve_quarantine_record",
    "build_adapters",
    "load_quarantine_record",
    "prepare_monitoring_handoff",
    "reject_quarantine_record",
    "resolve_adapter",
]
