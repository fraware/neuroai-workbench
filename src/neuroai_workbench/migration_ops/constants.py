from __future__ import annotations

SCHEMA_VERSION = "1.0"
RULESET_ID = "GOVERNING-INPUT-MIGRATION-v1"
ADAPTER_VERSION = "1"

BOUNDARY = (
    "Governing-input migration records storage lineage, digests, and adapter outcomes only. "
    "It does not validate substantive claims, confer authorization, or establish conformance."
)

ACCESS_ACCESSIBLE = "ACCESSIBLE"
ACCESS_INACCESSIBLE = "INACCESSIBLE"
ACCESS_NOT_RECORDED = "NOT_RECORDED"
ACCESS_UNKNOWN = "UNKNOWN"

MIGRATION_MIGRATED = "MIGRATED"
MIGRATION_BLOCKED = "BLOCKED"
MIGRATION_SKIPPED = "SKIPPED"

DISPOSITION_PENDING = "PENDING_REVIEW"
DISPOSITION_ACKNOWLEDGED = "ACKNOWLEDGED"
DISPOSITION_DEFERRED = "DEFERRED"

FAMILY_OBSERVATORY_V1_4 = "OBSERVATORY_V1_4"
FAMILY_OBSERVATORY_V1_6 = "OBSERVATORY_V1_6"
FAMILY_OBSERVATORY_V1_7 = "OBSERVATORY_V1_7"
FAMILY_ASSESSMENT_V4_2 = "ASSESSMENT_V4_2"
FAMILY_SOURCE_REGISTRY = "SOURCE_REGISTRY"
FAMILY_PROGRAMME_ADAPTER = "PROGRAMME_ADAPTER"
FAMILY_EXTERNAL_ARCHIVE = "EXTERNAL_ARCHIVE"
FAMILY_POLICY = "POLICY"

FAMILY_ADAPTER_IDS = {
    FAMILY_OBSERVATORY_V1_4: "observatory-v1.4-adapter",
    FAMILY_OBSERVATORY_V1_6: "observatory-v1.6-inaccessible-adapter",
    FAMILY_OBSERVATORY_V1_7: "observatory-v1.7-adapter",
    FAMILY_ASSESSMENT_V4_2: "assessment-v4.2-adapter",
    FAMILY_SOURCE_REGISTRY: "source-registry-adapter",
    FAMILY_PROGRAMME_ADAPTER: "programme-adapter-input-adapter",
    FAMILY_EXTERNAL_ARCHIVE: "external-archive-adapter",
    FAMILY_POLICY: "policy-adapter",
}

INACCESSIBLE_ARCHIVE_KEYS = frozenset(
    {
        "external/archive/observatory_v1.6_live_refresh_delta.json",
        "external/archive/SOURCE_MONITOR_REGISTRY_v1.5.json",
        "external/archive/combined_observatory_workbook.xlsx",
        "external/NeuroAI_Operations_Starter_v0.1.0.zip",
    }
)
