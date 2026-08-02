from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from .contract import (
    EXTRACTION_BOUNDARY,
    validate_extraction_response,
)

FAKE_OFFLINE_PROVIDER_ID = "fake-offline"
ALLOWED_ENDPOINT_CLASSES = frozenset({"NOT_EXECUTED", "OFFLINE_EXPORT"})
DEFAULT_PROVIDER_REGISTRY: dict[str, str] = {}


class ProviderExecutionRefusedError(ValueError):
    """Raised when a provider adapter is disabled or not approved for execution."""


@dataclass(frozen=True)
class ExtractionProviderConfig:
    config_id: str
    provider_id: str
    model_id: str
    enabled: bool = False
    profile: str = "baseline"
    endpoint_class: str = "NOT_EXECUTED"


@runtime_checkable
class ExtractionProvider(Protocol):
    config: ExtractionProviderConfig

    def extract(self, request: dict[str, Any], *, annotation: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a contract-shaped extraction response without network access."""


def validate_provider_config(config: ExtractionProviderConfig) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not config.config_id.strip():
        errors.append({"code": "CONFIG_INVALID", "path": "config_id", "message": "config_id must be non-empty"})
    if config.endpoint_class not in ALLOWED_ENDPOINT_CLASSES:
        errors.append(
            {
                "code": "NETWORK_REFUSED",
                "path": "endpoint_class",
                "message": f"endpoint_class {config.endpoint_class!r} is not allowed for bounded offline evaluation",
            }
        )
    if config.provider_id not in {FAKE_OFFLINE_PROVIDER_ID} and config.provider_id not in DEFAULT_PROVIDER_REGISTRY:
        errors.append(
            {
                "code": "PROVIDER_UNREGISTERED",
                "path": "provider_id",
                "message": f"provider {config.provider_id!r} is not registered; adapters remain default-off",
            }
        )
    return errors


def resolve_provider(config: ExtractionProviderConfig) -> ExtractionProvider:
    errors = validate_provider_config(config)
    if errors:
        raise ProviderExecutionRefusedError(
            f"Provider configuration refused: {errors[0]['message'] if errors else 'invalid config'}"
        )
    if not config.enabled:
        raise ProviderExecutionRefusedError(
            "Provider adapter is disabled by default; enable explicitly for offline evaluation only."
        )
    if config.provider_id != FAKE_OFFLINE_PROVIDER_ID:
        raise ProviderExecutionRefusedError(
            f"Provider {config.provider_id!r} is not approved for offline execution in this release."
        )
    return FakeOfflineExtractionProvider(config)


class FakeOfflineExtractionProvider:
    """Deterministic offline provider for tests and bounded evaluation only."""

    def __init__(self, config: ExtractionProviderConfig) -> None:
        self.config = config

    def extract(self, request: dict[str, Any], *, annotation: dict[str, Any] | None = None) -> dict[str, Any]:
        excerpts = request.get("selected_excerpts", [])
        if not isinstance(excerpts, list) or not excerpts:
            raise ValueError("Extraction request must include selected_excerpts")
        excerpt = excerpts[0]
        if not isinstance(excerpt, dict):
            raise ValueError("selected_excerpts[0] must be an object")

        expected_fields = []
        expected_abstentions = []
        if isinstance(annotation, dict):
            raw_fields = annotation.get("expected_fields", [])
            raw_abstentions = annotation.get("expected_abstentions", [])
            if isinstance(raw_fields, list):
                expected_fields = [item for item in raw_fields if isinstance(item, dict)]
            if isinstance(raw_abstentions, list):
                expected_abstentions = [item for item in raw_abstentions if isinstance(item, dict)]

        proposed_fields: list[dict[str, Any]] = []
        abstentions: list[dict[str, Any]] = []
        if self.config.profile == "conservative" and expected_abstentions:
            for item in expected_abstentions:
                abstentions.append(
                    {
                        "field_path": f"abstained.{item.get('field_type', 'UNKNOWN').lower()}",
                        "field_type": item.get("field_type"),
                        "abstention_reason": item.get("reason")
                        or "Conservative profile abstains on ambiguous support.",
                        "limitations": ["Requires human adjudication."],
                    }
                )
        else:
            for item in expected_fields:
                value = item.get("value")
                if value is None:
                    continue
                supporting = str(value)
                excerpt_text = str(excerpt.get("text", ""))
                start_offset = excerpt_text.find(supporting)
                if start_offset < 0:
                    supporting = excerpt_text[: max(1, len(excerpt_text) // 2)]
                    start_offset = 0
                end_offset = start_offset + len(supporting)
                proposed_fields.append(
                    {
                        "field_path": f"proposed.{item.get('field_type', 'UNKNOWN').lower()}",
                        "field_type": item.get("field_type"),
                        "value": value,
                        "confidence": "MEDIUM" if self.config.profile == "conservative" else "HIGH",
                        "citation": {
                            "excerpt_id": excerpt.get("excerpt_id"),
                            "excerpt_sha256": excerpt.get("excerpt_sha256"),
                            "supporting_text": supporting,
                            "start_offset": start_offset,
                            "end_offset": end_offset,
                        },
                        "limitations": ["Human disposition is required before any use."],
                    }
                )

        response = {
            "schema_version": "1",
            "request_id": request.get("request_id"),
            "request_sha256": request.get("request_sha256"),
            "task_type": request.get("task_type"),
            "summary": (
                f"Offline fake provider ({self.config.profile}) proposed {len(proposed_fields)} field(s) "
                f"via {self.config.provider_id}/{self.config.model_id}."
            ),
            "proposed_fields": proposed_fields,
            "abstentions": abstentions,
            "warnings": ["Offline fake provider output requires human disposition."],
            "boundary": EXTRACTION_BOUNDARY,
        }
        validation = validate_extraction_response(response, request)
        if not validation["valid"]:
            raise ValueError(f"Fake provider produced invalid response: {validation['errors']}")
        return response


def default_offline_evaluation_configs(*, enabled: bool = True) -> list[ExtractionProviderConfig]:
    """Return two preregistered offline configs for bounded comparison."""
    return [
        ExtractionProviderConfig(
            config_id="CFG-FAKE-BASELINE",
            provider_id=FAKE_OFFLINE_PROVIDER_ID,
            model_id="fake-offline-baseline-v1",
            enabled=enabled,
            profile="baseline",
            endpoint_class="NOT_EXECUTED",
        ),
        ExtractionProviderConfig(
            config_id="CFG-FAKE-CONSERVATIVE",
            provider_id=FAKE_OFFLINE_PROVIDER_ID,
            model_id="fake-offline-conservative-v1",
            enabled=enabled,
            profile="conservative",
            endpoint_class="NOT_EXECUTED",
        ),
    ]


def new_request_id() -> str:
    return f"EXT-{uuid4().hex}"
