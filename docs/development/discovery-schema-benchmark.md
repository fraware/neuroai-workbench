# Discovery schema-validation microbenchmark

The Product Discovery component uses four immutable, package-bundled JSON Schemas.
The benchmark in `scripts/benchmark_discovery_schema_validation.py` measures
repeated schema loading/validator construction against cached validators, using
synthetic invalid `{}` inputs. It checks exact diagnostic equivalence before timing.

Run from an editable developer environment:

```bash
python scripts/benchmark_discovery_schema_validation.py --iterations 100 --repeats 5
python scripts/benchmark_discovery_schema_validation.py --schema capture --iterations 1000 --repeats 7
```

The JSON output provides paired per-call medians and the observed uncached/cached
ratio. Record Python version, operating system, CPU, dependency lock revision,
git commit, and invocation when comparing revisions. First establish a
pre-optimization baseline on the same host and environment.

**Scope:** this microbenchmark measures schema-validation overhead only.
It does not measure complete Release-A discovery throughput, remote-source
collection, identity adjudication, correctness of scientific conclusions, or
workloads with realistically structured capture records. Timings are not
release criteria. The smoke test checks valid output and semantic equivalence,
without asserting a speedup or a machine-specific latency threshold.
