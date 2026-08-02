"""Shadow refresh evaluation scaffolding for non-canonical operational rehearsal."""

from .cohort import (
    bind_reviewed_cohort_to_registry,
    discover_cohort_candidates,
    load_reviewed_cohort_manifest,
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
    "SHADOW_EVALUATION_STATUS",
    "SHADOW_REFRESH_BOUNDARY",
    "bind_reviewed_cohort_to_registry",
    "compute_go_no_go_metrics",
    "discover_cohort_candidates",
    "load_reviewed_cohort_manifest",
    "validate_shadow_artifact_status",
    "validate_shadow_refresh_cohort",
    "validate_shadow_refresh_freeze_manifest",
    "validate_shadow_refresh_go_no_go_metrics",
    "validate_shadow_refresh_run_results",
]
