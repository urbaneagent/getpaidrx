"""
Multi-Location Pharmacy Performance Comparator
=================================================
Compares operational and financial metrics across multiple pharmacy
locations to identify best practices, underperforming sites, and
optimization opportunities for pharmacy chains and networks.

Features:
- Cross-location KPI benchmarking (revenue, margin, volume, efficiency)
- Staffing efficiency comparison with normalization
- Payer mix analysis by location
- Prescription volume trending with seasonal adjustments
- Inventory turnover and carrying cost comparison
- Patient retention and satisfaction scoring
- Service-level performance (wait times, fill accuracy)
- Location ranking with composite scoring
- Variance reporting with drill-down capability

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import math
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class MetricCategory(Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    CLINICAL = "clinical"
    PATIENT = "patient"
    STAFFING = "staffing"
    INVENTORY = "inventory"
    COMPLIANCE = "compliance"


class PerformanceTier(Enum):
    EXCELLENT = "excellent"       # Top 10%
    ABOVE_AVERAGE = "above_average"  # 10-35%
    AVERAGE = "average"           # 35-65%
    BELOW_AVERAGE = "below_average"  # 65-90%
    NEEDS_IMPROVEMENT = "needs_improvement"  # Bottom 10%


@dataclass
class LocationProfile:
    """Profile data for a pharmacy location."""
    location_id: str
    name: str
    address: str
    market_type: str              # urban, suburban, rural
    open_hours_per_week: float
    staff_pharmacist_fte: float
    staff_tech_fte: float
    square_footage: int
    has_drive_through: bool = False
    has_clinic: bool = False
    specialties: List[str] = field(default_factory=list)
    opened_date: str = ""
    notes: str = ""


@dataclass
class LocationMetrics:
    """Performance metrics for a pharmacy location over a period."""
    location_id: str
    period_start: str
    period_end: str

    # Financial
    total_revenue: float = 0
    gross_margin: float = 0
    gross_margin_pct: float = 0
    net_margin: float = 0
    net_margin_pct: float = 0
    revenue_per_rx: float = 0
    cogs: float = 0
    operating_expenses: float = 0
    dir_fees_paid: float = 0

    # Volume
    total_rx_count: int = 0
    new_rx_count: int = 0
    refill_count: int = 0
    transfer_in_count: int = 0
    transfer_out_count: int = 0
    otc_sales: float = 0
    specialty_rx_count: int = 0

    # Efficiency
    rx_per_labor_hour: float = 0
    avg_fill_time_minutes: float = 0
    avg_wait_time_minutes: float = 0
    fill_accuracy_rate: float = 0
    claim_rejection_rate: float = 0

    # Patient
    unique_patients: int = 0
    new_patients: int = 0
    patient_retention_rate: float = 0
    satisfaction_score: float = 0
    nps_score: float = 0
    complaint_count: int = 0

    # Inventory
    inventory_turns: float = 0
    carrying_cost: float = 0
    dead_stock_value: float = 0
    shrinkage_value: float = 0
    avg_days_on_hand: float = 0

    # Clinical
    immunizations_given: int = 0
    mtm_sessions: int = 0
    clinical_interventions: int = 0
    adherence_calls: int = 0
    star_rating_impact: float = 0

    # Payer mix
    payer_mix: Dict[str, float] = field(default_factory=dict)
    generic_dispensing_rate: float = 0


@dataclass
class LocationComparison:
    """Comparison result between locations for a single metric."""
    metric_name: str
    category: MetricCategory
    values: Dict[str, float]            # location_id → value
    mean: float
    median: float
    std_dev: float
    min_value: float
    min_location: str
    max_value: float
    max_location: str
    rankings: Dict[str, int]            # location_id → rank (1=best)
    higher_is_better: bool = True


class MetricNormalizer:
    """Normalizes metrics for fair comparison across differently-sized locations."""

    @staticmethod
    def per_fte(value: float, pharmacist_fte: float, tech_fte: float) -> float:
        total_fte = pharmacist_fte + tech_fte
        return value / total_fte if total_fte > 0 else 0

    @staticmethod
    def per_sqft(value: float, square_footage: int) -> float:
        return value / square_footage if square_footage > 0 else 0

    @staticmethod
    def per_rx(value: float, rx_count: int) -> float:
        return value / rx_count if rx_count > 0 else 0

    @staticmethod
    def per_hour(value: float, hours_per_week: float, weeks: float = 4.33) -> float:
        total_hours = hours_per_week * weeks
        return value / total_hours if total_hours > 0 else 0

    @staticmethod
    def z_score(value: float, mean: float, std_dev: float) -> float:
        return (value - mean) / std_dev if std_dev > 0 else 0


class CompositeScorer:
    """Calculates composite performance scores for location ranking."""

    WEIGHT_PROFILES = {
        "balanced": {
            MetricCategory.FINANCIAL: 0.30,
            MetricCategory.OPERATIONAL: 0.25,
            MetricCategory.PATIENT: 0.20,
            MetricCategory.CLINICAL: 0.15,
            MetricCategory.INVENTORY: 0.10
        },
        "financial_focus": {
            MetricCategory.FINANCIAL: 0.50,
            MetricCategory.OPERATIONAL: 0.20,
            MetricCategory.PATIENT: 0.10,
            MetricCategory.CLINICAL: 0.10,
            MetricCategory.INVENTORY: 0.10
        },
        "patient_centric": {
            MetricCategory.FINANCIAL: 0.15,
            MetricCategory.OPERATIONAL: 0.20,
            MetricCategory.PATIENT: 0.40,
            MetricCategory.CLINICAL: 0.20,
            MetricCategory.INVENTORY: 0.05
        }
    }

    def calculate_composite_score(self, location_id: str,
                                   comparisons: List[LocationComparison],
                                   profile: str = "balanced") -> Dict:
        weights = self.WEIGHT_PROFILES.get(profile, self.WEIGHT_PROFILES["balanced"])
        total_count = len(comparisons)
        if total_count == 0:
            return {"location_id": location_id, "score": 0, "grade": "N/A"}

        category_scores = defaultdict(list)

        for comp in comparisons:
            if location_id not in comp.rankings:
                continue

            rank = comp.rankings[location_id]
            total_locations = len(comp.rankings)
            # Normalize rank to 0-100 (1st = 100, last = 0)
            percentile = ((total_locations - rank) / (total_locations - 1) * 100) if total_locations > 1 else 100

            category_scores[comp.category].append(percentile)

        # Calculate weighted score
        weighted_sum = 0
        weight_sum = 0

        for category, scores in category_scores.items():
            cat_avg = sum(scores) / len(scores)
            weight = weights.get(category, 0.1)
            weighted_sum += cat_avg * weight
            weight_sum += weight

        composite = weighted_sum / weight_sum if weight_sum > 0 else 0

        return {
            "location_id": location_id,
            "composite_score": round(composite, 1),
            "grade": self._score_to_grade(composite),
            "tier": self._score_to_tier(composite).value,
            "category_scores": {
                cat.value: round(sum(scores) / len(scores), 1)
                for cat, scores in category_scores.items()
            },
            "weight_profile": profile
        }

    def _score_to_grade(self, score: float) -> str:
        if score >= 95: return "A+"
        if score >= 90: return "A"
        if score >= 85: return "A-"
        if score >= 80: return "B+"
        if score >= 75: return "B"
        if score >= 70: return "B-"
        if score >= 65: return "C+"
        if score >= 60: return "C"
        if score >= 55: return "C-"
        if score >= 50: return "D"
        return "F"

    def _score_to_tier(self, score: float) -> PerformanceTier:
        if score >= 90: return PerformanceTier.EXCELLENT
        if score >= 75: return PerformanceTier.ABOVE_AVERAGE
        if score >= 50: return PerformanceTier.AVERAGE
        if score >= 25: return PerformanceTier.BELOW_AVERAGE
        return PerformanceTier.NEEDS_IMPROVEMENT


class VarianceAnalyzer:
    """Analyzes variance between locations and identifies opportunities."""

    def analyze_variance(self, comparisons: List[LocationComparison]) -> List[Dict]:
        """Identify the metrics with the highest variance (biggest opportunities)."""
        variance_results = []

        for comp in comparisons:
            if comp.std_dev == 0 or comp.mean == 0:
                continue

            cv = comp.std_dev / abs(comp.mean) * 100  # Coefficient of variation

            gap = comp.max_value - comp.min_value
            gap_pct = (gap / comp.mean * 100) if comp.mean != 0 else 0

            opportunity_value = gap * 0.5  # Conservative: closing half the gap

            variance_results.append({
                "metric": comp.metric_name,
                "category": comp.category.value,
                "mean": round(comp.mean, 2),
                "std_dev": round(comp.std_dev, 2),
                "cv_pct": round(cv, 1),
                "best_location": comp.max_location if comp.higher_is_better else comp.min_location,
                "best_value": comp.max_value if comp.higher_is_better else comp.min_value,
                "worst_location": comp.min_location if comp.higher_is_better else comp.max_location,
                "worst_value": comp.min_value if comp.higher_is_better else comp.max_value,
                "gap": round(gap, 2),
                "gap_pct": round(gap_pct, 1),
                "estimated_opportunity": round(opportunity_value, 2),
                "higher_is_better": comp.higher_is_better
            })

        return sorted(variance_results, key=lambda x: x["cv_pct"], reverse=True)


class MultiLocationComparator:
    """
    Main comparator engine for multi-location pharmacy performance.
    
    Usage:
        comparator = MultiLocationComparator()
        comparator.add_location(profile, metrics)
        
        results = comparator.compare_all()
        rankings = comparator.rank_locations()
        opportunities = comparator.find_opportunities()
    """

    def __init__(self):
        self.locations: Dict[str, LocationProfile] = {}
        self.metrics: Dict[str, LocationMetrics] = {}
        self.normalizer = MetricNormalizer()
        self.scorer = CompositeScorer()
        self.variance_analyzer = VarianceAnalyzer()

    def add_location(self, profile: LocationProfile, metrics: LocationMetrics):
        self.locations[profile.location_id] = profile
        self.metrics[profile.location_id] = metrics

    def compare_metric(self, metric_name: str, category: MetricCategory,
                       higher_is_better: bool = True) -> LocationComparison:
        """Compare a single metric across all locations."""
        values = {}

        for loc_id, m in self.metrics.items():
            value = getattr(m, metric_name, None)
            if value is not None:
                values[loc_id] = float(value)

        if not values:
            return LocationComparison(
                metric_name=metric_name, category=category,
                values={}, mean=0, median=0, std_dev=0,
                min_value=0, min_location="", max_value=0, max_location="",
                rankings={}, higher_is_better=higher_is_better
            )

        vals = list(values.values())
        mean = sum(vals) / len(vals)
        sorted_vals = sorted(vals)
        median = sorted_vals[len(sorted_vals) // 2]
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        std_dev = math.sqrt(variance)

        min_loc = min(values, key=values.get)
        max_loc = max(values, key=values.get)

        # Rank (1 = best)
        if higher_is_better:
            sorted_locs = sorted(values.items(), key=lambda x: x[1], reverse=True)
        else:
            sorted_locs = sorted(values.items(), key=lambda x: x[1])

        rankings = {loc: rank + 1 for rank, (loc, _) in enumerate(sorted_locs)}

        return LocationComparison(
            metric_name=metric_name,
            category=category,
            values=values,
            mean=round(mean, 2),
            median=round(median, 2),
            std_dev=round(std_dev, 2),
            min_value=round(min(vals), 2),
            min_location=min_loc,
            max_value=round(max(vals), 2),
            max_location=max_loc,
            rankings=rankings,
            higher_is_better=higher_is_better
        )

    def compare_all(self) -> Dict:
        """Run full comparison across all standard metrics."""
        metrics_config = [
            ("total_revenue", MetricCategory.FINANCIAL, True),
            ("gross_margin_pct", MetricCategory.FINANCIAL, True),
            ("net_margin_pct", MetricCategory.FINANCIAL, True),
            ("revenue_per_rx", MetricCategory.FINANCIAL, True),
            ("total_rx_count", MetricCategory.OPERATIONAL, True),
            ("rx_per_labor_hour", MetricCategory.OPERATIONAL, True),
            ("avg_fill_time_minutes", MetricCategory.OPERATIONAL, False),
            ("avg_wait_time_minutes", MetricCategory.OPERATIONAL, False),
            ("fill_accuracy_rate", MetricCategory.OPERATIONAL, True),
            ("claim_rejection_rate", MetricCategory.OPERATIONAL, False),
            ("patient_retention_rate", MetricCategory.PATIENT, True),
            ("satisfaction_score", MetricCategory.PATIENT, True),
            ("nps_score", MetricCategory.PATIENT, True),
            ("new_patients", MetricCategory.PATIENT, True),
            ("complaint_count", MetricCategory.PATIENT, False),
            ("inventory_turns", MetricCategory.INVENTORY, True),
            ("dead_stock_value", MetricCategory.INVENTORY, False),
            ("shrinkage_value", MetricCategory.INVENTORY, False),
            ("avg_days_on_hand", MetricCategory.INVENTORY, False),
            ("immunizations_given", MetricCategory.CLINICAL, True),
            ("mtm_sessions", MetricCategory.CLINICAL, True),
            ("clinical_interventions", MetricCategory.CLINICAL, True),
            ("generic_dispensing_rate", MetricCategory.CLINICAL, True),
        ]

        comparisons = []
        for metric_name, category, higher_is_better in metrics_config:
            comp = self.compare_metric(metric_name, category, higher_is_better)
            if comp.values:
                comparisons.append(comp)

        return {
            "locations_compared": len(self.locations),
            "metrics_compared": len(comparisons),
            "comparisons": [
                {
                    "metric": c.metric_name,
                    "category": c.category.value,
                    "mean": c.mean,
                    "std_dev": c.std_dev,
                    "best": {"location": c.max_location if c.higher_is_better else c.min_location,
                             "value": c.max_value if c.higher_is_better else c.min_value},
                    "worst": {"location": c.min_location if c.higher_is_better else c.max_location,
                              "value": c.min_value if c.higher_is_better else c.max_value},
                    "rankings": c.rankings
                }
                for c in comparisons
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

    def rank_locations(self, weight_profile: str = "balanced") -> List[Dict]:
        """Rank all locations using composite scoring."""
        metrics_config = [
            ("total_revenue", MetricCategory.FINANCIAL, True),
            ("gross_margin_pct", MetricCategory.FINANCIAL, True),
            ("net_margin_pct", MetricCategory.FINANCIAL, True),
            ("rx_per_labor_hour", MetricCategory.OPERATIONAL, True),
            ("fill_accuracy_rate", MetricCategory.OPERATIONAL, True),
            ("avg_wait_time_minutes", MetricCategory.OPERATIONAL, False),
            ("patient_retention_rate", MetricCategory.PATIENT, True),
            ("satisfaction_score", MetricCategory.PATIENT, True),
            ("nps_score", MetricCategory.PATIENT, True),
            ("inventory_turns", MetricCategory.INVENTORY, True),
            ("immunizations_given", MetricCategory.CLINICAL, True),
            ("generic_dispensing_rate", MetricCategory.CLINICAL, True),
        ]

        comparisons = []
        for metric_name, category, hib in metrics_config:
            comp = self.compare_metric(metric_name, category, hib)
            if comp.values:
                comparisons.append(comp)

        rankings = []
        for loc_id in self.locations:
            score = self.scorer.calculate_composite_score(loc_id, comparisons, weight_profile)
            loc = self.locations[loc_id]
            score["name"] = loc.name
            score["market_type"] = loc.market_type
            rankings.append(score)

        rankings.sort(key=lambda x: x["composite_score"], reverse=True)

        # Assign final ranks
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def find_opportunities(self) -> Dict:
        """Identify performance improvement opportunities."""
        all_comps = []
        metrics_config = [
            ("gross_margin_pct", MetricCategory.FINANCIAL, True),
            ("rx_per_labor_hour", MetricCategory.OPERATIONAL, True),
            ("avg_wait_time_minutes", MetricCategory.OPERATIONAL, False),
            ("patient_retention_rate", MetricCategory.PATIENT, True),
            ("inventory_turns", MetricCategory.INVENTORY, True),
            ("generic_dispensing_rate", MetricCategory.CLINICAL, True),
        ]

        for metric_name, category, hib in metrics_config:
            comp = self.compare_metric(metric_name, category, hib)
            if comp.values:
                all_comps.append(comp)

        variances = self.variance_analyzer.analyze_variance(all_comps)

        return {
            "opportunities": variances,
            "total_estimated_value": round(sum(v["estimated_opportunity"] for v in variances), 2),
            "top_3_priorities": variances[:3],
            "generated_at": datetime.utcnow().isoformat()
        }

    def generate_location_report(self, location_id: str) -> Dict:
        """Generate a detailed report card for a single location."""
        if location_id not in self.locations:
            return {"error": "Location not found"}

        loc = self.locations[location_id]
        metrics = self.metrics.get(location_id)
        if not metrics:
            return {"error": "No metrics for location"}

        rankings = self.rank_locations()
        loc_ranking = next((r for r in rankings if r["location_id"] == location_id), None)

        return {
            "location": {
                "id": loc.location_id,
                "name": loc.name,
                "address": loc.address,
                "market_type": loc.market_type,
                "hours_per_week": loc.open_hours_per_week,
                "total_fte": loc.staff_pharmacist_fte + loc.staff_tech_fte
            },
            "financial_summary": {
                "revenue": metrics.total_revenue,
                "gross_margin_pct": metrics.gross_margin_pct,
                "net_margin_pct": metrics.net_margin_pct,
                "revenue_per_rx": metrics.revenue_per_rx,
                "dir_fees": metrics.dir_fees_paid
            },
            "operational_summary": {
                "total_rx": metrics.total_rx_count,
                "rx_per_labor_hour": metrics.rx_per_labor_hour,
                "fill_time_min": metrics.avg_fill_time_minutes,
                "wait_time_min": metrics.avg_wait_time_minutes,
                "fill_accuracy": metrics.fill_accuracy_rate,
                "rejection_rate": metrics.claim_rejection_rate
            },
            "patient_summary": {
                "unique_patients": metrics.unique_patients,
                "retention_rate": metrics.patient_retention_rate,
                "satisfaction": metrics.satisfaction_score,
                "nps": metrics.nps_score,
                "complaints": metrics.complaint_count
            },
            "ranking": loc_ranking,
            "generated_at": datetime.utcnow().isoformat()
        }


# FastAPI Integration
try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1/locations", tags=["Multi-Location"])
    comparator = MultiLocationComparator()

    @router.get("/compare")
    async def compare_all():
        return comparator.compare_all()

    @router.get("/rankings")
    async def rankings(profile: str = "balanced"):
        return {"rankings": comparator.rank_locations(profile)}

    @router.get("/opportunities")
    async def opportunities():
        return comparator.find_opportunities()

    @router.get("/{location_id}/report")
    async def location_report(location_id: str):
        result = comparator.generate_location_report(location_id)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result

except ImportError:
    router = None
