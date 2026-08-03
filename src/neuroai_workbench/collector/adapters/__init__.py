from __future__ import annotations

from .auth_download import AuthenticatedDownloadStub
from .base import CollectorAdapter, HttpCollectorAdapter
from .clinicaltrials import ClinicalTrialsGovAdapter
from .eu_ctis import EuCtisAdapter
from .fda_device import FdaDeviceAdapter
from .fda_maude import FdaMaudeAdapter
from .fda_recall import FdaRecallAdapter
from .html import HtmlPageAdapter
from .json_api import JsonApiAdapter
from .neuroscience_archive import NeuroscienceArchiveAdapter
from .patents_grants import PatentsGrantsAdapter
from .pubmed import PubmedCrossrefAdapter
from .registry import ADAPTER_ORDER, adapter_for_source, build_adapters, resolve_adapter
from .registry_stub import (
    REGISTRY_STUB_BODY,
    ClinicalRegulatoryHttpCaptureAdapter,
    ClinicalRegulatoryRegistryStub,
)
from .structured import (
    NORMALIZED_DEVICE_SCHEMA,
    NORMALIZED_PUBLICATION_SCHEMA,
    NORMALIZED_STUDY_SCHEMA,
    STRUCTURED_ADAPTER_CONTRACT_SCHEMA,
    ScaffoldAdapter,
    load_adapter_contract,
)
from .who_ictrp import WhoIctrpAdapter
from .xml_feed import XmlFeedAdapter

__all__ = [
    "ADAPTER_ORDER",
    "NORMALIZED_DEVICE_SCHEMA",
    "NORMALIZED_PUBLICATION_SCHEMA",
    "NORMALIZED_STUDY_SCHEMA",
    "STRUCTURED_ADAPTER_CONTRACT_SCHEMA",
    "AuthenticatedDownloadStub",
    "ClinicalRegulatoryHttpCaptureAdapter",
    "ClinicalRegulatoryRegistryStub",
    "ClinicalTrialsGovAdapter",
    "CollectorAdapter",
    "EuCtisAdapter",
    "FdaDeviceAdapter",
    "FdaMaudeAdapter",
    "FdaRecallAdapter",
    "HtmlPageAdapter",
    "HttpCollectorAdapter",
    "JsonApiAdapter",
    "NeuroscienceArchiveAdapter",
    "PatentsGrantsAdapter",
    "PubmedCrossrefAdapter",
    "REGISTRY_STUB_BODY",
    "ScaffoldAdapter",
    "WhoIctrpAdapter",
    "XmlFeedAdapter",
    "adapter_for_source",
    "build_adapters",
    "load_adapter_contract",
    "resolve_adapter",
]
