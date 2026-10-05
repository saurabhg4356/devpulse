"""Custom exception hierarchy for DevPulse.

All custom errors inherit from DevPulseError, allowing users and services to
differentiate internal domain errors from unexpected system faults.
"""

from typing import Optional


class DevPulseError(Exception):
    """Base exception for all DevPulse errors."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class InvalidRepositoryError(DevPulseError):
    """Raised when the specified target is not a valid Git repository."""
    pass


class GitCommandError(DevPulseError):
    """Raised when a Git command execution fails or Git is missing."""

    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ) -> None:
        super().__init__(message, details=stderr)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr


class InvalidCommitError(DevPulseError):
    """Raised when commit data is malformed or invalid."""
    pass


class AnalysisError(DevPulseError):
    """Raised when an analysis calculation or pipeline fails."""
    pass


class InsufficientDataError(DevPulseError):
    """Raised when there is not enough historical data to perform an analysis."""
    pass


class PredictionError(DevPulseError):
    """Raised when release prediction fails or cannot be computed."""
    pass


class ClassificationError(DevPulseError):
    """Raised when commit classification fails."""
    pass


class ReportGenerationError(DevPulseError):
    """Raised when report or chart rendering fails."""
    pass


class StorageError(DevPulseError):
    """Raised when reading or writing persistence files fails."""
    pass
