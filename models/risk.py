"""RiskResult and ReleaseRisk models representing codebase and release risk evaluations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RiskResult:
    """Represents the risk assessment for a specific file in the repository.
    
    Attributes:
        file_path: Relative path to the analyzed file.
        score: Computed risk score between 0.0 and 100.0.
        level: Categorical risk tier ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL').
        reasons: List of human-explainable factors that drove the risk score.
        recommended_action: Suggested software engineering mitigation.
        factors: Numerical breakdown of individual scoring components.
    """
    file_path: str
    score: float
    level: str
    reasons: List[str] = field(default_factory=list)
    recommended_action: str = ""
    factors: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = round(max(0.0, min(100.0, float(self.score))), 2)
        self.file_path = self.file_path.strip().replace("\\", "/")
        if not self.recommended_action and self.level in ("HIGH", "CRITICAL"):
            self.recommended_action = "Review recent changes and run related regression tests."
        elif not self.recommended_action:
            self.recommended_action = "Standard code review prior to release."

    # Comparison support for heapq / sorting based on risk score
    def __lt__(self, other: Any) -> bool:
        if isinstance(other, RiskResult):
            return self.score < other.score
        if isinstance(other, (int, float)):
            return self.score < other
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, RiskResult):
            return self.score > other.score
        if isinstance(other, (int, float)):
            return self.score > other
        return NotImplemented

    def summary(self) -> str:
        """Formatted summary of the file's risk evaluation."""
        lines = [
            f"FILE: {self.file_path}",
            f"Risk Score: {self.score:.1f} ({self.level})",
            "Reasons:",
        ]
        for reason in self.reasons:
            lines.append(f"  * {reason}")
        lines.append(f"Recommended action: {self.recommended_action}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert risk result to dictionary for CSV/JSON export."""
        return {
            "file_path": self.file_path,
            "score": self.score,
            "level": self.level,
            "reasons": "; ".join(self.reasons),
            "recommended_action": self.recommended_action,
            "factors": self.factors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskResult":
        """Instantiate RiskResult from dictionary."""
        reasons_val = data.get("reasons", [])
        if isinstance(reasons_val, str):
            reasons_val = [r.strip() for r in reasons_val.split(";") if r.strip()]
        return cls(
            file_path=data["file_path"],
            score=float(data["score"]),
            level=data.get("level", "LOW"),
            reasons=reasons_val,
            recommended_action=data.get("recommended_action", ""),
            factors=data.get("factors", {}),
        )


@dataclass
class ReleaseRisk:
    """Represents the aggregate release risk for the entire repository at current state."""
    overall_score: float
    level: str
    top_risk_drivers: List[str] = field(default_factory=list)
    summary_text: str = ""

    def __post_init__(self) -> None:
        self.overall_score = round(max(0.0, min(100.0, float(self.overall_score))), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "level": self.level,
            "top_risk_drivers": self.top_risk_drivers,
            "summary_text": self.summary_text,
        }
