"""Commit model representing a Git commit with metadata, code churn, and risk annotations."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union
from utils.dates import format_display_date, format_iso_datetime, parse_iso_datetime
from utils.validators import validate_commit_hash, validate_non_negative_int


class Commit:
    """Encapsulates a Git commit record.
    
    Demonstrates OOP encapsulation: immutable core attributes (hash, date, author)
    with controlled modification for enrichment properties (classification, risk_score).
    Implements comparison operators to enable chronological ordering and binary search.
    """

    def __init__(
        self,
        commit_hash: str,
        author: str,
        author_email: str,
        commit_date: Union[datetime, str],
        message: str,
        files_changed: Optional[Sequence[str]] = None,
        insertions: int = 0,
        deletions: int = 0,
        classification: Optional[str] = None,
        risk_score: Optional[float] = None,
    ) -> None:
        self._commit_hash = validate_commit_hash(commit_hash)
        self._author = author.strip() if author else "Unknown"
        self._author_email = author_email.strip().lower() if author_email else ""
        
        if isinstance(commit_date, str):
            self._commit_date = parse_iso_datetime(commit_date)
        elif isinstance(commit_date, datetime):
            self._commit_date = commit_date
        else:
            raise ValueError("commit_date must be a datetime or ISO string")

        self._message = message.strip() if message else ""
        self._files_changed = tuple(sorted(set(files_changed))) if files_changed else ()
        self._insertions = validate_non_negative_int(insertions, "insertions")
        self._deletions = validate_non_negative_int(deletions, "deletions")
        self._classification = classification
        self._risk_score = float(risk_score) if risk_score is not None else None

    # Encapsulated property accessors
    @property
    def commit_hash(self) -> str:
        return self._commit_hash

    @property
    def short_hash(self) -> str:
        return self._commit_hash[:7]

    @property
    def author(self) -> str:
        return self._author

    @property
    def author_email(self) -> str:
        return self._author_email

    @property
    def commit_date(self) -> datetime:
        return self._commit_date

    @property
    def message(self) -> str:
        return self._message

    @property
    def files_changed(self) -> Sequence[str]:
        return self._files_changed

    @property
    def file_count(self) -> int:
        return len(self._files_changed)

    @property
    def insertions(self) -> int:
        return self._insertions

    @property
    def deletions(self) -> int:
        return self._deletions

    @property
    def total_changes(self) -> int:
        """Total churn (insertions + deletions)."""
        return self._insertions + self._deletions

    @property
    def classification(self) -> Optional[str]:
        return self._classification

    @classification.setter
    def classification(self, value: Optional[str]) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError("classification must be a string or None")
        self._classification = value.strip() if value else None

    @property
    def risk_score(self) -> Optional[float]:
        return self._risk_score

    @risk_score.setter
    def risk_score(self, value: Optional[float]) -> None:
        if value is not None:
            val = float(value)
            if not (0.0 <= val <= 100.0):
                raise ValueError(f"risk_score must be between 0.0 and 100.0, got {val}")
            self._risk_score = round(val, 2)
        else:
            self._risk_score = None

    # Serialization
    def to_dict(self) -> Dict[str, Any]:
        """Convert commit to a serializable dictionary."""
        return {
            "commit_hash": self._commit_hash,
            "short_hash": self.short_hash,
            "author": self._author,
            "author_email": self._author_email,
            "commit_date": format_iso_datetime(self._commit_date),
            "message": self._message,
            "files_changed": list(self._files_changed),
            "insertions": self._insertions,
            "deletions": self._deletions,
            "total_changes": self.total_changes,
            "classification": self._classification or "",
            "risk_score": self._risk_score if self._risk_score is not None else "",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Commit":
        """Factory method to instantiate a Commit from serialized dictionary data."""
        files = data.get("files_changed", [])
        if isinstance(files, str):
            files = [f.strip() for f in files.split(";") if f.strip()]
        
        raw_risk = data.get("risk_score")
        risk_val = float(raw_risk) if raw_risk not in (None, "", "None") else None

        return cls(
            commit_hash=data["commit_hash"],
            author=data.get("author", "Unknown"),
            author_email=data.get("author_email", ""),
            commit_date=data["commit_date"],
            message=data.get("message", ""),
            files_changed=files,
            insertions=int(data.get("insertions", 0)),
            deletions=int(data.get("deletions", 0)),
            classification=data.get("classification") or None,
            risk_score=risk_val,
        )

    # Date comparison operators for binary search and sorting
    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Commit):
            return self._commit_date < other._commit_date
        if isinstance(other, datetime):
            return self._commit_date < other
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Commit):
            return self._commit_date <= other._commit_date
        if isinstance(other, datetime):
            return self._commit_date <= other
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Commit):
            return self._commit_date > other._commit_date
        if isinstance(other, datetime):
            return self._commit_date > other
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Commit):
            return self._commit_date >= other._commit_date
        if isinstance(other, datetime):
            return self._commit_date >= other
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Commit):
            return False
        return self._commit_hash == other._commit_hash

    def __hash__(self) -> int:
        return hash(self._commit_hash)

    def __repr__(self) -> str:
        return (
            f"Commit(hash={self.short_hash!r}, author={self._author!r}, "
            f"date={format_display_date(self._commit_date)}, churn={self.total_changes})"
        )

    def __str__(self) -> str:
        cls_str = f" [{self._classification}]" if self._classification else ""
        return (
            f"[{self.short_hash}] {self._author} | "
            f"{format_display_date(self._commit_date)} | "
            f"+{self._insertions}/-{self._deletions}{cls_str} - {self._message[:50]}"
        )
