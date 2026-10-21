#!/usr/bin/env python3
"""Measure frozen discovery-schema validation overhead on synthetic invalid inputs.

Usage: python scripts/benchmark_discovery_schema_validation.py --iterations 100 --repeats 5

This measures repeated schema loading/validator creation versus cached schema
validation. Timing results are local measurements, not field-workload estimates.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Callable
from typing import Any

from jsonschema import Draft202012Validator

import neuroai_workbench.product_discovery_frames as discovery

SCHEMAS: dict[str, str] = {
    "frame": discovery.FRAME_SCHEMA,
    "capture": discovery.CAPTURE_SCHEMA,
    "run": discovery.RUN_SCHEMA,
    "universe": discovery.ANALYSIS_UNIVERSE_SCHEMA,
}


def uncached_errors(value: Any, schema_name: str) -> list[str]:
    """Reconstruct exactly the former per-call compilation path."""
    validator = Draft202012Validator(discovery._schema(schema_name))
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def elapsed_microseconds_per_call(fn: Callable[[], list[str]], *, iterations: int) -> float:
    start = time.perf_counter_ns()
    for _ in range(iterations):
        fn()
    return (time.perf_counter_ns() - start) / (iterations * 1_000.0)


def run_benchmark(schema_name: str, *, iterations: int, repeats: int) -> dict[str, Any]:
    """Check semantic equivalence before reporting paired median timings."""
    value: dict[str, Any] = {}  # Synthetic and intentionally invalid.

    def baseline() -> list[str]:
        return uncached_errors(value, schema_name)

    def cached() -> list[str]:
        return discovery._schema_errors(value, schema_name)

    discovery._compiled_schema_validator.cache_clear()
    expected, observed = baseline(), cached()
    if not expected or expected != observed:
        raise RuntimeError("Schema diagnostics differed or synthetic input was unexpectedly accepted")

    # Use alternating measurement order to reduce systematic warm/cold bias.
    samples_uncached: list[float] = []
    samples_cached: list[float] = []
    for repeat in range(repeats):
        if repeat % 2 == 0:
            samples_uncached.append(elapsed_microseconds_per_call(baseline, iterations=iterations))
            samples_cached.append(elapsed_microseconds_per_call(cached, iterations=iterations))
        else:
            samples_cached.append(elapsed_microseconds_per_call(cached, iterations=iterations))
            samples_uncached.append(elapsed_microseconds_per_call(baseline, iterations=iterations))
    median_uncached = statistics.median(samples_uncached)
    median_cached = statistics.median(samples_cached)
    return {
        "schema": schema_name,
        "iterations_per_repeat": iterations,
        "repeats": repeats,
        "input": "synthetic-empty-object",
        "invalid_diagnostic_count": len(expected),
        "diagnostics_identical": True,
        "median_uncached_microseconds_per_call": round(median_uncached, 3),
        "median_cached_microseconds_per_call": round(median_cached, 3),
        "observed_ratio_uncached_to_cached": round(median_uncached / median_cached, 3) if median_cached else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", choices=[*SCHEMAS, "all"], default="all")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.repeats < 1:
        parser.error("iterations and repeats must be positive")
    selected = SCHEMAS if args.schema == "all" else {args.schema: SCHEMAS[args.schema]}
    rows = [
        {"schema_key": key, **run_benchmark(name, iterations=args.iterations, repeats=args.repeats)}
        for key, name in selected.items()
    ]
    print(json.dumps({"benchmark": "discovery-schema-compiled-validator", "results": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
