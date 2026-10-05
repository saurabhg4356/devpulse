"""DevPulse configuration and threshold settings.

Centralized configuration for risk scoring, anomaly detection, commit classification,
forecasting, and output paths. All parameters are customizable.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple


@dataclass(frozen=True)
class RiskThresholds:
    """Configurable risk level boundaries (0-100 scale)."""
    low_max: float = 30.0
    medium_max: float = 60.0
    high_max: float = 80.0
    critical_max: float = 100.0

    def categorize(self, score: float) -> str:
        """Classify a numeric risk score into a risk category.
        
        Args:
            score: Risk score between 0.0 and 100.0.
            
        Returns:
            One of 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
        """
        clamped = max(0.0, min(100.0, float(score)))
        if clamped <= self.low_max:
            return "LOW"
        if clamped <= self.medium_max:
            return "MEDIUM"
        if clamped <= self.high_max:
            return "HIGH"
        return "CRITICAL"


@dataclass(frozen=True)
class RiskWeights:
    """Relative weights for risk scoring factors. Must sum approximately to 1.0."""
    churn_weight: float = 0.30
    frequency_weight: float = 0.25
    contributor_weight: float = 0.20
    recency_weight: float = 0.15
    large_commit_weight: float = 0.10


@dataclass(frozen=True)
class AnomalySettings:
    """Configuration for statistical anomaly detection."""
    z_score_threshold: float = 2.5
    min_samples: int = 4
    iqr_multiplier: float = 1.5


@dataclass(frozen=True)
class ClassifierSettings:
    """Configuration for TF-IDF + MultinomialNB commit classifier."""
    min_confidence: float = 0.28
    ngram_range: Tuple[int, int] = (1, 2)
    max_features: int = 1500
    default_label: str = "Other"
    categories: Tuple[str, ...] = (
        "Feature",
        "Bug Fix",
        "Refactor",
        "Performance",
        "Testing",
        "Documentation",
        "Configuration",
        "Other",
    )


@dataclass(frozen=True)
class PredictorSettings:
    """Configuration for Linear Regression release prediction."""
    min_periods: int = 3
    aggregation_unit: str = "W"  # Weekly ('W') or Monthly ('ME')


@dataclass
class DevPulseConfig:
    """Master configuration for a DevPulse analysis run."""
    risk_thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    risk_weights: RiskWeights = field(default_factory=RiskWeights)
    anomaly: AnomalySettings = field(default_factory=AnomalySettings)
    classifier: ClassifierSettings = field(default_factory=ClassifierSettings)
    predictor: PredictorSettings = field(default_factory=PredictorSettings)
    
    # Subprocess timeouts
    git_timeout_seconds: int = 60
    
    # Storage / output paths
    default_reports_dir: Path = field(default_factory=lambda: Path("reports"))
    default_charts_dir: Path = field(default_factory=lambda: Path("charts"))
    default_data_dir: Path = field(default_factory=lambda: Path("data"))


# Singleton default configuration instance
DEFAULT_CONFIG = DevPulseConfig()
