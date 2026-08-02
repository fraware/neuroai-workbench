from __future__ import annotations


class DeltaError(Exception):
    """Base error for adjudicated delta operations."""


class DeltaValidationError(DeltaError):
    """Schema or semantic validation failed."""


class DeltaCompileError(DeltaError):
    """Compilation from refresh package to delta failed."""


class DeltaApplyError(DeltaError):
    """Fail-closed delta application rejected the operation."""
