"""Hardened HTTP collector core with quarantine-only writes."""

from .acquisition_policy import (
    FALLBACK_FORBID,
    FALLBACK_PRIOR_CAPTURE,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    POLICY_BOUNDARY,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    acquisition_policy_digest,
    build_acquisition_policy,
    canonicalize_policy_origin,
    canonicalize_requested_origin,
    require_acquisition_policy,
    validate_acquisition_policy,
)
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
from .policy_execution import POLICY_EXECUTION_BOUNDARY, PolicyBoundCollectionScheduler, PolicyExecutionBlocked
from .scheduler import CollectionScheduler, SchedulerConfig
from .service import CollectionOutcome, HttpCollector, PriorCapture

__all__ = [
    "AcquisitionPolicyError",
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
    "FALLBACK_FORBID",
    "FALLBACK_PRIOR_CAPTURE",
    "FdaDeviceAdapter",
    "HandoffBlockedError",
    "HtmlPageAdapter",
    "HttpCollector",
    "JsonApiAdapter",
    "LocalContentAddressedAdapter",
    "MonitoringHandoffPayload",
    "ONLINE_PREFERRED",
    "ONLINE_REQUIRED",
    "POLICY_BOUNDARY",
    "POLICY_EXECUTION_BOUNDARY",
    "PinnedSocketHttpTransport",
    "PolicyBoundCollectionScheduler",
    "PolicyExecutionBlocked",
    "PriorCapture",
    "QuarantineService",
    "REPLAY_ONLY",
    "SchedulerConfig",
    "StaticCredentialProvider",
    "XmlFeedAdapter",
    "acquisition_policy_digest",
    "adapter_for_source",
    "approve_quarantine_record",
    "build_acquisition_policy",
    "build_adapters",
    "canonicalize_policy_origin",
    "canonicalize_requested_origin",
    "load_quarantine_record",
    "prepare_monitoring_handoff",
    "reject_quarantine_record",
    "require_acquisition_policy",
    "resolve_adapter",
    "validate_acquisition_policy",
]
