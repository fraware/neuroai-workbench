from __future__ import annotations

from .auth_download import AuthenticatedDownloadStub
from .base import CollectorAdapter, HttpCollectorAdapter
from .html import HtmlPageAdapter
from .json_api import JsonApiAdapter
from .registry import ADAPTER_ORDER, adapter_for_source, build_adapters, resolve_adapter
from .registry_stub import REGISTRY_STUB_BODY, ClinicalRegulatoryRegistryStub
from .xml_feed import XmlFeedAdapter

__all__ = [
    "ADAPTER_ORDER",
    "AuthenticatedDownloadStub",
    "ClinicalRegulatoryRegistryStub",
    "CollectorAdapter",
    "HtmlPageAdapter",
    "HttpCollectorAdapter",
    "JsonApiAdapter",
    "REGISTRY_STUB_BODY",
    "XmlFeedAdapter",
    "adapter_for_source",
    "build_adapters",
    "resolve_adapter",
]
