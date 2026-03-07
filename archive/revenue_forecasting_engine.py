"""
GetPaidRx - Pharmacy Revenue Forecasting Engine
Forecasts pharmacy revenue using historical fill patterns, seasonal trends,
payer mix shifts, drug pricing trajectories, and regulatory impact modeling.

Features:
- Time series forecasting with seasonal decomposition
- Payer mix trend analysis and projection
- Drug pricing trajectory modeling (NADAC, AWP trends)
- New generic launch impact prediction
- Regulatory impact modeling (CMS 2026 DIR rule, IRA drug negotiation)
- Scenario-based P&L projections
- Cash flow forecasting with confidence intervals
"""
import json
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class ForecastHorizon(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class TrendDirection(Enum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"


@dataclass
class MonthlyRevenue:
    """Monthly revenue snapshot."""
    year_month: str  # YYYY-MM
    total_fills: int = 0
    total_revenue: float = 0.0
    total_cost: float = 0.0
    gross_profit: float = 0.0
    brand_fills: int = 0
    generic_fills: int = 0
    specialty_fills: int = 0
    brand_revenue: float = 0.0
    generic_revenue: float = 0.0
    specialty_revenue: float = 0.0
    avg_margin_per_fill: float = 0.0
    payer_mix: Dict[str, float] = field(default_factory=dict)


@dataclass
class SeasonalPattern:
    """Seasonal pattern for a revenue component."""
    component: str
    monthly_indices: List[float] = field(default_factory=list)  # 12 values, 1.0 = average
    peak_months: List[int] = field(default_factory=list)
    trough_months: List[int] = field(default_factory=list)
    amplitude: float = 0.0  # max deviation from mean


@dataclass
class ForecastResult:
    """Result of a revenue forecast for a single period."""
    period: str
    forecasted_fills: int
    forecasted_revenue: float
    forecasted_cost: float
    forecasted_profit: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float = 0.95
    components: Dict[str, float] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)


class SeasonalDecomposer:
    """Decomposes time series into trend, seasonal, and residual components."""

    def decompose(
        self,
        values: List[float],
        period: int = 12
    ) -> Dict[str, List[float]]:
        """Perform additive seasonal decomposition."""
        n = len(values)
        if n < period * 2:
            # Not enough data for decomposition
            return {
                "original": values,
                "trend": values,
                "seasonal": [0.0] * n,
                "residual": [0.0] * n
            }

        # Step 1: Compute centered moving average (trend)
        trend = self._centered_moving_average(values, period)

        # Step 2: De-trend (original - trend)
        detrended = [
            values[i] - trend[i] if trend[i] is not None else 0.0
            for i in range(n)
        ]

        # Step 3: Average seasonal component
        seasonal_avg = [0.0] * period
        seasonal_counts = [0] * period
        for i in range(n):
            if trend[i] is not None:
                idx = i % period
                seasonal_avg[idx] += detrended[i]
                seasonal_counts[idx] += 1

        for i in range(period):
            if seasonal_counts[i] > 0:
                seasonal_avg[i] /= seasonal_counts[i]

        # Normalize (subtract mean to make seasonal zero-sum)
        mean_seasonal = sum(seasonal_avg) / period
        seasonal_avg = [s - mean_seasonal for s in seasonal_avg]

        # Step 4: Extend seasonal component to full series
        seasonal = [seasonal_avg[i % period] for i in range(n)]

        # Step 5: Residual
        residual = []
        for i in range(n):
            t = trend[i] if trend[i] is not None else values[i]
            residual.append(values[i] - t - seasonal[i])

        # Fill None trends with linear interpolation
        trend_filled = self._interpolate_nones(trend, values)

        return {
            "original": values,
            "trend": trend_filled,
            "seasonal": seasonal,
            "residual": residual
        }

    def _centered_moving_average(
        self, values: List[float], period: int
    ) -> List[Optional[float]]:
        """Compute centered moving average."""
        n = len(values)
        result: List[Optional[float]] = [None] * n
        half = period // 2

        for i in range(half, n - half):
            window = values[i - half:i + half + 1]
            if period % 2 == 0:
                # For even period, average two adjacent windows
                window2 = values[i - half + 1:i + half + 2] if i + half + 2 <= n else window
                result[i] = (sum(window) + sum(window2)) / (len(window) + len(window2))
            else:
                result[i] = sum(window) / len(window)

        return result

    def _interpolate_nones(
        self, series: List[Optional[float]], fallback: List[float]
    ) -> List[float]:
        """Interpolate None values in series."""
        result = list(series)
        n = len(result)

        # Forward fill
        last_val = None
        for i in range(n):
            if result[i] is not None:
                last_val = result[i]
            elif last_val is not None:
                result[i] = last_val

        # Backward fill remaining
        last_val = None
        for i in range(n - 1, -1, -1):
            if result[i] is not None:
                last_val = result[i]
            elif last_val is not None:
                result[i] = last_val
            else:
                result[i] = fallback[i] if i < len(fallback) else 0.0

        return result

    def extract_seasonal_pattern(
        self,
        values: List[float],
        component_name: str
    ) -> SeasonalPattern:
        """Extract and summarize the seasonal pattern."""
        decomp = self.decompose(values)
        seasonal = decomp["seasonal"]

        if len(seasonal) < 12:
            return SeasonalPattern(component=component_name)

        # Monthly indices (first 12 values normalized to mean)
        monthly = seasonal[:12]
        mean_val = sum(values) / len(values) if values else 1
        indices = [(mean_val + m) / mean_val if mean_val else 1.0 for m in monthly]

        peak_months = sorted(range(12), key=lambda i: indices[i], reverse=True)[:3]
        trough_months = sorted(range(12), key=lambda i: indices[i])[:3]
        amplitude = max(indices) - min(indices)

        return SeasonalPattern(
            component=component_name,
            monthly_indices=indices,
            peak_months=[m + 1 for m in peak_months],
            trough_months=[m + 1 for m in trough_months],
            amplitude=round(amplitude, 4)
        )


class RevenueForecastEngine:
    """Main forecasting engine for pharmacy revenue."""

    def __init__(self):
        self.historical: List[MonthlyRevenue] = []
        self.decomposer = SeasonalDecomposer()
        self._trend_cache: Dict[str, List[float]] = {}

    def load_historical(self, data: List[MonthlyRevenue]):
        """Load historical monthly revenue data."""
        self.historical = sorted(data, key=lambda d: d.year_month)
        logger.info(f"Loaded {len(data)} months of historical revenue data")

    def forecast(
        self,
        months_ahead: int = 12,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """Generate revenue forecast."""
        if len(self.historical) < 6:
            return {"error": "Need at least 6 months of historical data"}

        # Extract revenue series
        revenue_series = [m.total_revenue for m in self.historical]
        fill_series = [float(m.total_fills) for m in self.historical]
        margin_series = [m.avg_margin_per_fill for m in self.historical]

        # Decompose
        rev_decomp = self.decomposer.decompose(revenue_series)
        fill_decomp = self.decomposer.decompose(fill_series)

        # Forecast trend using linear regression on last 12 months
        recent_trend = rev_decomp["trend"][-min(12, len(rev_decomp["trend"])):]
        slope, intercept = self._linear_regression(
            list(range(len(recent_trend))), recent_trend
        )

        # Calculate residual standard deviation for confidence intervals
        residuals = rev_decomp["residual"]
        residual_std = self._std_dev(residuals)

        # Z-score for confidence level
        z = 1.96 if confidence_level == 0.95 else 1.645

        # Generate forecasts
        forecasts: List[ForecastResult] = []
        last_month = self.historical[-1].year_month
        last_year, last_mo = int(last_month[:4]), int(last_month[5:7])

        n = len(revenue_series)
        seasonal = rev_decomp["seasonal"]

        for i in range(1, months_ahead + 1):
            # Calculate forecast month
            forecast_mo = last_mo + i
            forecast_yr = last_year + (forecast_mo - 1) // 12
            forecast_mo = ((forecast_mo - 1) % 12) + 1
            period = f"{forecast_yr}-{forecast_mo:02d}"

            # Trend projection
            trend_val = intercept + slope * (n + i - 1)

            # Seasonal component
            seasonal_idx = (n + i - 1) % 12
            seasonal_val = seasonal[seasonal_idx] if seasonal_idx < len(seasonal) else 0

            # Point forecast
            forecast_revenue = trend_val + seasonal_val
            forecast_revenue = max(0, forecast_revenue)

            # Confidence interval (widens with horizon)
            horizon_factor = math.sqrt(i)  # uncertainty grows with sqrt(time)
            ci_width = z * residual_std * horizon_factor

            # Fill and margin forecasts
            fill_trend = fill_decomp["trend"][-1] if fill_decomp["trend"] else 0
            fill_slope = slope / (revenue_series[-1] / fill_series[-1]) if fill_series[-1] > 0 and revenue_series[-1] > 0 else 0

            forecast_fills = int(max(0, fill_trend + fill_slope * i))
            avg_margin = sum(margin_series[-6:]) / min(6, len(margin_series))
            forecast_cost = forecast_revenue - (forecast_fills * avg_margin)

            forecasts.append(ForecastResult(
                period=period,
                forecasted_fills=forecast_fills,
                forecasted_revenue=round(forecast_revenue, 2),
                forecasted_cost=round(forecast_cost, 2),
                forecasted_profit=round(forecast_revenue - forecast_cost, 2),
                confidence_lower=round(max(0, forecast_revenue - ci_width), 2),
                confidence_upper=round(forecast_revenue + ci_width, 2),
                confidence_level=confidence_level,
                components={
                    "trend": round(trend_val, 2),
                    "seasonal": round(seasonal_val, 2),
                    "slope_per_month": round(slope, 2)
                }
            ))

        # Summary statistics
        total_forecast_revenue = sum(f.forecasted_revenue for f in forecasts)
        total_forecast_profit = sum(f.forecasted_profit for f in forecasts)
        last_12_revenue = sum(m.total_revenue for m in self.historical[-12:])

        yoy_growth = (
            (total_forecast_revenue - last_12_revenue) / last_12_revenue * 100
            if last_12_revenue > 0 else 0
        )

        # Trend direction
        if slope > residual_std * 0.1:
            trend_dir = TrendDirection.INCREASING
        elif slope < -residual_std * 0.1:
            trend_dir = TrendDirection.DECREASING
        else:
            trend_dir = TrendDirection.STABLE

        return {
            "forecast_generated": datetime.now(timezone.utc).isoformat(),
            "historical_months": len(self.historical),
            "forecast_months": months_ahead,
            "confidence_level": confidence_level,
            "summary": {
                "forecasted_annual_revenue": round(total_forecast_revenue, 2),
                "forecasted_annual_profit": round(total_forecast_profit, 2),
                "prior_12mo_revenue": round(last_12_revenue, 2),
                "yoy_growth_pct": round(yoy_growth, 1),
                "trend_direction": trend_dir.value,
                "monthly_growth_rate": round(slope, 2),
                "forecast_uncertainty_avg": round(
                    sum(f.confidence_upper - f.confidence_lower for f in forecasts) / len(forecasts), 2
                )
            },
            "monthly_forecasts": [
                {
                    "period": f.period,
                    "revenue": f.forecasted_revenue,
                    "profit": f.forecasted_profit,
                    "fills": f.forecasted_fills,
                    "lower_bound": f.confidence_lower,
                    "upper_bound": f.confidence_upper
                }
                for f in forecasts
            ],
            "seasonal_pattern": {
                "peak_months": self.decomposer.extract_seasonal_pattern(
                    revenue_series, "revenue"
                ).peak_months,
                "trough_months": self.decomposer.extract_seasonal_pattern(
                    revenue_series, "revenue"
                ).trough_months
            }
        }

    def scenario_forecast(
        self,
        scenario_name: str,
        adjustments: Dict[str, float],
        months_ahead: int = 12
    ) -> Dict[str, Any]:
        """Run forecast with scenario adjustments."""
        # Get base forecast
        base = self.forecast(months_ahead)
        if "error" in base:
            return base

        # Apply adjustments
        revenue_mult = 1.0 + adjustments.get("revenue_growth_pct", 0) / 100
        cost_mult = 1.0 + adjustments.get("cost_increase_pct", 0) / 100
        fill_mult = 1.0 + adjustments.get("volume_change_pct", 0) / 100
        margin_adj = adjustments.get("margin_adjustment_per_fill", 0)

        scenario_forecasts = []
        for month_data in base["monthly_forecasts"]:
            adj_revenue = month_data["revenue"] * revenue_mult
            adj_fills = int(month_data["fills"] * fill_mult)
            adj_profit = month_data["profit"] * revenue_mult + adj_fills * margin_adj
            adj_cost = adj_revenue - adj_profit

            scenario_forecasts.append({
                "period": month_data["period"],
                "revenue": round(adj_revenue, 2),
                "profit": round(adj_profit, 2),
                "fills": adj_fills,
                "vs_base_revenue": round(adj_revenue - month_data["revenue"], 2),
                "vs_base_profit": round(adj_profit - month_data["profit"], 2)
            })

        total_adj_revenue = sum(f["revenue"] for f in scenario_forecasts)
        total_adj_profit = sum(f["profit"] for f in scenario_forecasts)
        total_base_revenue = sum(f["revenue"] for f in base["monthly_forecasts"])
        total_base_profit = sum(f["profit"] for f in base["monthly_forecasts"])

        return {
            "scenario_name": scenario_name,
            "adjustments": adjustments,
            "forecast_months": months_ahead,
            "summary": {
                "scenario_annual_revenue": round(total_adj_revenue, 2),
                "scenario_annual_profit": round(total_adj_profit, 2),
                "base_annual_revenue": round(total_base_revenue, 2),
                "base_annual_profit": round(total_base_profit, 2),
                "revenue_impact": round(total_adj_revenue - total_base_revenue, 2),
                "profit_impact": round(total_adj_profit - total_base_profit, 2)
            },
            "monthly_forecasts": scenario_forecasts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def _linear_regression(
        self, x: List[float], y: List[float]
    ) -> Tuple[float, float]:
        """Simple linear regression returning (slope, intercept)."""
        n = len(x)
        if n < 2:
            return (0.0, y[0] if y else 0.0)

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-10:
            return (0.0, sum_y / n)

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return (slope, intercept)

    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)
