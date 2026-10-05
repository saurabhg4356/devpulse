"""Visualizer service rendering high-quality charts using Matplotlib.

Produces 7 required visualizations from actual repository data:
1. Commit activity over time
2. Code churn over time (additions vs deletions)
3. Top modified files
4. Risk distribution
5. Developer activity
6. Release change-volume trend
7. Predicted vs historical change volume

Adheres strictly to best practices: Agg backend, readable axes, high DPI, and explicit figure closure.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import matplotlib
# Use non-interactive Agg backend for safe headless rendering
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from models.commit import Commit
from models.developer import Developer
from models.exceptions import ReportGenerationError
from models.risk import RiskResult
from services.release_predictor import PredictionResult


class Visualizer:
    """Renders and exports graphical charts of repository metrics."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._configure_style()

    def _configure_style(self) -> None:
        """Apply clean, modern styling to all plots."""
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Helvetica", "Arial"]
        plt.rcParams["axes.edgecolor"] = "#cccccc"
        plt.rcParams["axes.linewidth"] = 0.8

    def plot_commit_activity_over_time(self, commits: Sequence[Commit]) -> Path:
        """Chart 1: Commits aggregated by weekly/monthly timeline."""
        out_path = self.output_dir / "commit_activity.png"
        if not commits:
            return out_path

        df = pd.DataFrame([{"date": c.commit_date} for c in commits])
        df.set_index("date", inplace=True)
        # Resample weekly
        resampled = df.resample("W").size()

        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
        ax.plot(resampled.index, resampled.values, color="#1f77b4", marker="o", linewidth=2, markersize=4)
        ax.fill_between(resampled.index, resampled.values, color="#1f77b4", alpha=0.15)
        ax.set_title("Commit Activity Over Time (Weekly Aggregation)", fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Date", fontsize=10, labelpad=8)
        ax.set_ylabel("Commit Count", fontsize=10, labelpad=8)
        fig.autofmt_xdate()
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_code_churn_over_time(self, commits: Sequence[Commit]) -> Path:
        """Chart 2: Additions (+) vs Deletions (-) timeline."""
        out_path = self.output_dir / "code_churn.png"
        if not commits:
            return out_path

        df = pd.DataFrame(
            [{"date": c.commit_date, "ins": c.insertions, "dels": -c.deletions} for c in commits]
        )
        df.set_index("date", inplace=True)
        resampled = df.resample("W").sum()

        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
        ax.bar(resampled.index, resampled["ins"], width=4, label="Additions (+)", color="#2ca02c", alpha=0.85)
        ax.bar(resampled.index, resampled["dels"], width=4, label="Deletions (-)", color="#d62728", alpha=0.85)
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.set_title("Code Churn Over Time (Additions vs Deletions)", fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Date", fontsize=10, labelpad=8)
        ax.set_ylabel("Lines Changed", fontsize=10, labelpad=8)
        ax.legend(frameon=True, facecolor="white")
        fig.autofmt_xdate()
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_top_modified_files(self, top_files: Sequence[Dict[str, Any]]) -> Path:
        """Chart 3: Horizontal bar chart of most frequently touched files."""
        out_path = self.output_dir / "top_modified_files.png"
        if not top_files:
            return out_path

        # Take up to 10 files
        subset = list(top_files[:10])
        # Shorten filenames for clean y-axis labels
        labels = [f.get("file_path", "")[-35:] for f in subset][::-1]
        counts = [f.get("modification_count", 0) for f in subset][::-1]

        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        bars = ax.barh(labels, counts, color="#3b82f6", alpha=0.85, edgecolor="#1d4ed8")
        ax.set_title("Top Modified Files by Modification Frequency", fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Modification Count", fontsize=10, labelpad=8)
        ax.bar_label(bars, padding=4, fontsize=9)
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_risk_distribution(self, file_risks: Sequence[RiskResult]) -> Path:
        """Chart 4: Breakdown of repository files by risk level tier."""
        out_path = self.output_dir / "risk_distribution.png"
        if not file_risks:
            return out_path

        levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        counts = {lvl: 0 for lvl in levels}
        for r in file_risks:
            lvl = r.level if r.level in counts else "LOW"
            counts[lvl] += 1

        colors = ["#22c55e", "#eab308", "#f97316", "#ef4444"]
        labels = [f"{lvl}\n({counts[lvl]})" for lvl in levels]
        values = [counts[lvl] for lvl in levels]

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        bars = ax.bar(labels, values, color=colors, alpha=0.85, edgecolor="#333333", width=0.55)
        ax.set_title("Codebase Risk Level Distribution", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Number of Files", fontsize=10, labelpad=8)
        ax.bar_label(bars, padding=3, fontsize=9)
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_developer_activity(self, developers: Sequence[Developer]) -> Path:
        """Chart 5: Contributor commit and churn distribution."""
        out_path = self.output_dir / "developer_activity.png"
        if not developers:
            return out_path

        subset = sorted(developers, key=lambda d: d.commit_count, reverse=True)[:8]
        names = [d.name[:18] for d in subset]
        commits = [d.commit_count for d in subset]

        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
        bars = ax.bar(names, commits, color="#8b5cf6", alpha=0.85, edgecolor="#6d28d9", width=0.5)
        ax.set_title("Developer Activity (Commits Contributed)", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Commit Count", fontsize=10, labelpad=8)
        ax.bar_label(bars, padding=3, fontsize=9)
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_release_trend(self, historical_periods: Sequence[Dict[str, Any]]) -> Path:
        """Chart 6: Historical release code churn trend."""
        out_path = self.output_dir / "release_trend.png"
        if not historical_periods:
            return out_path

        labels = [p["period"] for p in historical_periods]
        churns = [p["churn"] for p in historical_periods]

        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
        ax.plot(labels, churns, color="#06b6d4", marker="s", linewidth=2, markersize=5)
        ax.set_title("Release Code Change-Volume Trend", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Total Churn (Lines)", fontsize=10, labelpad=8)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def plot_predicted_vs_historical(
        self,
        prediction: PredictionResult,
    ) -> Path:
        """Chart 7: Predicted versus historical code change volume."""
        out_path = self.output_dir / "predicted_vs_historical.png"
        hist = prediction.historical_periods
        if not hist:
            return out_path

        periods = [h["period"] for h in hist] + ["Next Cycle (Forecast)"]
        values = [h["churn"] for h in hist] + [prediction.predicted_volume]
        colors = ["#3b82f6"] * len(hist) + ["#f59e0b"]

        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
        bars = ax.bar(periods, values, color=colors, alpha=0.85, edgecolor="#1f2937", width=0.55)
        ax.set_title("Historical Churn vs Next-Period Forecast", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Code Churn (Lines)", fontsize=10, labelpad=8)
        ax.bar_label(bars, padding=3, fmt="%.0f", fontsize=9)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def generate_all_charts(
        self,
        commits: Sequence[Commit],
        file_risks: Sequence[RiskResult],
        top_files: Sequence[Dict[str, Any]],
        developers: Sequence[Developer],
        prediction: Optional[PredictionResult] = None,
    ) -> Dict[str, Path]:
        """Generate all required charts in one unified execution.
        
        Returns:
            Dictionary of chart names mapping to generated image file paths.
        """
        generated: Dict[str, Path] = {}
        try:
            generated["commit_activity"] = self.plot_commit_activity_over_time(commits)
            generated["code_churn"] = self.plot_code_churn_over_time(commits)
            generated["top_modified_files"] = self.plot_top_modified_files(top_files)
            generated["risk_distribution"] = self.plot_risk_distribution(file_risks)
            generated["developer_activity"] = self.plot_developer_activity(developers)
            
            if prediction and prediction.historical_periods:
                generated["release_trend"] = self.plot_release_trend(prediction.historical_periods)
                generated["predicted_vs_historical"] = self.plot_predicted_vs_historical(prediction)
        except Exception as err:
            raise ReportGenerationError(f"Failed to render charts: {err}") from err

        return generated
