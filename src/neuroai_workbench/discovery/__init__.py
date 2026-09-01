"""Continuous discovery layer: DISCOVERY_QUERY objects and human-gated candidate sources.

Offline-first by default. Opt-in network execution reuses collector SSRF URL policy and
never mutates a live monitor registry without human acceptance and an append-only successor.
"""

from .boundary import DISCOVERY_BOUNDARY, DISCOVERY_NETWORK_ENV, DISCOVERY_SSRF_POLICY
from .clinicaltrials import project_search_pages as project_clinicaltrials_search_pages
from .openfda_registration_listing import project_search_pages as project_openfda_registration_listing_pages
from .errors import (
    DiscoveryAdjudicationRequiredError,
    DiscoveryError,
    DiscoveryNetworkBlockedError,
    DiscoveryOverwriteRefusedError,
)
from .network import network_discovery_allowed, require_network_discovery_allowed, validate_discovery_url
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
    "DiscoveryAdjudicationRequiredError",
    "DiscoveryError",
    "DiscoveryNetworkBlockedError",
    "DiscoveryOverwriteRefusedError",
    "adjudicate_candidate_source",
    "execute_discovery_query",
    "get_fixture_query",
    "get_offline_result_set",
    "initialize_discovery_workspace",
    "list_fixture_queries",
    "load_adjudication",
    "load_proposal",
    "load_query",
    "load_run",
    "load_successor",
    "network_discovery_allowed",
    "project_clinicaltrials_search_pages",
    "project_openfda_registration_listing_pages",
    "refuse_registry_overwrite",
    "require_accepted_proposals_for_successor",
    "require_network_discovery_allowed",
    "seed_fixture_queries",
    "store_query",
    "validate_discovery_url",
]
