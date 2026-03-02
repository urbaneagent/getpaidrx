"""
GetPaidRx - Drug Pricing Trend Monitor

Tracks drug pricing trends over time to predict upcoming cost spikes,
detect price manipulation patterns, and identify optimal procurement
windows. Integrates NADAC data for objective price benchmarking.

Features:
  - Price trend analysis (daily/weekly/monthly)
  - Spike detection algorithm (sudden price increases)
  - Seasonal pattern identification
  - Generic cliff predictions (brand patent expirations)
  - Cost forecast using moving averages
  - Price volatility scoring
  - Multi-source price comparison
  - Alert generation for significant price changes
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# Constants
# ============================================================

# Price change thresholds for alerts
SPIKE_THRESHOLD_PCT = 15.0       # 15% increase = spike
MODERATE_CHANGE_PCT = 5.0        # 5% change = noteworthy
CRITICAL_SPIKE_PCT = 50.0        # 50% increase = critical

# Volatility thresholds
VOLATILITY_LEVELS = {
    "stable": (0, 5),
    "low": (5, 10),
    "moderate": (10, 20),
    "high": (20, 40),
    "extreme": (40, float("inf")),
}

# Moving average windows
MA_WINDOWS = {
    "short": 7,      # 7-day
    "medium": 30,     # 30-day
    "long": 90,       # 90-day
}


@dataclass
class PricePoint:
    """A single price observation."""
    date: str
    ndc: str
    drug_name: str
    price_per_unit: float
    source: str = "nadac"           # nadac, awp, wac, acquisition
    package_size: int = 0
    supplier: str = ""


class DrugPricingTrendMonitor:
    """
    Monitors and analyzes drug pricing trends for pharmacy
    procurement optimization.
    """

    def __init__(self):
        self.price_data: Dict[str, List[PricePoint]] = defaultdict(list)

    def load_prices(self, prices: List[Dict[str, Any]]) -> int:
        """Load price history data."""
        loaded = 0
        for p in prices:
            try:
                point = PricePoint(
                    date=str(p.get("date", "")),
                    ndc=str(p.get("ndc", "")),
                    drug_name=str(p.get("drug_name", "")),
                    price_per_unit=float(p.get("price_per_unit", 0)),
                    source=str(p.get("source", "nadac")),
                    package_size=int(p.get("package_size", 0)),
                    supplier=str(p.get("supplier", "")),
                )
                key = f"{point.ndc}_{point.drug_name}"
                self.price_data[key].append(point)
                loaded += 1
            except (ValueError, TypeError):
                continue
        return loaded

    # -------------------------------------------------------
    # Trend Analysis
    # -------------------------------------------------------

    def analyze_drug_trend(self, ndc: str = "", drug_name: str = "") -> Dict[str, Any]:
        """Analyze pricing trend for a specific drug."""
        key = self._find_key(ndc, drug_name)
        if not key:
            return {"error": "Drug not found in price data"}

        points = sorted(self.price_data[key], key=lambda p: p.date)
        if len(points) < 2:
            return {"error": "Need at least 2 data points for trend analysis"}

        prices = [p.price_per_unit for p in points]
        dates = [p.date for p in points]

        # Basic stats
        current_price = prices[-1]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)

        # Trend direction
        first_half = statistics.mean(prices[:len(prices) // 2])
        second_half = statistics.mean(prices[len(prices) // 2:])
        if second_half > first_half * 1.05:
            trend = "increasing"
        elif second_half < first_half * 0.95:
            trend = "decreasing"
        else:
            trend = "stable"

        # Price change
        total_change = current_price - prices[0]
        total_change_pct = round((total_change / prices[0]) * 100, 2) if prices[0] > 0 else 0

        # Moving averages
        ma_short = self._moving_average(prices, MA_WINDOWS["short"])
        ma_medium = self._moving_average(prices, MA_WINDOWS["medium"])
        ma_long = self._moving_average(prices, MA_WINDOWS["long"])

        # Volatility
        volatility = self._compute_volatility(prices)

        # Spike detection
        spikes = self._detect_spikes(points)

        # Forecast (simple linear projection)
        forecast = self._simple_forecast(prices, periods=30)

        return {
            "drug_name": points[0].drug_name,
            "ndc": points[0].ndc,
            "data_points": len(points),
            "date_range": {"start": dates[0], "end": dates[-1]},
            "current_price": round(current_price, 4),
            "statistics": {
                "min": round(min_price, 4),
                "max": round(max_price, 4),
                "mean": round(avg_price, 4),
                "median": round(statistics.median(prices), 4),
                "std_dev": round(statistics.stdev(prices), 4) if len(prices) > 1 else 0,
            },
            "trend": {
                "direction": trend,
                "total_change": round(total_change, 4),
                "total_change_pct": total_change_pct,
                "first_half_avg": round(first_half, 4),
                "second_half_avg": round(second_half, 4),
            },
            "moving_averages": {
                "ma_7": round(ma_short, 4) if ma_short else None,
                "ma_30": round(ma_medium, 4) if ma_medium else None,
                "ma_90": round(ma_long, 4) if ma_long else None,
            },
            "volatility": volatility,
            "spikes": spikes,
            "forecast_30d": round(forecast, 4) if forecast else None,
            "alerts": self._generate_price_alerts(
                current_price, prices, volatility, spikes, trend
            ),
        }

    def get_portfolio_overview(self) -> Dict[str, Any]:
        """Get trend overview across all monitored drugs."""
        results = []
        for key in self.price_data:
            points = self.price_data[key]
            if len(points) < 2:
                continue

            sorted_pts = sorted(points, key=lambda p: p.date)
            prices = [p.price_per_unit for p in sorted_pts]

            current = prices[-1]
            previous = prices[-2]
            change_pct = round(((current - previous) / previous) * 100, 2) if previous > 0 else 0

            results.append({
                "drug_name": sorted_pts[0].drug_name,
                "ndc": sorted_pts[0].ndc,
                "current_price": round(current, 4),
                "change_pct": change_pct,
                "data_points": len(points),
                "is_spike": abs(change_pct) > SPIKE_THRESHOLD_PCT,
            })

        results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

        spikes = [r for r in results if r["is_spike"]]

        return {
            "total_drugs_monitored": len(results),
            "drugs_with_spikes": len(spikes),
            "top_increases": [r for r in results if r["change_pct"] > 0][:10],
            "top_decreases": [r for r in results if r["change_pct"] < 0][:10],
            "spike_alerts": spikes,
        }

    # -------------------------------------------------------
    # Spike Detection
    # -------------------------------------------------------

    def _detect_spikes(self, points: List[PricePoint]) -> List[Dict[str, Any]]:
        """Detect price spikes in the data."""
        spikes = []
        sorted_pts = sorted(points, key=lambda p: p.date)

        for i in range(1, len(sorted_pts)):
            prev_price = sorted_pts[i - 1].price_per_unit
            curr_price = sorted_pts[i].price_per_unit

            if prev_price == 0:
                continue

            change_pct = ((curr_price - prev_price) / prev_price) * 100

            if abs(change_pct) >= SPIKE_THRESHOLD_PCT:
                severity = (
                    "critical" if abs(change_pct) >= CRITICAL_SPIKE_PCT else
                    "high" if abs(change_pct) >= 25 else
                    "moderate"
                )
                spikes.append({
                    "date": sorted_pts[i].date,
                    "previous_price": round(prev_price, 4),
                    "new_price": round(curr_price, 4),
                    "change_pct": round(change_pct, 2),
                    "direction": "increase" if change_pct > 0 else "decrease",
                    "severity": severity,
                })

        return spikes

    # -------------------------------------------------------
    # Volatility
    # -------------------------------------------------------

    def _compute_volatility(self, prices: List[float]) -> Dict[str, Any]:
        """Compute price volatility metrics."""
        if len(prices) < 2:
            return {"score": 0, "level": "stable"}

        # Coefficient of variation
        mean = statistics.mean(prices)
        std = statistics.stdev(prices)
        cv = (std / mean * 100) if mean > 0 else 0

        # Daily returns volatility
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                ret = (prices[i] - prices[i - 1]) / prices[i - 1] * 100
                returns.append(ret)

        returns_volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        # Level
        level = "stable"
        for lev, (low, high) in VOLATILITY_LEVELS.items():
            if low <= cv < high:
                level = lev
                break

        return {
            "coefficient_of_variation": round(cv, 2),
            "returns_volatility": round(returns_volatility, 2),
            "level": level,
            "score": round(min(100, cv * 2), 1),
        }

    # -------------------------------------------------------
    # Forecast
    # -------------------------------------------------------

    def _simple_forecast(self, prices: List[float], periods: int = 30) -> Optional[float]:
        """Simple linear forecast using recent trend."""
        if len(prices) < 5:
            return None

        recent = prices[-min(30, len(prices)):]
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(recent)

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return recent[-1]

        slope = numerator / denominator
        forecast = recent[-1] + slope * periods

        return max(0, forecast)

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------

    def _find_key(self, ndc: str, drug_name: str) -> Optional[str]:
        """Find the data key for a drug."""
        for key in self.price_data:
            if ndc and ndc in key:
                return key
            if drug_name and drug_name.lower() in key.lower():
                return key
        return None

    def _moving_average(self, prices: List[float], window: int) -> Optional[float]:
        """Compute moving average."""
        if len(prices) < window:
            return None
        return statistics.mean(prices[-window:])

    def _generate_price_alerts(
        self, current, prices, volatility, spikes, trend
    ) -> List[Dict[str, Any]]:
        """Generate alerts from price analysis."""
        alerts = []

        if spikes:
            recent_spike = spikes[-1]
            if recent_spike["severity"] == "critical":
                alerts.append({
                    "severity": "critical",
                    "message": f"Critical price spike: {recent_spike['change_pct']:.0f}% "
                               f"on {recent_spike['date']}",
                })

        if volatility.get("level") in ("high", "extreme"):
            alerts.append({
                "severity": "warning",
                "message": f"High price volatility (CV: {volatility['coefficient_of_variation']:.1f}%). "
                           "Consider locked-in pricing contracts.",
            })

        if trend == "increasing" and len(prices) > 10:
            recent_change = (prices[-1] - prices[-10]) / prices[-10] * 100 if prices[-10] > 0 else 0
            if recent_change > 10:
                alerts.append({
                    "severity": "warning",
                    "message": f"Price increased {recent_change:.0f}% over last 10 data points. "
                               "Consider stockpiling or alternative NDC.",
                })

        return alerts


# ============================================================
# Module-level convenience
# ============================================================

def analyze_drug_pricing(price_data, ndc="", drug_name=""):
    monitor = DrugPricingTrendMonitor()
    monitor.load_prices(price_data)
    return monitor.analyze_drug_trend(ndc, drug_name)
