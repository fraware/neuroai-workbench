from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from ..util import utc_now
from .adapters.registry import adapter_for_source, build_adapters
from .boundary import COLLECTOR_BOUNDARY
from .config import CollectorConfig
from .credentials import CredentialProvider
from .dns import DnsGuard
from .handoff import prepare_monitoring_handoff
from .http_client import HttpTransport
from .ids import new_request_id
from .schemas import REQUEST_SCHEMA, validate_or_raise
from .url_normalize import group_plan_items_by_retrieval_target


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


@dataclass(frozen=True)
class SchedulerConfig:
    collection_enabled: bool = True
    handoff_enabled: bool = False
    disabled_source_ids: frozenset[str] = frozenset()
    disabled_adapter_ids: frozenset[str] = frozenset()
    include_manual_sources: bool = False


@dataclass
class CollectionScheduler:
    collector_config: CollectorConfig
    transport: HttpTransport
    quarantine_root: Path
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)
    credential_provider: CredentialProvider | None = None
    dns_guard: DnsGuard | None = None

    def build_collection_request(
        self,
        plan_item: dict[str, Any],
        *,
        registry_sha256: str,
    ) -> dict[str, Any]:
        request = {
            "request_id": new_request_id(),
            "source_id": plan_item["source_id"],
            "monitor_id": plan_item["monitor_id"],
            "requested_url": plan_item["url"],
            "requested_at": utc_now(),
            "registry_sha256": registry_sha256,
            "collector_version": self.collector_config.collector_version,
            "configuration_hash": self.collector_config.configuration_hash,
            "boundary": COLLECTOR_BOUNDARY,
        }
        validate_or_raise(request, REQUEST_SCHEMA)
        return request

    def run_plan(
        self,
        plan: dict[str, Any],
        *,
        registry_sha256: str,
        source_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.scheduler_config.collection_enabled:
            return self._killed_run(plan, reason="collection_disabled")

        adapters = build_adapters(
            config=self.collector_config,
            transport=self.transport,
            quarantine_root=self.quarantine_root,
            credential_provider=self.credential_provider,
            dns_guard=self.dns_guard,
        )

        items = list(plan.get("due", []))
        if self.scheduler_config.include_manual_sources:
            items.extend(plan.get("manual", []))

        eligible: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        for item in items:
            source_id = str(item["source_id"])
            if source_id in self.scheduler_config.disabled_source_ids:
                outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "source_kill_switch"})
                continue
            source_record = source_index.get(source_id)
            if source_record is None:
                outcomes.append({"source_id": source_id, "status": "SKIPPED", "reason": "unknown_source"})
                continue
            requested_url = str(item.get("url") or source_record.get("url") or "")
            if not _is_http_url(requested_url):
                outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "FAILURE",
                        "reason": "POLICY_BLOCK",
                        "failure_class": "POLICY_BLOCK",
                        "message": (
                            "Non-HTTP URL cannot enter the HTTP collector path; "
                            "use manual queue or LocalContentAddressedAdapter"
                        ),
                    }
                )
                continue
            adapter = adapter_for_source(adapters, source_record)
            if adapter.adapter_id in self.scheduler_config.disabled_adapter_ids:
                outcomes.append(
                    {
                        "source_id": source_id,
                        "status": "SKIPPED",
                        "reason": "adapter_kill_switch",
                        "adapter_id": adapter.adapter_id,
                    }
                )
                continue
            eligible.append({**item, "url": requested_url})

        groups = group_plan_items_by_retrieval_target(eligible, source_index=source_index)
        retrieval_targets: list[dict[str, Any]] = []
        unique_retrievals = 0
        for group in groups:
            primary_record = source_index[group.primary_source_id]
            adapter = adapter_for_source(adapters, primary_record)
            try:
                request = self.build_collection_request(
                    {
                        "source_id": group.primary_source_id,
                        "monitor_id": group.primary_monitor_id,
                        "url": group.normalized_url
                        if group.normalized_url.startswith(("http://", "https://"))
                        else group.requested_url,
                    },
                    registry_sha256=registry_sha256,
                )
            except (ValueError, TypeError, KeyError) as exc:
                for source_id in group.source_ids:
                    outcomes.append(
                        {
                            "source_id": source_id,
                            "status": "FAILURE",
                            "reason": "POLICY_BLOCK",
                            "failure_class": "POLICY_BLOCK",
                            "message": f"Collection request rejected: {exc}",
                            "retrieval_target_id": group.retrieval_target_id,
                        }
                    )
                retrieval_targets.append(
                    {
                        "retrieval_target_id": group.retrieval_target_id,
                        "normalized_url": group.normalized_url,
                        "source_ids": list(group.source_ids),
                        "http_calls": 0,
                        "status": "POLICY_BLOCK",
                    }
                )
                continue

            outcome = adapter.collect(request)
            unique_retrievals += 1
            record_id = outcome.record.get("result_id") or outcome.record.get("failure_id")
            for source_id in group.source_ids:
                outcomes.append(
                    {
                        "source_id": source_id,
                        "adapter_id": adapter.adapter_id,
                        "status": outcome.kind.upper(),
                        "record_id": record_id,
                        "retrieval_target_id": group.retrieval_target_id,
                        "primary_source_id": group.primary_source_id,
                    }
                )
            retrieval_targets.append(
                {
                    "retrieval_target_id": group.retrieval_target_id,
                    "normalized_url": group.normalized_url,
                    "source_ids": list(group.source_ids),
                    "http_calls": 1,
                    "status": outcome.kind.upper(),
                }
            )

        succeeded = sum(1 for item in outcomes if item["status"] == "RESULT")
        failed = sum(1 for item in outcomes if item["status"] == "FAILURE")
        skipped = sum(1 for item in outcomes if item["status"] == "SKIPPED")
        coalesced_source_count = sum(len(group.source_ids) for group in groups if len(group.source_ids) > 1)
        return {
            "run_id": f"CRUN-{uuid4().hex}",
            "plan_id": plan.get("plan_id"),
            "as_of": plan.get("as_of"),
            "status": "COMPLETED",
            "counts": {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "total": len(outcomes),
                "unique_retrievals": unique_retrievals,
                "retrieval_target_groups": len(groups),
                "coalesced_source_count": coalesced_source_count,
                "logical_sources": len(outcomes) - skipped,
            },
            "retrieval_targets": retrieval_targets,
            "outcomes": outcomes,
            "boundary": COLLECTOR_BOUNDARY,
        }

    def attempt_handoff(self, quarantine_id: str) -> dict[str, Any]:
        if not self.scheduler_config.handoff_enabled:
            raise ValueError("Monitoring handoff kill switch is engaged")
        payload = prepare_monitoring_handoff(self.quarantine_root, quarantine_id)
        return payload.as_dict()

    def _killed_run(self, plan: dict[str, Any], *, reason: str) -> dict[str, Any]:
        return {
            "run_id": f"CRUN-{uuid4().hex}",
            "plan_id": plan.get("plan_id"),
            "as_of": plan.get("as_of"),
            "status": "KILLED",
            "kill_reason": reason,
            "counts": {
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "unique_retrievals": 0,
                "retrieval_target_groups": 0,
                "coalesced_source_count": 0,
                "logical_sources": 0,
            },
            "retrieval_targets": [],
            "outcomes": [],
            "boundary": COLLECTOR_BOUNDARY,
        }
