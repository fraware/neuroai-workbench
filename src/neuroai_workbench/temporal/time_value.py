from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from ..util import canonical_json_bytes, sha256_bytes

Precision = Literal["YEAR", "DATE", "TIMESTAMP", "UNKNOWN"]

PRECISIONS = frozenset({"YEAR", "DATE", "TIMESTAMP", "UNKNOWN"})
TIME_VALUE_BOUNDARY = (
    "A TimeValue records calendar or clock precision only. YEAR and DATE values must round-trip "
    "without fabricating a timestamp. UNKNOWN is unresolved, not a default epoch."
)


class TemporalValueError(ValueError):
    """Raised when a TimeValue cannot be parsed or would fabricate precision."""


def _require_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemporalValueError("TimeValue must be an object")
    return value


def parse_time_value(value: Any) -> dict[str, Any]:
    """Return a schema-shaped TimeValue dict. Date-only values are not promoted to timestamps."""
    record = _require_mapping(value)
    precision_raw = record.get("precision")
    if precision_raw not in PRECISIONS:
        raise TemporalValueError(f"Unknown TimeValue precision {precision_raw!r}")
    precision: Precision = precision_raw
    raw = record.get("value")
    extra = {key: item for key, item in record.items() if key not in {"value", "precision", "boundary"}}
    if extra:
        raise TemporalValueError(f"TimeValue contains unsupported fields: {sorted(extra)}")

    if precision == "UNKNOWN":
        if raw is not None:
            raise TemporalValueError("UNKNOWN TimeValue must use value null; do not encode a guessed instant")
        return _finalize(None, "UNKNOWN")

    if not isinstance(raw, str) or not raw.strip():
        raise TemporalValueError(f"{precision} TimeValue requires a non-empty string value")
    text = raw.strip()

    if precision == "YEAR":
        if len(text) != 4 or not text.isdigit():
            raise TemporalValueError("YEAR TimeValue must be a four-digit calendar year, not a date or timestamp")
        year = int(text)
        if year < 1 or year > 9999:
            raise TemporalValueError("YEAR TimeValue is out of range")
        return _finalize(text, "YEAR")

    if precision == "DATE":
        if "T" in text or " " in text or text.endswith("Z") or "+" in text[10:]:
            raise TemporalValueError(
                "DATE TimeValue must be YYYY-MM-DD without a time component; do not fabricate T00:00:00Z"
            )
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise TemporalValueError("DATE TimeValue must be a real calendar date in YYYY-MM-DD form") from exc
        round_trip = parsed.strftime("%Y-%m-%d")
        if round_trip != text:
            raise TemporalValueError("DATE TimeValue must round-trip without normalization side effects")
        return _finalize(text, "DATE")

    # TIMESTAMP
    if "T" not in text:
        raise TemporalValueError("TIMESTAMP TimeValue must include a date-time separator T; do not promote a date")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed_ts = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TemporalValueError("TIMESTAMP TimeValue must be RFC 3339 / ISO 8601 with an explicit offset") from exc
    if parsed_ts.tzinfo is None or parsed_ts.utcoffset() is None:
        raise TemporalValueError("TIMESTAMP TimeValue must include an explicit timezone")
    return _finalize(text, "TIMESTAMP")


def _finalize(value: str | None, precision: Precision) -> dict[str, Any]:
    record = {"value": value, "precision": precision, "boundary": TIME_VALUE_BOUNDARY}
    return record


def dump_time_value(value: Any) -> dict[str, Any]:
    """Canonical dump used for persistence. Round-trips DATE and YEAR without timestamp invention."""
    parsed = parse_time_value(value)
    return {"value": parsed["value"], "precision": parsed["precision"], "boundary": parsed["boundary"]}


def time_value_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(dump_time_value(value)))


def is_time_value(value: Any) -> bool:
    try:
        parse_time_value(value)
    except (TypeError, TemporalValueError):
        return False
    return True


# Keep json import available for schema-adjacent tests without a second object model.
def time_value_from_json(text: str) -> dict[str, Any]:
    loaded = json.loads(text)
    return dump_time_value(loaded)
