"""Continuous discovery layer: DISCOVERY_QUERY objects and human-gated candidate sources.

Offline-first by default. Opt-in network execution reuses collector SSRF URL policy and
never mutates a live monitor registry without human acceptance and an append-only successor.
"""

from .boundary import DISCOVERY_BOUNDARY, DISCOVERY_NETWORK_ENV, DISCOVERY_SSRF_POLICY
from .clinicaltrials import project_search_pages as project_clinicaltrials_search_pages
from .epo_ops import project_search_pages as project_epo_ops_search_pages
from .europepmc import project_search_pages as project_europepmc_search_pages
from .errors import (
    DiscoveryAdjudicationRequiredError,
    DiscoveryError,
    DiscoveryNetworkBlockedError,
    DiscoveryOverwriteRefusedError,
)
from .network import network_discovery_allowed, require_network_discovery_allowed, validate_discovery_url
from .nih_reporter import project_search_pages as project_nih_reporter_search_pages
from .openfda_510k import project_search_pages as project_openfda_510k_pages
from .openfda_device_event import project_search_pages as project_openfda_device_event_pages
from .openfda_hde import project_search_pages as project_openfda_hde_pages
from .openfda_pma import project_search_pages as project_openfda_pma_pages
from .openfda_recall import project_search_pages as project_openfda_device_recall_pages
from .programme import (
    OFFLINE_EXECUTABLE_UNIVERSE_IDS,
    SU_TRIAL_DOC_ALIAS,
    SU_TRIAL_ID,
    list_programme_ids,
    load_first_wave_programmes,
    load_programme,
    load_su_trial_programme,
    programme_maturity,
    run_source_universe,
    validate_programme,
)
from .service import DiscoveryService
from .store import (
    EXPECTED_FIXTURE_QUERY_IDS,
    get_fixture_query,
    get_offline_result_set,
    initialize_discovery_workspace,
    list_fixture_queries,
    load_adjudication,
    load_proposal,
    load_query,
    load_run,
    load_successor,
    seed_fixture_queries,
    store_query,
)
from .universe_projection import project_universe_pages
from .workflow import (
    adjudicate_candidate_source,
    execute_discovery_query,
    refuse_registry_overwrite,
    require_accepted_proposals_for_successor,
)

__all__ = [
    "DISCOVERY_BOUNDARY",
    "DISCOVERY_NETWORK_ENV",
    "DISCOVERY_SSRF_POLICY",
    "EXPECTED_FIXTURE_QUERY_IDS",
    "OFFLINE_EXECUTABLE_UNIVERSE_IDS",
    "SU_TRIAL_DOC_ALIAS",
    "SU_TRIAL_ID",
    "DiscoveryAdjudicationRequiredError",
    "DiscoveryError",
    "DiscoveryNetworkBlockedError",
    "DiscoveryOverwriteRefusedError",
    "DiscoveryService",
    "adjudicate_candidate_source",
    "execute_discovery_query",
    "get_fixture_query",
    "get_offline_result_set",
    "initialize_discovery_workspace",
    "list_fixture_queries",
    "list_programme_ids",
    "load_adjudication",
    "load_first_wave_programmes",
    "load_proposal",
    "load_programme",
    "load_query",
    "load_run",
    "load_su_trial_programme",
    "load_successor",
    "network_discovery_allowed",
    "programme_maturity",
    "project_clinicaltrials_search_pages",
    "project_epo_ops_search_pages",
    "project_europepmc_search_pages",
    "project_nih_reporter_search_pages",
    "project_openfda_510k_pages",
    "project_openfda_device_event_pages",
    "project_openfda_device_recall_pages",
    "project_openfda_hde_pages",
    "project_openfda_pma_pages",
    "project_universe_pages",
    "refuse_registry_overwrite",
    "require_accepted_proposals_for_successor",
    "require_network_discovery_allowed",
    "run_source_universe",
    "seed_fixture_queries",
    "store_query",
    "validate_discovery_url",
    "validate_programme",
]
