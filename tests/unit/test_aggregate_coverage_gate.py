from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.check_aggregate_coverage import (
    AGGREGATE_COVERAGE_FLOOR,
    evaluate_aggregate_coverage,
    load_aggregate_percent,
    main,
)


def _coverage_json(tmp_path: Path, percent_literal: str) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(f'{{"totals":{{"percent_covered":{percent_literal}}}}}', encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ("89.999999", False),
        ("89.80", False),
        ("90.00", True),
        ("90.01", True),
    ],
)
def test_exact_aggregate_threshold(tmp_path: Path, literal: str, expected: bool) -> None:
    passed, observed = evaluate_aggregate_coverage(_coverage_json(tmp_path, literal))
    assert passed is expected
    assert observed == Decimal(literal)
    assert AGGREGATE_COVERAGE_FLOOR == Decimal("90.00")


def test_integer_percentage_is_compared_exactly(tmp_path: Path) -> None:
    passed, observed = evaluate_aggregate_coverage(_coverage_json(tmp_path, "90"))
    assert passed is True
    assert observed == Decimal("90")


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        '{"totals":null}',
        '{"totals":{}}',
        '{"totals":{"percent_covered":"90.00"}}',
        '{"totals":{"percent_covered":true}}',
        '{"totals":{"percent_covered":-0.01}}',
        '{"totals":{"percent_covered":100.01}}',
        "[]",
        "not-json",
    ],
)
def test_missing_or_malformed_aggregate_fails_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        load_aggregate_percent(path)


def test_non_finite_json_numeric_constant_fails_closed(tmp_path: Path) -> None:
    for literal in ("NaN", "Infinity", "-Infinity"):
        path = _coverage_json(tmp_path, literal)
        with pytest.raises(ValueError, match="could not be parsed"):
            load_aggregate_percent(path)


def test_missing_coverage_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing coverage JSON"):
        load_aggregate_percent(tmp_path / "missing.json")


def test_invalid_requested_floor_fails_closed(tmp_path: Path) -> None:
    path = _coverage_json(tmp_path, "95.00")
    with pytest.raises(ValueError, match="coverage floor"):
        evaluate_aggregate_coverage(path, floor=Decimal("100.01"))


def test_cli_reports_exact_observed_value_and_returns_nonzero_below_floor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _coverage_json(tmp_path, "89.80")
    assert main(["--coverage-json", str(path)]) == 1
    captured = capsys.readouterr()
    assert "89.800000%" in captured.out
    assert "required >= 90.00%" in captured.out
    assert "below required 90.00%" in captured.err


def test_cli_passes_at_literal_floor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _coverage_json(tmp_path, "90.00")
    assert main(["--coverage-json", str(path)]) == 0
    captured = capsys.readouterr()
    assert "90.000000%" in captured.out
    assert "aggregate coverage floor passed" in captured.out
