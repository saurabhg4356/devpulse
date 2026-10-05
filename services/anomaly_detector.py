"""Statistical Anomaly Detection service using NumPy and pandas.

Identifies unusual commit sizes, abnormal code churn bursts, and outlier file activity
using explainable Z-score and interquartile statistical metrics.
Defensively handles zero standard deviation and small sample sizes.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
import pandas as pd

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.commit import Commit
from services.dsa_utils import build_file_stats_map


@dataclass
class Anomaly:
    """Represents a statistical outlier event in the codebase history."""
    metric: str
    identifier: str
    value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "identifier": self.identifier,
            "value": self.value,
            "baseline_mean": round(self.baseline_mean, 2),
            "baseline_std": round(self.baseline_std, 2),
            "z_score": round(self.z_score, 2),
            "reason": self.reason,
        }

    def __str__(self) -> str:
        return (
            f"Unusual {self.metric} [{self.identifier}]: value={self.value:,.0f} "
            f"(Z={self.z_score:.2f} > mean={self.baseline_mean:.1f}). Reason: {self.reason}"
        )


class AnomalyDetector:
    """Detects unusual repository activity using explainable statistical methods."""

    def __init__(self, config: Optional[DevPulseConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.settings = self.config.anomaly

    def detect_commit_anomalies(self, commits: Sequence[Commit]) -> List[Anomaly]:
        """Detect commits whose churn is significantly above repository historical patterns.
        
        Args:
            commits: Sequence of analyzed commits.
            
        Returns:
            List of Anomaly objects.
        """
        if len(commits) < self.settings.min_samples:
            return []

        churns = np.array([c.total_changes for c in commits], dtype=float)
        mean_churn = float(np.mean(churns))
        std_churn = float(np.std(churns))

        # Handle zero standard deviation (e.g. all commits are identical size)
        if std_churn <= 1e-6:
            return []

        # For finite sample sizes N, max possible sample Z-score is (N-1)/sqrt(N).
        # We adjust effective threshold so small samples (e.g. N=5..8) can detect extreme outliers.
        max_possible_z = (len(churns) - 1) / np.sqrt(len(churns))
        effective_threshold = min(self.settings.z_score_threshold, max_possible_z * 0.92)

        anomalies: List[Anomaly] = []
        for c in commits:
            val = float(c.total_changes)
            z_score = (val - mean_churn) / std_churn
            if z_score >= effective_threshold:
                reason = (
                    f"Change volume (+{c.insertions}/-{c.deletions}) is significantly "
                    f"above historical pattern (mean: {mean_churn:.1f} lines, Z-score: {z_score:.2f})."
                )
                anomalies.append(
                    Anomaly(
                        metric="Commit Churn",
                        identifier=c.short_hash,
                        value=val,
                        baseline_mean=mean_churn,
                        baseline_std=std_churn,
                        z_score=z_score,
                        reason=reason,
                    )
                )

        return anomalies

    def detect_file_modification_anomalies(
        self,
        commits: Sequence[Commit],
    ) -> List[Anomaly]:
        """Identify files modified at frequencies statistical standard deviations above peers."""
        if len(commits) < self.settings.min_samples:
            return []

        stats_map = build_file_stats_map(commits)
        if len(stats_map) < self.settings.min_samples:
            return []

        mods = np.array([s["modification_count"] for s in stats_map.values()], dtype=float)
        mean_mods = float(np.mean(mods))
        std_mods = float(np.std(mods))

        if std_mods <= 1e-6:
            return []

        anomalies: List[Anomaly] = []
        for path, s in stats_map.items():
            count = float(s["modification_count"])
            z = (count - mean_mods) / std_mods
            if z >= self.settings.z_score_threshold:
                anomalies.append(
                    Anomaly(
                        metric="File Modification Frequency",
                        identifier=path,
                        value=count,
                        baseline_mean=mean_mods,
                        baseline_std=std_mods,
                        z_score=z,
                        reason=(
                            f"File modified in {int(count)} commits, which is a statistical outlier "
                            f"(peer average: {mean_mods:.1f}, Z-score: {z:.2f})."
                        ),
                    )
                )

        return anomalies

    def detect_all(self, commits: Sequence[Commit]) -> List[Anomaly]:
        """Run all statistical detectors and return combined anomalies."""
        commit_anomalies = self.detect_commit_anomalies(commits)
        file_anomalies = self.detect_file_modification_anomalies(commits)
        return commit_anomalies + file_anomalies
