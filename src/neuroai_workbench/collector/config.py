from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectorConfig:
    collector_version: str
    configuration_hash: str
    user_agent: str = "NeuroAI-Collector/0.3.0-dev (+https://github.com/fraware/neuroai-workbench)"
    max_response_bytes: int = 10 * 1024 * 1024
    max_redirects: int = 16
    max_decompression_ratio: int = 100
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    total_timeout_seconds: float = 60.0
    max_attempts: int = 3
    requests_per_host_per_minute: int = 30
    allowed_content_types: frozenset[str] = frozenset(
        {
            "text/html",
            "text/plain",
            "application/json",
            "application/xml",
            "text/xml",
            "application/octet-stream",
        }
    )
