from __future__ import annotations

import json

import pytest

from neuroai_workbench.temporal import (
    TIME_VALUE_BOUNDARY,
    TemporalValueError,
    dump_time_value,
    parse_time_value,
    time_value_digest,
    time_value_from_json,
)


def test_date_only_round_trip_does_not_fabricate_timestamp() -> None:
    raw = {"value": "2026-08-31", "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}
    parsed = parse_time_value(raw)
    dumped = dump_time_value(parsed)
    assert dumped["value"] == "2026-08-31"
    assert dumped["precision"] == "DATE"
    assert "T" not in dumped["value"]
    again = time_value_from_json(json.dumps(dumped))
    assert again["value"] == "2026-08-31"


def test_year_and_timestamp_and_unknown() -> None:
    year = dump_time_value({"value": "2026", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY})
    assert year["value"] == "2026"
    ts = dump_time_value({"value": "2026-08-31T12:00:00Z", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY})
    assert ts["precision"] == "TIMESTAMP"
    unknown = dump_time_value({"value": None, "precision": "UNKNOWN", "boundary": TIME_VALUE_BOUNDARY})
    assert unknown["value"] is None


def test_precision_preserved_and_mismatch_rejected() -> None:
    with pytest.raises(TemporalValueError, match="four-digit"):
        parse_time_value({"value": "2026-01-01", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="fabricate"):
        parse_time_value({"value": "2026-08-31T00:00:00Z", "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="promote"):
        parse_time_value({"value": "2026-08-31", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY})


def test_unknown_enum_rejected() -> None:
    with pytest.raises(TemporalValueError, match="Unknown TimeValue precision"):
        parse_time_value({"value": "2026", "precision": "MONTH", "boundary": TIME_VALUE_BOUNDARY})


def test_digest_determinism() -> None:
    left = {"value": "2024", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY}
    right = {"boundary": TIME_VALUE_BOUNDARY, "precision": "YEAR", "value": "2024"}
    assert time_value_digest(left) == time_value_digest(right)


def test_unknown_cannot_carry_value_and_extra_fields_rejected() -> None:
    with pytest.raises(TemporalValueError, match="null"):
        parse_time_value({"value": "2026", "precision": "UNKNOWN", "boundary": TIME_VALUE_BOUNDARY})
    with pytest.raises(TemporalValueError, match="unsupported fields"):
        parse_time_value({"value": "2026", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY, "tz": "UTC"})
    from neuroai_workbench.temporal.time_value import is_time_value

    assert is_time_value({"value": "2026", "precision": "YEAR", "boundary": TIME_VALUE_BOUNDARY})
    assert not is_time_value("2026")
