"""
GetPaidRx - Medication Adherence & Outcomes Tracker
Tracks patient medication adherence using PDC (Proportion of Days Covered),
identifies non-adherent patients for intervention, and links adherence to
clinical and financial outcomes for Star Rating optimization.

Features:
- PDC calculation (CMS standard methodology)
- MPR (Medication Possession Ratio) alternative metric
- Adherence trend analysis with early warning detection
- Gap-in-therapy identification with outreach triggers
- Star Rating impact modeling (Medicare Part D)
- Adherence intervention ROI calculator
- Patient segmentation by risk and adherence patterns
"""
import json
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AdherenceStatus(Enum):
    ADHERENT = "adherent"           # PDC >= 80%
    PARTIALLY_ADHERENT = "partial"  # PDC 50-79%
    NON_ADHERENT = "non_adherent"   # PDC < 50%
    NEW_START = "new_start"         # < 60 days on therapy
    DISCONTINUED = "discontinued"    # No fills for > 90 days


class TherapyClass(Enum):
    """CMS Star Rating medication therapy classes."""
    RAS_ANTAGONISTS = "ras_antagonists"     # ACE/ARB (Hypertension)
    STATINS = "statins"                     # Cholesterol
    ORAL_DIABETES = "oral_diabetes"         # Diabetes non-insulin
    INSULIN = "insulin"                     # Diabetes insulin
    ANTIDEPRESSANTS = "antidepressants"     # Depression
    ANTICOAGULANTS = "anticoagulants"       # Blood thinners
    RESPIRATORY = "respiratory"             # COPD/Asthma
    OSTEOPOROSIS = "osteoporosis"           # Bone health
    OTHER = "other"


class InterventionType(Enum):
    PHONE_CALL = "phone_call"
    SMS_REMINDER = "sms_reminder"
    PHARMACIST_CONSULT = "pharmacist_consult"
    PRESCRIBER_NOTIFICATION = "prescriber_notification"
    SYNC_ENROLLMENT = "med_sync_enrollment"
    DELIVERY_SETUP = "home_delivery"
    COPAY_ASSISTANCE = "copay_assistance"
    THERAPY_REVIEW = "comprehensive_review"


@dataclass
class FillHistory:
    """A single fill in a patient's medication history."""
    fill_date: str  # YYYY-MM-DD
    days_supply: int
    quantity: float
    ndc: str
    drug_name: str
    prescriber_npi: str = ""
    pharmacy_npi: str = ""
    copay: float = 0.0
    is_mail_order: bool = False


@dataclass
class PatientTherapy:
    """A patient's therapy record for a medication class."""
    patient_id: str
    therapy_class: TherapyClass
    drug_name: str
    fills: List[FillHistory] = field(default_factory=list)
    start_date: str = ""
    interventions: List[Dict] = field(default_factory=list)
    notes: str = ""


@dataclass
class AdherenceResult:
    """Result of adherence calculation for a patient/therapy."""
    patient_id: str
    therapy_class: TherapyClass
    drug_name: str
    measurement_period_start: str
    measurement_period_end: str
    total_days_in_period: int
    days_covered: int
    pdc: float
    mpr: float
    status: AdherenceStatus
    fill_count: int
    avg_days_between_fills: float
    gaps: List[Dict] = field(default_factory=list)
    trend: str = ""  # improving, stable, declining
    risk_score: float = 0.0  # 0-100


class PDCCalculator:
    """CMS-standard PDC (Proportion of Days Covered) calculator."""

    def __init__(self):
        self.adherence_threshold = 0.80  # 80% PDC = adherent

    def calculate_pdc(
        self,
        fills: List[FillHistory],
        period_start: str,
        period_end: str
    ) -> AdherenceResult:
        """Calculate PDC for a list of fills within a measurement period."""
        if not fills:
            return self._empty_result(period_start, period_end)

        start = datetime.strptime(period_start, "%Y-%m-%d")
        end = datetime.strptime(period_end, "%Y-%m-%d")
        total_days = (end - start).days + 1

        if total_days <= 0:
            return self._empty_result(period_start, period_end)

        # Create day-level coverage array
        covered_days = [False] * total_days

        sorted_fills = sorted(fills, key=lambda f: f.fill_date)

        for fill in sorted_fills:
            fill_start = datetime.strptime(fill.fill_date, "%Y-%m-%d")
            fill_end = fill_start + timedelta(days=fill.days_supply - 1)

            # Clip to measurement period
            actual_start = max(fill_start, start)
            actual_end = min(fill_end, end)

            if actual_start > end or actual_end < start:
                continue

            start_idx = (actual_start - start).days
            end_idx = (actual_end - start).days

            for i in range(max(0, start_idx), min(total_days, end_idx + 1)):
                covered_days[i] = True

        days_covered = sum(covered_days)
        pdc = days_covered / total_days

        # Calculate MPR (total days supply / total days in period)
        total_supply = sum(f.days_supply for f in sorted_fills)
        mpr = min(total_supply / total_days, 1.0) if total_days > 0 else 0

        # Detect gaps
        gaps = self._detect_gaps(covered_days, start, min_gap_days=3)

        # Calculate average days between fills
        fill_dates = [
            datetime.strptime(f.fill_date, "%Y-%m-%d") for f in sorted_fills
        ]
        avg_between = 0.0
        if len(fill_dates) > 1:
            intervals = [
                (fill_dates[i + 1] - fill_dates[i]).days
                for i in range(len(fill_dates) - 1)
            ]
            avg_between = sum(intervals) / len(intervals)

        # Determine status
        if len(sorted_fills) == 1 and (end - datetime.strptime(sorted_fills[0].fill_date, "%Y-%m-%d")).days < 60:
            status = AdherenceStatus.NEW_START
        elif gaps and gaps[-1].get("gap_end", "") == period_end and gaps[-1].get("duration_days", 0) > 90:
            status = AdherenceStatus.DISCONTINUED
        elif pdc >= self.adherence_threshold:
            status = AdherenceStatus.ADHERENT
        elif pdc >= 0.50:
            status = AdherenceStatus.PARTIALLY_ADHERENT
        else:
            status = AdherenceStatus.NON_ADHERENT

        # Risk score (0-100, higher = more at risk)
        risk = self._calculate_risk_score(pdc, gaps, avg_between, sorted_fills)

        return AdherenceResult(
            patient_id="",  # Set by caller
            therapy_class=TherapyClass.OTHER,  # Set by caller
            drug_name=sorted_fills[0].drug_name if sorted_fills else "",
            measurement_period_start=period_start,
            measurement_period_end=period_end,
            total_days_in_period=total_days,
            days_covered=days_covered,
            pdc=round(pdc, 4),
            mpr=round(mpr, 4),
            status=status,
            fill_count=len(sorted_fills),
            avg_days_between_fills=round(avg_between, 1),
            gaps=gaps,
            risk_score=round(risk, 1)
        )

    def _detect_gaps(
        self,
        covered_days: List[bool],
        period_start: datetime,
        min_gap_days: int = 3
    ) -> List[Dict]:
        """Detect gaps in coverage."""
        gaps = []
        gap_start = None

        for i, covered in enumerate(covered_days):
            if not covered and gap_start is None:
                gap_start = i
            elif covered and gap_start is not None:
                gap_duration = i - gap_start
                if gap_duration >= min_gap_days:
                    gaps.append({
                        "gap_start": (period_start + timedelta(days=gap_start)).strftime("%Y-%m-%d"),
                        "gap_end": (period_start + timedelta(days=i - 1)).strftime("%Y-%m-%d"),
                        "duration_days": gap_duration
                    })
                gap_start = None

        # Handle gap at end of period
        if gap_start is not None:
            gap_duration = len(covered_days) - gap_start
            if gap_duration >= min_gap_days:
                gaps.append({
                    "gap_start": (period_start + timedelta(days=gap_start)).strftime("%Y-%m-%d"),
                    "gap_end": (period_start + timedelta(days=len(covered_days) - 1)).strftime("%Y-%m-%d"),
                    "duration_days": gap_duration
                })

        return gaps

    def _calculate_risk_score(
        self,
        pdc: float,
        gaps: List[Dict],
        avg_days_between: float,
        fills: List[FillHistory]
    ) -> float:
        """Calculate adherence risk score (0-100)."""
        risk = 0.0

        # PDC component (0-40 points)
        if pdc < 0.50:
            risk += 40
        elif pdc < 0.65:
            risk += 30
        elif pdc < 0.80:
            risk += 15
        else:
            risk += 0

        # Gap component (0-25 points)
        max_gap = max((g["duration_days"] for g in gaps), default=0)
        if max_gap > 60:
            risk += 25
        elif max_gap > 30:
            risk += 18
        elif max_gap > 14:
            risk += 10
        elif max_gap > 7:
            risk += 5

        # Recency component (0-20 points) - when was last fill?
        if fills:
            last_fill = datetime.strptime(fills[-1].fill_date, "%Y-%m-%d")
            days_since_last = (datetime.now() - last_fill).days
            expected_next = fills[-1].days_supply
            overdue = days_since_last - expected_next
            if overdue > 30:
                risk += 20
            elif overdue > 14:
                risk += 12
            elif overdue > 7:
                risk += 6

        # Cost barrier component (0-15 points)
        if fills:
            avg_copay = sum(f.copay for f in fills) / len(fills)
            if avg_copay > 75:
                risk += 15
            elif avg_copay > 50:
                risk += 10
            elif avg_copay > 25:
                risk += 5

        return min(100, risk)

    def _empty_result(self, start: str, end: str) -> AdherenceResult:
        """Return empty result when no fills exist."""
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        return AdherenceResult(
            patient_id="", therapy_class=TherapyClass.OTHER,
            drug_name="", measurement_period_start=start,
            measurement_period_end=end,
            total_days_in_period=(e - s).days + 1,
            days_covered=0, pdc=0.0, mpr=0.0,
            status=AdherenceStatus.NON_ADHERENT,
            fill_count=0, avg_days_between_fills=0.0,
            risk_score=100.0
        )


class StarRatingImpactModeler:
    """Models impact of adherence improvements on Medicare Part D Star Ratings."""

    # CMS 2026 Star Rating thresholds (approximate)
    STAR_THRESHOLDS = {
        TherapyClass.RAS_ANTAGONISTS: {5: 0.87, 4: 0.82, 3: 0.77, 2: 0.72},
        TherapyClass.STATINS: {5: 0.86, 4: 0.81, 3: 0.76, 2: 0.71},
        TherapyClass.ORAL_DIABETES: {5: 0.88, 4: 0.83, 3: 0.78, 2: 0.73},
    }

    # Revenue impact per star level (approximate rebate/bonus per member per month)
    REVENUE_PER_STAR = {5: 5.00, 4: 3.50, 3: 2.00, 2: 0.00, 1: -1.50}

    def calculate_current_star(
        self,
        therapy_class: TherapyClass,
        current_pdc_rate: float
    ) -> int:
        """Calculate current star rating for a therapy class."""
        thresholds = self.STAR_THRESHOLDS.get(therapy_class, {})
        for stars in [5, 4, 3, 2]:
            if current_pdc_rate >= thresholds.get(stars, 1.0):
                return stars
        return 1

    def model_improvement(
        self,
        therapy_class: TherapyClass,
        current_adherent_pct: float,  # % of patients with PDC >= 80%
        target_adherent_pct: float,
        total_patients: int,
        intervention_cost_per_patient: float = 15.0
    ) -> Dict[str, Any]:
        """Model financial impact of adherence improvement."""
        current_star = self.calculate_current_star(therapy_class, current_adherent_pct / 100)
        target_star = self.calculate_current_star(therapy_class, target_adherent_pct / 100)

        patients_to_convert = int(
            total_patients * (target_adherent_pct - current_adherent_pct) / 100
        )
        intervention_cost = patients_to_convert * intervention_cost_per_patient

        current_revenue = self.REVENUE_PER_STAR.get(current_star, 0) * total_patients * 12
        target_revenue = self.REVENUE_PER_STAR.get(target_star, 0) * total_patients * 12
        revenue_improvement = target_revenue - current_revenue

        # Additional revenue from increased fills (adherent patients fill more)
        avg_fills_per_year_adherent = 12
        avg_fills_per_year_non_adherent = 7
        additional_fills = patients_to_convert * (
            avg_fills_per_year_adherent - avg_fills_per_year_non_adherent
        )
        avg_margin_per_fill = 8.50
        fill_revenue = additional_fills * avg_margin_per_fill

        total_benefit = revenue_improvement + fill_revenue
        roi = ((total_benefit - intervention_cost) / intervention_cost * 100) if intervention_cost > 0 else 0

        return {
            "therapy_class": therapy_class.value,
            "current_adherent_pct": current_adherent_pct,
            "target_adherent_pct": target_adherent_pct,
            "current_star_rating": current_star,
            "projected_star_rating": target_star,
            "star_improvement": target_star - current_star,
            "patients_to_convert": patients_to_convert,
            "intervention_cost": round(intervention_cost, 2),
            "star_rating_revenue_impact": round(revenue_improvement, 2),
            "additional_fill_revenue": round(fill_revenue, 2),
            "total_annual_benefit": round(total_benefit, 2),
            "roi_pct": round(roi, 1),
            "payback_months": round(
                (intervention_cost / (total_benefit / 12)) if total_benefit > 0 else 999, 1
            ),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


class PatientSegmenter:
    """Segments patients by adherence risk for targeted interventions."""

    def segment_patients(
        self,
        adherence_results: List[AdherenceResult]
    ) -> Dict[str, Any]:
        """Segment patients into intervention groups."""
        segments = {
            "immediate_outreach": [],       # High risk, recently non-adherent
            "monitor_closely": [],           # Moderate risk, declining trend
            "prevention_maintenance": [],    # Currently adherent but with risk factors
            "stable_adherent": [],           # Low risk, consistently adherent
            "new_patient_support": [],       # New starts needing onboarding
            "re_engagement": [],             # Discontinued, might benefit from restart
        }

        for result in adherence_results:
            if result.status == AdherenceStatus.NEW_START:
                segments["new_patient_support"].append(self._patient_summary(result))
            elif result.status == AdherenceStatus.DISCONTINUED:
                segments["re_engagement"].append(self._patient_summary(result))
            elif result.risk_score >= 70:
                segments["immediate_outreach"].append(self._patient_summary(result))
            elif result.risk_score >= 40:
                segments["monitor_closely"].append(self._patient_summary(result))
            elif result.status == AdherenceStatus.ADHERENT and result.risk_score < 20:
                segments["stable_adherent"].append(self._patient_summary(result))
            else:
                segments["prevention_maintenance"].append(self._patient_summary(result))

        # Sort each segment by risk score
        for seg_name in segments:
            segments[seg_name].sort(key=lambda x: x["risk_score"], reverse=True)

        intervention_recommendations = {
            "immediate_outreach": [
                InterventionType.PHONE_CALL.value,
                InterventionType.PRESCRIBER_NOTIFICATION.value,
                InterventionType.COPAY_ASSISTANCE.value
            ],
            "monitor_closely": [
                InterventionType.SMS_REMINDER.value,
                InterventionType.SYNC_ENROLLMENT.value
            ],
            "prevention_maintenance": [
                InterventionType.SMS_REMINDER.value,
                InterventionType.DELIVERY_SETUP.value
            ],
            "new_patient_support": [
                InterventionType.PHARMACIST_CONSULT.value,
                InterventionType.THERAPY_REVIEW.value
            ],
            "re_engagement": [
                InterventionType.PHONE_CALL.value,
                InterventionType.PRESCRIBER_NOTIFICATION.value,
                InterventionType.THERAPY_REVIEW.value
            ]
        }

        return {
            "total_patients": len(adherence_results),
            "segments": {
                name: {
                    "count": len(patients),
                    "avg_risk_score": round(
                        sum(p["risk_score"] for p in patients) / len(patients), 1
                    ) if patients else 0,
                    "recommended_interventions": intervention_recommendations.get(name, []),
                    "patients": patients[:50]  # Top 50 per segment
                }
                for name, patients in segments.items()
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def _patient_summary(self, result: AdherenceResult) -> Dict:
        """Create patient summary for segmentation."""
        return {
            "patient_id": result.patient_id,
            "therapy_class": result.therapy_class.value,
            "drug_name": result.drug_name,
            "pdc": result.pdc,
            "status": result.status.value,
            "risk_score": result.risk_score,
            "fill_count": result.fill_count,
            "largest_gap_days": max(
                (g["duration_days"] for g in result.gaps), default=0
            ),
            "trend": result.trend
        }
