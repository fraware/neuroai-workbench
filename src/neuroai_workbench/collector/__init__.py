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
from .authorization import CollectionAuthorizationError
from .collection_service import EvidenceCollectionService, QuarantineService
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
from .pinned_transport import PinnedSocketHttpTransport
from .scheduler import CollectionScheduler, SchedulerConfig
from .service import CollectionOutcome, HttpCollector, PriorCapture

__all__ = [
    "AuthenticatedDownloadStub",
    "ClinicalRegulatoryHttpCaptureAdapter",
    "ClinicalRegulatoryRegistryStub",
    "ClinicalTrialsGovAdapter",
    "CollectionAuthorizationError",
    "CollectionOutcome",
    "CollectionScheduler",
    "CollectorAdapter",
    "CollectorConfig",
    "CredentialProvider",
    "EvidenceCollectionService",
    "FdaDeviceAdapter",
    "HandoffBlockedError",
    "HtmlPageAdapter",
    "HttpCollector",
    "JsonApiAdapter",
    "LocalContentAddressedAdapter",
    "MonitoringHandoffPayload",
    "PinnedSocketHttpTransport",
    "PriorCapture",
    "QuarantineService",
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
