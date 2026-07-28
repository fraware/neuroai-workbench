# ADR 0002 — Filesystem-backed controlled workspaces

**Status:** Accepted

Cases use transparent JSON, JSONL and content-addressed files. This supports inspection, portability, backups and reproducible exports.

The filesystem remains protected only by host controls. A database or object store may be added in future deployment profiles without changing the canonical assessment semantics.
