class WorkbenchError(Exception):
    """Base error raised for controlled workbench failures."""


class WorkspaceError(WorkbenchError):
    """Raised for invalid workspace or case operations."""


class ValidationFailure(WorkbenchError):
    """Raised when an assessment fails a required validation gate."""
