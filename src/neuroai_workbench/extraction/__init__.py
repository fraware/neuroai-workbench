"""Offline extraction contract validation, disclosure checks, and benchmark registry."""

from .benchmarks import (
    get_preregistered_metrics,
    get_stop_conditions,
    list_benchmark_fixtures,
    load_benchmark_manifest,
    load_fixture_stub,
    validate_benchmark_manifest,
)
from .contract import (
    EXTRACTION_BOUNDARY,
    EXTRACTION_SCHEMA_VERSION,
    TASK_TYPES,
    compute_excerpt_sha256,
    contract_sha256,
    scan_prompt_injection,
    validate_extraction_request,
    validate_extraction_response,
)
from .disclosure import (
    DEFAULT_DISCLOSURE_POLICY,
    EXPORT_ALLOWED_CLASSES,
    PROTECTED_DISCLOSURE_CLASSES,
    check_context_disclosure,
    check_response_disclosure,
    load_disclosure_policy,
    validate_disclosure_policy,
)
from .disposition import (
    DISPOSITIONS as EXTRACTION_DISPOSITIONS,
)
from .disposition import (
    dispose_extraction_response,
    record_extraction_request,
    record_extraction_response,
    verify_extraction_records,
)
from .evaluation import (
    build_extraction_request_from_capture,
    compare_provider_configs,
    run_bounded_offline_evaluation,
    run_config_against_benchmark,
    score_fixture_response,
)
from .providers import (
    FAKE_OFFLINE_PROVIDER_ID,
    ExtractionProviderConfig,
    FakeOfflineExtractionProvider,
    ProviderExecutionRefusedError,
    contract_fake_offline_configs,
    default_offline_evaluation_configs,
    resolve_provider,
    validate_provider_config,
)

__all__ = [
    "DEFAULT_DISCLOSURE_POLICY",
    "EXPORT_ALLOWED_CLASSES",
    "EXTRACTION_BOUNDARY",
    "EXTRACTION_DISPOSITIONS",
    "EXTRACTION_SCHEMA_VERSION",
    "FAKE_OFFLINE_PROVIDER_ID",
    "PROTECTED_DISCLOSURE_CLASSES",
    "TASK_TYPES",
    "ExtractionProviderConfig",
    "FakeOfflineExtractionProvider",
    "ProviderExecutionRefusedError",
    "build_extraction_request_from_capture",
    "check_context_disclosure",
    "check_response_disclosure",
    "compare_provider_configs",
    "compute_excerpt_sha256",
    "contract_fake_offline_configs",
    "contract_sha256",
    "default_offline_evaluation_configs",
    "dispose_extraction_response",
    "get_preregistered_metrics",
    "get_stop_conditions",
    "list_benchmark_fixtures",
    "load_benchmark_manifest",
    "load_disclosure_policy",
    "load_fixture_stub",
    "record_extraction_request",
    "record_extraction_response",
    "resolve_provider",
    "run_bounded_offline_evaluation",
    "run_config_against_benchmark",
    "scan_prompt_injection",
    "score_fixture_response",
    "validate_benchmark_manifest",
    "validate_disclosure_policy",
    "validate_extraction_request",
    "validate_extraction_response",
    "validate_provider_config",
    "verify_extraction_records",
]
