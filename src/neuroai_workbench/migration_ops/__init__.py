"""Versioned adapters for governing observatory and assessment input migration."""

from .verification import build_migration_verification, write_migration_verification

__all__ = ["build_migration_verification", "write_migration_verification"]
