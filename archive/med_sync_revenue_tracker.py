"""
GetPaidRx - Medication Synchronization (Med Sync) Revenue Tracker
Tracks revenue impact of medication synchronization programs where
multiple prescriptions are aligned to a single fill date. Calculates
adherence improvements, partial fill revenue, appointment scheduling
optimization, and long-term patient retention value.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import math
import statistics


class SyncStatus(Enum):
    ENROLLED = "enrolled"
    ACTIVE = "active"
    PAUSED = "paused"
    GRADUATED = "graduated"  # Stable adherence, less monitoring
    DROPPED = "dropped"


class MedicationCategory(Enum):
    CHRONIC = "chronic"
    ACUTE = "acute"
    MAINTENANCE = "maintenance"
    SPECIALTY = "specialty"
    CONTROLLED = "controlled"


@dataclass
class SyncMedication:
    """Individual medication in a sync program."""
    ndc: str
    drug_name: str
    quantity: float
    days_supply: int
    is_brand: bool = False
    category: MedicationCategory = MedicationCategory.CHRONIC
    current_adherence_pdc: float = 0.0  # Proportion of Days Covered
    avg_reimbursement: float = 0.0
    avg_dispensing_fee: float = 0.0
    avg_acquisition_cost: float = 0.0
    short_fill_quantity: float = 0.0  # For alignment fill
    short_fill_days: int = 0
    payer: str = ""


@dataclass
class SyncPatient:
    """Patient enrolled in med sync program."""
    patient_id: str
    name: str
    sync_date: int = 1  # Day of month for sync pickup
    status: SyncStatus = SyncStatus.ENROLLED
    enrolled_date: str = ""
    medications: List[SyncMedication] = field(default_factory=list)
    total_medications: int = 0
    pre_sync_adherence: float = 0.0  # Average PDC before enrollment
    current_adherence: float = 0.0  # Current PDC
    contact_preference: str = "phone"  # phone, text, email
    missed_pickups: int = 0
    last_sync_date: Optional[str] = None


@dataclass
class SyncFillEvent:
    """Record of a sync fill event."""
    event_id: str
    patient_id: str
    fill_date: str
    medications_filled: int
    total_reimbursement: float = 0.0
    total_dispensing_fees: float = 0.0
    total_acquisition: float = 0.0
    total_profit: float = 0.0
    short_fills_count: int = 0
    short_fill_revenue: float = 0.0
    patient_copay_total: float = 0.0
    was_missed: bool = False
    pickup_time_minutes: int = 0


@dataclass
class RevenueProjection:
    """Revenue projection for a sync patient."""
    patient_id: str
    monthly_revenue: float = 0.0
    monthly_profit: float = 0.0
    annual_revenue: float = 0.0
    annual_profit: float = 0.0
    short_fill_revenue_annual: float = 0.0
    dispensing_fee_uplift: float = 0.0
    adherence_improvement_value: float = 0.0
    retention_value_annual: float = 0.0
    total_annual_value: float = 0.0


class AdherenceImpactCalculator:
    """Calculates financial impact of adherence improvements."""

    # CMS Star Rating PDC thresholds
    STAR_THRESHOLDS = {
        "diabetes": 0.80,
        "hypertension": 0.80,
        "cholesterol": 0.80,
    }

    # Revenue per star rating improvement (pharmacy network incentives)
    STAR_RATING_VALUE = {
        3: 0.0,
        4: 2500.0,   # Annual bonus for 4-star
        5: 5000.0,   # Annual bonus for 5-star
    }

    def calculate_pdc(self, days_covered: int, observation_days: int = 365) -> float:
        """Calculate Proportion of Days Covered."""
        if observation_days <= 0:
            return 0.0
        return min(round(days_covered / observation_days, 4), 1.0)

    def estimate_adherence_revenue_impact(
        self, pre_sync_pdc: float, post_sync_pdc: float,
        num_patients_at_threshold: int,
    ) -> Dict[str, Any]:
        """Estimate revenue impact of adherence improvements on star ratings."""
        improvement = post_sync_pdc - pre_sync_pdc

        # Patients crossing threshold
        patients_now_adherent = 0
        if pre_sync_pdc < 0.80 and post_sync_pdc >= 0.80:
            patients_now_adherent = num_patients_at_threshold

        # Network incentive estimation
        star_bonus = 0.0
        if post_sync_pdc >= 0.90:
            star_bonus = self.STAR_RATING_VALUE[5]
        elif post_sync_pdc >= 0.80:
            star_bonus = self.STAR_RATING_VALUE[4]

        # Per-patient additional fill revenue (higher adherence = more fills)
        additional_fills_per_year = improvement * 12  # Approximate
        per_fill_value = 8.50  # Average profit per fill

        return {
            "pdc_improvement": round(improvement, 4),
            "patients_newly_adherent": patients_now_adherent,
            "additional_fills_per_year": round(additional_fills_per_year, 1),
            "additional_fill_revenue": round(additional_fills_per_year * per_fill_value, 2),
            "star_rating_bonus": star_bonus,
            "total_adherence_value": round(
                additional_fills_per_year * per_fill_value + star_bonus, 2
            ),
        }


class ShortFillCalculator:
    """Calculates revenue from alignment (short) fills."""

    def calculate_short_fill(
        self, medication: SyncMedication, target_sync_date: int
    ) -> Dict[str, Any]:
        """Calculate short fill quantity and revenue for alignment."""
        today = datetime.now()

        # Days until next sync date
        if today.day <= target_sync_date:
            sync_day = today.replace(day=target_sync_date)
        else:
            # Next month
            if today.month == 12:
                sync_day = today.replace(year=today.year + 1, month=1, day=target_sync_date)
            else:
                sync_day = today.replace(month=today.month + 1, day=target_sync_date)

        days_to_sync = (sync_day - today).days
        if days_to_sync <= 0 or days_to_sync >= medication.days_supply:
            return {"needs_short_fill": False}

        # Calculate partial quantity
        daily_dose = medication.quantity / medication.days_supply
        short_qty = math.ceil(daily_dose * days_to_sync)
        short_days = days_to_sync

        # Revenue calculation (prorated)
        prorate_factor = short_days / medication.days_supply
        short_reimb = medication.avg_reimbursement * prorate_factor
        short_disp_fee = medication.avg_dispensing_fee  # Full dispensing fee usually
        short_acq = medication.avg_acquisition_cost * prorate_factor

        return {
            "needs_short_fill": True,
            "short_quantity": short_qty,
            "short_days": short_days,
            "short_reimbursement": round(short_reimb, 2),
            "dispensing_fee": round(short_disp_fee, 2),
            "acquisition_cost": round(short_acq, 2),
            "profit": round(short_reimb + short_disp_fee - short_acq, 2),
            "alignment_date": sync_day.strftime("%Y-%m-%d"),
        }


class RetentionValueCalculator:
    """Calculates long-term patient retention value."""

    # Average patient lifetime at pharmacy without sync: 18 months
    # With sync: 36 months
    AVG_LIFETIME_NO_SYNC = 18  # months
    AVG_LIFETIME_WITH_SYNC = 36  # months

    def calculate_retention_value(
        self, monthly_profit: float, avg_medications: int
    ) -> Dict[str, Any]:
        """Calculate incremental retention value from sync enrollment."""
        no_sync_ltv = monthly_profit * self.AVG_LIFETIME_NO_SYNC
        sync_ltv = monthly_profit * self.AVG_LIFETIME_WITH_SYNC
        incremental = sync_ltv - no_sync_ltv

        return {
            "no_sync_ltv": round(no_sync_ltv, 2),
            "sync_ltv": round(sync_ltv, 2),
            "incremental_ltv": round(incremental, 2),
            "retention_months_gained": self.AVG_LIFETIME_WITH_SYNC - self.AVG_LIFETIME_NO_SYNC,
            "annualized_value": round(incremental / (self.AVG_LIFETIME_WITH_SYNC / 12), 2),
        }


class MedSyncRevenueTracker:
    """Main tracker for med sync program financial performance."""

    def __init__(self):
        self.patients: Dict[str, SyncPatient] = {}
        self.fill_events: List[SyncFillEvent] = []
        self.adherence_calc = AdherenceImpactCalculator()
        self.short_fill_calc = ShortFillCalculator()
        self.retention_calc = RetentionValueCalculator()

    def enroll_patient(self, patient: SyncPatient) -> Dict:
        """Enroll patient in med sync program."""
        patient.enrolled_date = datetime.now().isoformat()
        patient.status = SyncStatus.ACTIVE
        patient.total_medications = len(patient.medications)

        # Calculate pre-sync adherence
        if patient.medications:
            pdcs = [m.current_adherence_pdc for m in patient.medications if m.current_adherence_pdc > 0]
            patient.pre_sync_adherence = statistics.mean(pdcs) if pdcs else 0.0

        self.patients[patient.patient_id] = patient

        # Calculate alignment fills needed
        alignment_fills = []
        for med in patient.medications:
            result = self.short_fill_calc.calculate_short_fill(med, patient.sync_date)
            if result.get("needs_short_fill"):
                alignment_fills.append({
                    "drug": med.drug_name,
                    **result,
                })

        return {
            "patient_id": patient.patient_id,
            "status": "enrolled",
            "sync_date": patient.sync_date,
            "medications": patient.total_medications,
            "pre_sync_adherence": round(patient.pre_sync_adherence, 4),
            "alignment_fills_needed": len(alignment_fills),
            "alignment_fills": alignment_fills,
            "alignment_revenue": round(
                sum(f.get("profit", 0) for f in alignment_fills), 2
            ),
        }

    def project_patient_revenue(self, patient_id: str) -> RevenueProjection:
        """Project annual revenue for a sync patient."""
        patient = self.patients.get(patient_id)
        if not patient:
            return RevenueProjection(patient_id=patient_id)

        proj = RevenueProjection(patient_id=patient_id)

        # Monthly revenue from regular fills
        for med in patient.medications:
            fills_per_month = 30 / max(med.days_supply, 1)
            monthly_reimb = med.avg_reimbursement * fills_per_month
            monthly_disp = med.avg_dispensing_fee * fills_per_month
            monthly_acq = med.avg_acquisition_cost * fills_per_month

            proj.monthly_revenue += monthly_reimb + monthly_disp
            proj.monthly_profit += (monthly_reimb + monthly_disp - monthly_acq)

        proj.monthly_revenue = round(proj.monthly_revenue, 2)
        proj.monthly_profit = round(proj.monthly_profit, 2)
        proj.annual_revenue = round(proj.monthly_revenue * 12, 2)
        proj.annual_profit = round(proj.monthly_profit * 12, 2)

        # Short fill revenue (initial alignment + annual refills)
        alignment_revenue = 0
        for med in patient.medications:
            sf = self.short_fill_calc.calculate_short_fill(med, patient.sync_date)
            if sf.get("needs_short_fill"):
                alignment_revenue += sf.get("profit", 0)
        proj.short_fill_revenue_annual = round(alignment_revenue, 2)

        # Dispensing fee uplift (more fills per year with better adherence)
        adherence_improvement = 0.15  # Expected 15% PDC improvement
        additional_fills = adherence_improvement * len(patient.medications) * 12
        avg_disp_fee = 2.50
        proj.dispensing_fee_uplift = round(additional_fills * avg_disp_fee, 2)

        # Adherence star rating value
        adherence_impact = self.adherence_calc.estimate_adherence_revenue_impact(
            patient.pre_sync_adherence,
            min(patient.pre_sync_adherence + adherence_improvement, 1.0),
            1,
        )
        proj.adherence_improvement_value = adherence_impact["total_adherence_value"]

        # Retention value
        retention = self.retention_calc.calculate_retention_value(
            proj.monthly_profit, patient.total_medications
        )
        proj.retention_value_annual = retention["annualized_value"]

        # Total value
        proj.total_annual_value = round(
            proj.annual_profit +
            proj.short_fill_revenue_annual +
            proj.dispensing_fee_uplift +
            proj.adherence_improvement_value +
            proj.retention_value_annual,
            2,
        )

        return proj

    def get_program_summary(self) -> Dict[str, Any]:
        """Get overall med sync program metrics."""
        if not self.patients:
            return {"total_patients": 0}

        active = [p for p in self.patients.values() if p.status == SyncStatus.ACTIVE]
        total_meds = sum(p.total_medications for p in active)

        # Aggregate projections
        total_annual_value = 0
        total_annual_profit = 0
        for p in active:
            proj = self.project_patient_revenue(p.patient_id)
            total_annual_value += proj.total_annual_value
            total_annual_profit += proj.annual_profit

        # Adherence stats
        pre_adherence = [p.pre_sync_adherence for p in active if p.pre_sync_adherence > 0]
        avg_pre = statistics.mean(pre_adherence) if pre_adherence else 0

        return {
            "total_patients": len(self.patients),
            "active_patients": len(active),
            "total_medications_synced": total_meds,
            "avg_meds_per_patient": round(total_meds / max(len(active), 1), 1),
            "avg_pre_sync_adherence": round(avg_pre, 4),
            "estimated_post_sync_adherence": round(min(avg_pre + 0.15, 1.0), 4),
            "total_annual_value": round(total_annual_value, 2),
            "total_annual_profit": round(total_annual_profit, 2),
            "avg_value_per_patient": round(total_annual_value / max(len(active), 1), 2),
            "program_roi_pct": round(
                (total_annual_value / max(total_annual_profit, 1) - 1) * 100, 1
            ),
        }

    def generate_program_report(self) -> str:
        """Generate comprehensive med sync program report."""
        summary = self.get_program_summary()

        lines = [
            f"{'='*60}",
            f"  MEDICATION SYNCHRONIZATION PROGRAM REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"{'='*60}",
            f"",
            f"  📊 PROGRAM OVERVIEW",
            f"  {'─'*45}",
            f"  Total Enrolled:      {summary.get('total_patients', 0):>8}",
            f"  Active Patients:     {summary.get('active_patients', 0):>8}",
            f"  Medications Synced:  {summary.get('total_medications_synced', 0):>8}",
            f"  Avg Meds/Patient:    {summary.get('avg_meds_per_patient', 0):>8.1f}",
            f"",
            f"  💊 ADHERENCE IMPACT",
            f"  {'─'*45}",
            f"  Pre-Sync PDC:        {summary.get('avg_pre_sync_adherence', 0):>8.1%}",
            f"  Post-Sync PDC (est): {summary.get('estimated_post_sync_adherence', 0):>8.1%}",
            f"  Improvement:         {summary.get('estimated_post_sync_adherence', 0) - summary.get('avg_pre_sync_adherence', 0):>8.1%}",
            f"",
            f"  💰 FINANCIAL IMPACT (ANNUAL)",
            f"  {'─'*45}",
            f"  Total Program Value: ${summary.get('total_annual_value', 0):>10,.2f}",
            f"  Direct Profit:       ${summary.get('total_annual_profit', 0):>10,.2f}",
            f"  Avg Value/Patient:   ${summary.get('avg_value_per_patient', 0):>10,.2f}",
            f"  Program ROI:         {summary.get('program_roi_pct', 0):>10.1f}%",
        ]

        # Top patients by value
        lines.extend([f"", f"  🏆 TOP PATIENTS BY VALUE", f"  {'─'*45}"])
        patient_values = []
        for p in self.patients.values():
            if p.status == SyncStatus.ACTIVE:
                proj = self.project_patient_revenue(p.patient_id)
                patient_values.append((p, proj))

        patient_values.sort(key=lambda x: x[1].total_annual_value, reverse=True)
        for p, proj in patient_values[:5]:
            lines.append(
                f"  {p.name:25s} {p.total_medications} meds  "
                f"${proj.total_annual_value:>8,.2f}/yr"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    tracker = MedSyncRevenueTracker()

    # Enroll test patients
    patients = [
        SyncPatient(
            patient_id="PT-001", name="Robert Johnson", sync_date=15,
            medications=[
                SyncMedication("11111-001-30", "Metformin 500mg", 60, 30,
                               current_adherence_pdc=0.72, avg_reimbursement=8.50,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=2.10, payer="Anthem"),
                SyncMedication("11111-002-30", "Lisinopril 10mg", 30, 30,
                               current_adherence_pdc=0.68, avg_reimbursement=6.20,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.50, payer="Anthem"),
                SyncMedication("11111-003-30", "Atorvastatin 20mg", 30, 30,
                               current_adherence_pdc=0.75, avg_reimbursement=7.80,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.80, payer="Anthem"),
            ],
        ),
        SyncPatient(
            patient_id="PT-002", name="Mary Williams", sync_date=1,
            medications=[
                SyncMedication("22222-001-60", "Amlodipine 5mg", 30, 30,
                               current_adherence_pdc=0.65, avg_reimbursement=5.50,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.20, payer="UHC"),
                SyncMedication("22222-002-60", "Metoprolol 50mg", 60, 30,
                               current_adherence_pdc=0.70, avg_reimbursement=9.00,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=3.00, payer="UHC"),
            ],
        ),
        SyncPatient(
            patient_id="PT-003", name="James Davis", sync_date=20,
            medications=[
                SyncMedication("33333-001-90", "Omeprazole 20mg", 30, 30,
                               current_adherence_pdc=0.82, avg_reimbursement=7.00,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.90, payer="Aetna"),
                SyncMedication("33333-002-90", "Gabapentin 300mg", 90, 30,
                               current_adherence_pdc=0.60, avg_reimbursement=12.50,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=4.50, payer="Aetna"),
                SyncMedication("33333-003-90", "Sertraline 50mg", 30, 30,
                               current_adherence_pdc=0.73, avg_reimbursement=6.80,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.60, payer="Aetna"),
                SyncMedication("33333-004-90", "Losartan 50mg", 30, 30,
                               current_adherence_pdc=0.77, avg_reimbursement=5.90,
                               avg_dispensing_fee=2.00, avg_acquisition_cost=1.40, payer="Aetna"),
            ],
        ),
    ]

    for pt in patients:
        result = tracker.enroll_patient(pt)
        print(f"Enrolled {pt.name}: {result['medications']} meds, "
              f"alignment fills: {result['alignment_fills_needed']}, "
              f"alignment revenue: ${result['alignment_revenue']:.2f}")

    # Revenue projection
    for pt in patients:
        proj = tracker.project_patient_revenue(pt.patient_id)
        print(f"\n{pt.name} — Annual Value: ${proj.total_annual_value:,.2f} "
              f"(Profit: ${proj.annual_profit:,.2f}, Retention: ${proj.retention_value_annual:,.2f})")

    # Program report
    print(f"\n{tracker.generate_program_report()}")
