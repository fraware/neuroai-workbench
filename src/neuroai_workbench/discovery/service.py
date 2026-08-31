from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .workflow import execute_discovery_query


class DiscoveryService:
    """Thin facade over execute_discovery_query. Does not embed an HTTP client."""

    def run(
        self,
        workspace: Path,
        query_id: str,
        *,
        actor: str = "local-user",
        execution_mode: str = "OFFLINE_FIXTURE",
        result_records: list[Mapping[str, Any]] | None = None,
        known_sources: list[Mapping[str, Any]] | None = None,
        executed_at: str | None = None,
    ) -> dict[str, Any]:
        return execute_discovery_query(
            workspace,
            query_id,
            actor=actor,
            execution_mode=execution_mode,
            result_records=result_records,
            known_sources=known_sources,
            executed_at=executed_at,
        )
