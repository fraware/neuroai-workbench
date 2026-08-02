"""Shadow refresh evaluation scaffolding for non-canonical operational rehearsal."""

from .cohort import (
    bind_reviewed_cohort_to_registry,
    discover_cohort_candidates,
    load_reviewed_cohort_manifest,
)
from .live import (
    LIVE_COLLECTION_ENV,
    evaluation_collection_plan,
    live_collection_enabled,
    observed_run_results_from_live,
    require_live_collection_enabled,
    run_live_cohort_collection,
)
from .metrics import compute_go_no_go_metrics
from .schemas import (
    DEFAULT_GO_NO_GO_THRESHOLDS,
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
    validate_shadow_artifact_status,
    validate_shadow_refresh_cohort,
    validate_shadow_refresh_freeze_manifest,
    validate_shadow_refresh_go_no_go_metrics,
    validate_shadow_refresh_run_results,
)

__all__ = [
    "DEFAULT_GO_NO_GO_THRESHOLDS",
    "LIVE_COLLECTION_ENV",
    "SHADOW_EVALUATION_STATUS",
    "SHADOW_REFRESH_BOUNDARY",
    "bind_reviewed_cohort_to_registry",
    "compute_go_no_go_metrics",
    "discover_cohort_candidates",
    "evaluation_collection_plan",
    "live_collection_enabled",
    "load_reviewed_cohort_manifest",
    "observed_run_results_from_live",
    "require_live_collection_enabled",
    "run_live_cohort_collection",
    "validate_shadow_artifact_status",
    "validate_shadow_refresh_cohort",
    "validate_shadow_refresh_freeze_manifest",
    "validate_shadow_refresh_go_no_go_metrics",
    "validate_shadow_refresh_run_results",
]
