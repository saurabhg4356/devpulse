"""Input validation utilities for DevPulse."""

import re
from pathlib import Path
from typing import Any, Union
from models.exceptions import InvalidCommitError, InvalidRepositoryError


_GIT_HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{4,40}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_repository_path(path: Union[str, Path]) -> Path:
    """Validate that the provided path exists and is a directory.
    
    Args:
        path: Path to target repository.
        
    Returns:
        Resolved Path object.
        
    Raises:
        InvalidRepositoryError: If path does not exist or is not a directory.
    """
    repo_path = Path(path).resolve()
    if not repo_path.exists():
        raise InvalidRepositoryError(f"Repository path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise InvalidRepositoryError(f"Repository path is not a directory: {repo_path}")
    return repo_path


def validate_commit_hash(commit_hash: str) -> str:
    """Validate that a string is a valid Git commit hash.
    
    Args:
        commit_hash: SHA-1 hex string.
        
    Returns:
        Stripped lower-case hash string.
        
    Raises:
        InvalidCommitError: If hash is malformed.
    """
    if not isinstance(commit_hash, str):
        raise InvalidCommitError(f"Commit hash must be a string, got {type(commit_hash).__name__}")
    cleaned = commit_hash.strip().lower()
    if not _GIT_HASH_PATTERN.match(cleaned):
        raise InvalidCommitError(f"Invalid Git commit hash format: '{commit_hash}'")
    return cleaned


def validate_non_negative_int(value: Any, name: str = "value") -> int:
    """Validate that value is a non-negative integer.
    
    Args:
        value: Numeric value to check.
        name: Parameter name for error messages.
        
    Returns:
        Integer value.
        
    Raises:
        ValueError: If value is negative or cannot be converted to int.
    """
    try:
        val = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} must be an integer, got {value!r}") from err
    if val < 0:
        raise ValueError(f"{name} cannot be negative, got {val}")
    return val


def is_valid_email(email: str) -> bool:
    """Check if an email string is structurally valid."""
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_PATTERN.match(email.strip()))
