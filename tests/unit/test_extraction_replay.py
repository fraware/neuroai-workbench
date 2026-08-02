from __future__ import annotations

from neuroai_workbench.extraction.contract import EXTRACTION_BOUNDARY
from neuroai_workbench.extraction.providers import (
    CAPTURED_REPLAY_PROVIDER_ID,
    captured_replay_evaluation_config,
    resolve_provider,
)


def test_captured_response_replay_provider_replays_fixture() -> None:
    config = captured_replay_evaluation_config(enabled=True)
    request_id = "EXT-" + ("a" * 32)
    excerpt_id = "EX-" + ("b" * 32)
    request = {
        "schema_version": "1",
        "request_id": request_id,
        "request_sha256": "a" * 64,
        "task_type": "EXTRACT_ENTITY_MENTIONS",
        "selected_excerpts": [
            {
                "excerpt_id": excerpt_id,
                "excerpt_sha256": "b" * 64,
                "text": "Science Corporation announced a PRIMA update.",
            }
        ],
        "boundary": EXTRACTION_BOUNDARY,
    }
    captured = {
        request_id: {
            "schema_version": "1",
            "request_id": request_id,
            "request_sha256": "a" * 64,
            "task_type": "EXTRACT_ENTITY_MENTIONS",
            "summary": "Captured replay proposed one organization name.",
            "proposed_fields": [
                {
                    "field_path": "proposed.entity_mention",
                    "field_type": "ENTITY_MENTION",
                    "value": "Science Corporation",
                    "confidence": "MEDIUM",
                    "citation": {
                        "excerpt_id": excerpt_id,
                        "excerpt_sha256": "b" * 64,
                        "supporting_text": "Science Corporation",
                        "start_offset": 0,
                        "end_offset": 19,
                    },
                    "limitations": ["Human disposition required."],
                }
            ],
            "abstentions": [],
            "warnings": ["Captured replay; not a live model call."],
            "boundary": EXTRACTION_BOUNDARY,
        }
    }
    provider = resolve_provider(config, captured_responses=captured)
    assert provider.config.provider_id == CAPTURED_REPLAY_PROVIDER_ID
    response = provider.extract(request)
    assert response["proposed_fields"][0]["value"] == "Science Corporation"
