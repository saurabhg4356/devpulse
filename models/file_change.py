"""FileChange model representing a modification to a specific file in a Git commit."""

from datetime import datetime
from typing import Any, Dict
from utils.dates import format_iso_datetime, parse_iso_datetime
from utils.validators import validate_commit_hash, validate_non_negative_int


VALID_CHANGE_TYPES = {"added", "modified", "deleted", "renamed"}


class FileChange:
    """Represents a discrete file modification within a commit.
    
    Attributes:
        file_path: Relative repository path to the file.
        commit_hash: Commit SHA-1 identifier where this change occurred.
        change_type: Nature of the change ('added', 'modified', 'deleted', 'renamed').
        insertions: Number of lines added.
        deletions: Number of lines removed.
        timestamp: Time when change occurred.
    """

    def __init__(
        self,
        file_path: str,
        commit_hash: str,
        change_type: str = "modified",
        insertions: int = 0,
        deletions: int = 0,
        timestamp: datetime = None,
    ) -> None:
        if not file_path or not isinstance(file_path, str):
            raise ValueError("file_path must be a non-empty string")
        
        self._file_path = file_path.strip().replace("\\", "/")
        self._commit_hash = validate_commit_hash(commit_hash)
        
        norm_type = change_type.strip().lower() if isinstance(change_type, str) else "modified"
        self._change_type = norm_type if norm_type in VALID_CHANGE_TYPES else "modified"
        
        self._insertions = validate_non_negative_int(insertions, "insertions")
        self._deletions = validate_non_negative_int(deletions, "deletions")
        self._timestamp = timestamp or datetime.now()

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def commit_hash(self) -> str:
        return self._commit_hash

    @property
    def change_type(self) -> str:
        return self._change_type

    @property
    def insertions(self) -> int:
        return self._insertions

    @property
    def deletions(self) -> int:
        return self._deletions

    @property
    def total_changes(self) -> int:
        """Total churn: lines added plus lines deleted."""
        return self._insertions + self._deletions

    @property
    def churn(self) -> int:
        """Alias for total code churn."""
        return self.total_changes

    @property
    def net_change(self) -> int:
        """Net lines added or removed."""
        return self._insertions - self._deletions

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize file change instance to dictionary."""
        return {
            "file_path": self._file_path,
            "commit_hash": self._commit_hash,
            "change_type": self._change_type,
            "insertions": self._insertions,
            "deletions": self._deletions,
            "total_changes": self.total_changes,
            "timestamp": format_iso_datetime(self._timestamp),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileChange":
        """Reconstruct a FileChange instance from dictionary data."""
        ts = parse_iso_datetime(data["timestamp"]) if "timestamp" in data else None
        return cls(
            file_path=data["file_path"],
            commit_hash=data["commit_hash"],
            change_type=data.get("change_type", "modified"),
            insertions=data.get("insertions", 0),
            deletions=data.get("deletions", 0),
            timestamp=ts,
        )

    def __repr__(self) -> str:
        return (
            f"FileChange(file_path={self._file_path!r}, commit={self._commit_hash[:7]}, "
            f"type={self._change_type}, +{self._insertions}/-{self._deletions})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileChange):
            return False
        return (
            self._file_path == other._file_path
            and self._commit_hash == other._commit_hash
            and self._change_type == other._change_type
            and self._insertions == other._insertions
            and self._deletions == other._deletions
        )
