"""Regression tests for reusing immutable Release-A discovery schema validators."""

from __future__ import annotations

import neuroai_workbench.product_discovery_frames as discovery


def test_repeated_validation_reuses_compiled_schema(monkeypatch) -> None:
    """Cache schema compilation while leaving invalid-instance diagnostics unchanged."""
    original_loader = discovery._schema
    loaded: list[str] = []

    def tracking_loader(name: str) -> dict[str, object]:
        loaded.append(name)
        return original_loader(name)

    monkeypatch.setattr(discovery, "_schema", tracking_loader)
    discovery._compiled_schema_validator.cache_clear()
    try:
        invalid_frame: dict[str, object] = {}
        first = discovery._schema_errors(invalid_frame, discovery.FRAME_SCHEMA)
        second = discovery._schema_errors(invalid_frame, discovery.FRAME_SCHEMA)

        assert first
        assert first == second
        assert loaded == [discovery.FRAME_SCHEMA]
        assert discovery._compiled_schema_validator.cache_info().hits == 1
    finally:
        discovery._compiled_schema_validator.cache_clear()


def test_compiled_validator_cache_is_keyed_by_schema_name(monkeypatch) -> None:
    """Distinct frozen schemas must retain independent validation contracts."""
    original_loader = discovery._schema
    loaded: list[str] = []

    def tracking_loader(name: str) -> dict[str, object]:
        loaded.append(name)
        return original_loader(name)

    monkeypatch.setattr(discovery, "_schema", tracking_loader)
    discovery._compiled_schema_validator.cache_clear()
    try:
        schema_names = (
            discovery.FRAME_SCHEMA,
            discovery.CAPTURE_SCHEMA,
            discovery.RUN_SCHEMA,
            discovery.ANALYSIS_UNIVERSE_SCHEMA,
        )
        for schema_name in schema_names:
            first = discovery._schema_errors({}, schema_name)
            assert first == discovery._schema_errors({}, schema_name)

        assert loaded == list(schema_names)
        assert discovery._compiled_schema_validator.cache_info().misses == len(schema_names)
        assert discovery._compiled_schema_validator.cache_info().hits == len(schema_names)
    finally:
        discovery._compiled_schema_validator.cache_clear()
