"""Release change-volume predictor using scikit-learn LinearRegression.

Estimates next-cycle code change volume (churn) by modeling historical chronological trends.
Explicitly documents limitations and raises InsufficientDataError when repository history
has fewer than minimum required temporal intervals.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.commit import Commit
from models.exceptions import InsufficientDataError, PredictionError


@dataclass
class PredictionResult:
    """Encapsulates release volume prediction outputs."""
    predicted_volume: float
    coefficient: float
    intercept: float
    mae: Optional[float]
    periods_count: int
    historical_periods: List[Dict[str, Any]]
    confidence_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_volume": round(self.predicted_volume, 1),
            "coefficient": round(self.coefficient, 2),
            "intercept": round(self.intercept, 2),
            "mae": round(self.mae, 2) if self.mae is not None else None,
            "periods_count": self.periods_count,
            "historical_periods": self.historical_periods,
            "confidence_note": self.confidence_note,
        }

    def summary(self) -> str:
        return (
            f"Predicted next-cycle change volume: ~{int(round(self.predicted_volume)):,} lines "
            f"(Trend slope: {self.coefficient:+.1f} lines/period, MAE: ±{self.mae:.1f})"
        )


class ReleasePredictor:
    """Predicts upcoming release code churn using Ordinary Least Squares linear regression.
    
    LIMITATION NOTE:
    Linear regression models unidirectional linear velocity. Real software release churn
    is impacted by sprint boundaries, refactoring initiatives, and holidays.
    This prediction should be interpreted as an indicative baseline trend rather than an SLA.
    """

    def __init__(self, config: Optional[DevPulseConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.settings = self.config.predictor

    def predict_next_period_churn(
        self,
        commits: Sequence[Commit],
        period_freq: Optional[str] = None,
    ) -> PredictionResult:
        """Fit a linear regression model on historical period churn and forecast the next period.
        
        Args:
            commits: Sequence of analyzed commits.
            period_freq: Aggregation frequency ('W' for weekly, 'ME' for monthly).
                         Defaults to config setting.
                         
        Returns:
            PredictionResult with predicted churn and statistical parameters.
            
        Raises:
            InsufficientDataError: If fewer than `min_periods` temporal units exist.
            PredictionError: If regression fitting fails.
        """
        if not commits:
            raise InsufficientDataError("No commit data provided for release prediction.")

        freq = period_freq or self.settings.aggregation_unit

        # Build chronological DataFrame
        records = [
            {
                "date": c.commit_date,
                "churn": c.total_changes,
                "insertions": c.insertions,
                "deletions": c.deletions,
            }
            for c in commits
        ]
        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)

        try:
            # Resample by time interval
            # Note: pandas 2.2+ uses 'ME' for month-end, fallback to 'M' if needed
            resampled = df.resample(freq).sum()
        except Exception:
            # Fallback for compatibility across pandas versions
            resampled = df.resample("W").sum()

        # Filter out empty leading intervals if any
        resampled = resampled[resampled["churn"] > 0]

        periods_count = len(resampled)
        if periods_count < self.settings.min_periods:
            raise InsufficientDataError(
                f"Insufficient historical periods ({periods_count} found, "
                f"{self.settings.min_periods} required) to perform linear regression."
            )

        # Feature matrix X: chronological period index [0, 1, 2, ...]
        X = np.arange(periods_count).reshape(-1, 1)
        y = resampled["churn"].to_numpy(dtype=float)

        try:
            model = LinearRegression()
            model.fit(X, y)

            # Predict next step (index = periods_count)
            next_step = np.array([[periods_count]])
            raw_pred = float(model.predict(next_step)[0])
            pred_val = max(0.0, raw_pred)  # Code churn cannot be negative

            # Calculate historical MAE
            y_pred = model.predict(X)
            mae = float(mean_absolute_error(y, y_pred))

            coef = float(model.coef_[0])
            intercept = float(model.intercept_)

            # Build historical summary list
            historical_data: List[Dict[str, Any]] = []
            for idx, (timestamp, row) in enumerate(resampled.iterrows()):
                label = (
                    timestamp.strftime("%Y-%m-%d")
                    if isinstance(timestamp, (datetime, pd.Timestamp))
                    else f"Period {idx + 1}"
                )
                historical_data.append(
                    {
                        "period": label,
                        "churn": int(row["churn"]),
                        "insertions": int(row["insertions"]),
                        "deletions": int(row["deletions"]),
                    }
                )

            note = (
                "Linear regression based on historical chronological intervals. "
                "Forecast subject to sprint scope fluctuations."
            )

            return PredictionResult(
                predicted_volume=pred_val,
                coefficient=coef,
                intercept=intercept,
                mae=mae,
                periods_count=periods_count,
                historical_periods=historical_data,
                confidence_note=note,
            )

        except Exception as err:
            if isinstance(err, InsufficientDataError):
                raise
            raise PredictionError(f"Linear regression fitting failed: {err}") from err
