"""Hardened HTTP collector core with quarantine-only writes."""

from .adapters import (
    AuthenticatedDownloadStub,
    ClinicalRegulatoryHttpCaptureAdapter,
    ClinicalRegulatoryRegistryStub,
    ClinicalTrialsGovAdapter,
    CollectorAdapter,
    FdaDeviceAdapter,
    HtmlPageAdapter,
    JsonApiAdapter,
    XmlFeedAdapter,
    adapter_for_source,
    build_adapters,
    resolve_adapter,
)
from .config import CollectorConfig
from .credentials import CredentialProvider, StaticCredentialProvider
from .handoff import (
    HandoffBlockedError,
    MonitoringHandoffPayload,
    approve_quarantine_record,
    load_quarantine_record,
    prepare_monitoring_handoff,
    reject_quarantine_record,
)
from .local_adapter import LocalContentAddressedAdapter
from .scheduler import CollectionScheduler, SchedulerConfig
from .service import CollectionOutcome, HttpCollector, PriorCapture

__all__ = [
    "AuthenticatedDownloadStub",
    "ClinicalRegulatoryHttpCaptureAdapter",
    "ClinicalRegulatoryRegistryStub",
    "ClinicalTrialsGovAdapter",
    "CollectionOutcome",
    "CollectionScheduler",
    "CollectorAdapter",
    "CollectorConfig",
    "CredentialProvider",
    "FdaDeviceAdapter",
    "HandoffBlockedError",
    "HtmlPageAdapter",
    "HttpCollector",
    "JsonApiAdapter",
    "LocalContentAddressedAdapter",
    "MonitoringHandoffPayload",
    "PriorCapture",
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
