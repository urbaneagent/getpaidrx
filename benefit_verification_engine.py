"""
GetPaidRx — Pharmacy Benefit Verification Engine
Real-time patient benefit verification including formulary status,
copay estimation, coverage limits, and accumulator tracking.

Features:
  - Real-time eligibility verification (E1/271 transaction)
  - Formulary tier lookup with alternative suggestions
  - Copay/coinsurance estimation with accumulator tracking
  - Deductible tracking (individual + family)
  - Out-of-pocket maximum monitoring
  - Coverage gap (donut hole) detection for Medicare Part D
  - Copay accumulator/maximizer program detection
  - Patient cost comparison across fill quantities
"""

import json
import uuid
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class CoverageType(str, Enum):
    COMMERCIAL = "commercial"
    MEDICARE_PART_D = "medicare_part_d"
    MEDICAID = "medicaid"
    TRICARE = "tricare"
    WORKERS_COMP = "workers_comp"
    CASH = "cash"


class FormularyTier(str, Enum):
    TIER_1 = "tier_1"     # Preferred generic
    TIER_2 = "tier_2"     # Non-preferred generic
    TIER_3 = "tier_3"     # Preferred brand
    TIER_4 = "tier_4"     # Non-preferred brand
    TIER_5 = "tier_5"     # Specialty
    NOT_COVERED = "not_covered"


class EligibilityStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    TERMINATED = "terminated"
    COBRA = "cobra"


class CoveragePhase(str, Enum):
    DEDUCTIBLE = "deductible"
    INITIAL_COVERAGE = "initial_coverage"
    COVERAGE_GAP = "coverage_gap"         # Medicare donut hole
    CATASTROPHIC = "catastrophic"


class AccumulatorType(str, Enum):
    STANDARD = "standard"
    ACCUMULATOR = "accumulator"           # Copay card $ don't count
    MAXIMIZER = "maximizer"               # Copay card spreads across year


# 2026 Medicare Part D thresholds
MEDICARE_2026 = {
    "deductible": 590,
    "initial_coverage_limit": 5030,
    "oop_max": 2000,          # $2,000 OOP cap (IRA provision)
    "catastrophic_threshold": 8000,
    "brand_gap_discount": 0.70,  # Manufacturer 70% discount in gap
    "generic_gap_coinsurance": 0.25,  # 25% patient share in gap
}

# Tier copay defaults (commercial)
DEFAULT_COPAYS = {
    FormularyTier.TIER_1: 10.0,
    FormularyTier.TIER_2: 25.0,
    FormularyTier.TIER_3: 50.0,
    FormularyTier.TIER_4: 80.0,
    FormularyTier.TIER_5: 150.0,
    FormularyTier.NOT_COVERED: None,
}


# ============================================================
# Data Classes
# ============================================================

@dataclass
class PatientBenefit:
    """Patient's pharmacy benefit details."""
    patient_id: str
    member_id: str
    group_number: str
    bin_number: str
    pcn: str
    plan_name: str
    coverage_type: CoverageType
    eligibility: EligibilityStatus
    effective_date: str
    termination_date: Optional[str]
    copay_schedule: Dict[str, float]   # tier -> copay
    coinsurance_schedule: Dict[str, float]  # tier -> coinsurance %
    deductible_individual: float
    deductible_family: float
    oop_max_individual: float
    oop_max_family: float
    deductible_met_individual: float
    deductible_met_family: float
    oop_met_individual: float
    oop_met_family: float
    accumulator_type: AccumulatorType
    coverage_phase: CoveragePhase
    plan_year_start: str


@dataclass
class FormularyEntry:
    """A drug's formulary entry."""
    ndc: str
    drug_name: str
    generic_name: str
    tier: FormularyTier
    pa_required: bool
    step_therapy_required: bool
    quantity_limit: Optional[float]
    specialty_pharmacy_required: bool
    preferred_alternatives: List[str]
    clinical_notes: str


@dataclass
class CostEstimate:
    """Estimated patient cost for a prescription."""
    estimate_id: str
    patient_id: str
    drug_name: str
    ndc: str
    tier: FormularyTier
    quantity: float
    days_supply: int
    ingredient_cost: float
    plan_pays: float
    patient_copay: float
    patient_coinsurance: float
    patient_deductible_applied: float
    patient_total: float
    remaining_deductible: float
    remaining_oop: float
    coverage_phase: CoveragePhase
    copay_card_eligible: bool
    copay_card_savings: float
    alternatives: List[Dict[str, Any]]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug_name": self.drug_name,
            "tier": self.tier.value,
            "quantity": self.quantity,
            "days_supply": self.days_supply,
            "patient_total": self.patient_total,
            "plan_pays": self.plan_pays,
            "coverage_phase": self.coverage_phase.value,
            "copay_card_eligible": self.copay_card_eligible,
            "warnings": self.warnings,
        }


@dataclass
class FillComparison:
    """Comparison of costs across different fill quantities."""
    drug_name: str
    options: List[Dict[str, Any]]
    recommended_option: str
    savings_vs_30day: float


# ============================================================
# Benefit Verification Engine
# ============================================================

class BenefitVerificationEngine:
    """
    Verifies pharmacy benefits, estimates patient costs, tracks
    accumulators, and identifies cost-saving opportunities.
    """

    def __init__(self):
        self.patients: Dict[str, PatientBenefit] = {}
        self.formulary: Dict[str, FormularyEntry] = {}  # NDC -> entry
        self.estimates: List[CostEstimate] = []
        self.claim_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def enroll_patient(
        self,
        patient_id: str,
        member_id: str,
        group_number: str,
        bin_number: str,
        pcn: str,
        plan_name: str,
        coverage_type: CoverageType,
        deductible: float = 500.0,
        deductible_family: float = 1500.0,
        oop_max: float = 5000.0,
        oop_max_family: float = 10000.0,
        copays: Optional[Dict[str, float]] = None,
        accumulator_type: AccumulatorType = AccumulatorType.STANDARD,
    ) -> PatientBenefit:
        """Enroll a patient with their benefit details."""
        now = datetime.utcnow()
        plan_year = datetime(now.year, 1, 1).isoformat() + "Z"

        benefit = PatientBenefit(
            patient_id=patient_id,
            member_id=member_id,
            group_number=group_number,
            bin_number=bin_number,
            pcn=pcn,
            plan_name=plan_name,
            coverage_type=coverage_type,
            eligibility=EligibilityStatus.ACTIVE,
            effective_date=plan_year,
            termination_date=None,
            copay_schedule=copays or {t.value: c for t, c in DEFAULT_COPAYS.items() if c is not None},
            coinsurance_schedule={},
            deductible_individual=deductible,
            deductible_family=deductible_family,
            oop_max_individual=oop_max,
            oop_max_family=oop_max_family,
            deductible_met_individual=0.0,
            deductible_met_family=0.0,
            oop_met_individual=0.0,
            oop_met_family=0.0,
            accumulator_type=accumulator_type,
            coverage_phase=CoveragePhase.DEDUCTIBLE,
            plan_year_start=plan_year,
        )
        self.patients[patient_id] = benefit
        return benefit

    def add_formulary_entry(
        self,
        ndc: str,
        drug_name: str,
        generic_name: str,
        tier: FormularyTier,
        pa_required: bool = False,
        step_therapy: bool = False,
        quantity_limit: Optional[float] = None,
        specialty_required: bool = False,
        alternatives: Optional[List[str]] = None,
        notes: str = "",
    ) -> FormularyEntry:
        """Add a drug to the formulary."""
        entry = FormularyEntry(
            ndc=ndc,
            drug_name=drug_name,
            generic_name=generic_name,
            tier=tier,
            pa_required=pa_required,
            step_therapy_required=step_therapy,
            quantity_limit=quantity_limit,
            specialty_pharmacy_required=specialty_required,
            preferred_alternatives=alternatives or [],
            clinical_notes=notes,
        )
        self.formulary[ndc] = entry
        return entry

    def verify_eligibility(self, patient_id: str) -> Dict[str, Any]:
        """Verify patient eligibility and current benefit status."""
        patient = self.patients.get(patient_id)
        if not patient:
            return {"eligible": False, "reason": "Patient not found"}

        now = datetime.utcnow()

        # Check termination
        if patient.termination_date:
            term = datetime.fromisoformat(patient.termination_date.replace("Z", ""))
            if now > term:
                return {
                    "eligible": False,
                    "reason": "Coverage terminated",
                    "termination_date": patient.termination_date,
                }

        # Check status
        if patient.eligibility != EligibilityStatus.ACTIVE:
            return {
                "eligible": False,
                "reason": f"Status: {patient.eligibility.value}",
            }

        return {
            "eligible": True,
            "member_id": patient.member_id,
            "plan_name": patient.plan_name,
            "coverage_type": patient.coverage_type.value,
            "deductible_remaining": round(
                patient.deductible_individual - patient.deductible_met_individual, 2
            ),
            "oop_remaining": round(
                patient.oop_max_individual - patient.oop_met_individual, 2
            ),
            "coverage_phase": patient.coverage_phase.value,
            "accumulator_type": patient.accumulator_type.value,
        }

    def _determine_coverage_phase(self, patient: PatientBenefit) -> CoveragePhase:
        """Determine which coverage phase the patient is in."""
        if patient.coverage_type == CoverageType.MEDICARE_PART_D:
            if patient.deductible_met_individual < MEDICARE_2026["deductible"]:
                return CoveragePhase.DEDUCTIBLE
            elif patient.oop_met_individual < MEDICARE_2026["initial_coverage_limit"]:
                return CoveragePhase.INITIAL_COVERAGE
            elif patient.oop_met_individual < MEDICARE_2026["catastrophic_threshold"]:
                return CoveragePhase.COVERAGE_GAP
            else:
                return CoveragePhase.CATASTROPHIC
        else:
            if patient.deductible_met_individual < patient.deductible_individual:
                return CoveragePhase.DEDUCTIBLE
            elif patient.oop_met_individual >= patient.oop_max_individual:
                return CoveragePhase.CATASTROPHIC  # OOP max reached
            else:
                return CoveragePhase.INITIAL_COVERAGE

    def estimate_cost(
        self,
        patient_id: str,
        ndc: str,
        quantity: float,
        days_supply: int,
        ingredient_cost: Optional[float] = None,
    ) -> CostEstimate:
        """Estimate patient cost for a prescription."""
        patient = self.patients.get(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        formulary_entry = self.formulary.get(ndc)
        if not formulary_entry:
            raise ValueError(f"Drug {ndc} not in formulary")

        tier = formulary_entry.tier
        drug_cost = ingredient_cost or (quantity * 5.0)  # Default if not provided
        warnings = []

        # Update coverage phase
        patient.coverage_phase = self._determine_coverage_phase(patient)
        phase = patient.coverage_phase

        # Calculate patient responsibility
        deductible_applied = 0.0
        copay = 0.0
        coinsurance = 0.0

        if tier == FormularyTier.NOT_COVERED:
            patient_total = drug_cost
            plan_pays = 0.0
            warnings.append("Drug not covered — patient pays full price")
        elif phase == CoveragePhase.DEDUCTIBLE:
            remaining_ded = patient.deductible_individual - patient.deductible_met_individual
            deductible_applied = min(drug_cost, remaining_ded)
            patient_total = deductible_applied
            plan_pays = drug_cost - patient_total
            if deductible_applied >= remaining_ded:
                warnings.append("This fill will satisfy the remaining deductible")
        elif phase == CoveragePhase.CATASTROPHIC:
            if patient.coverage_type == CoverageType.MEDICARE_PART_D:
                patient_total = max(drug_cost * 0.05, 4.50)  # 5% or small copay
            else:
                patient_total = 0.0  # OOP max reached
            plan_pays = drug_cost - patient_total
            warnings.append("Patient has reached catastrophic/OOP maximum phase")
        elif phase == CoveragePhase.COVERAGE_GAP:
            # Medicare donut hole
            if formulary_entry.generic_name != formulary_entry.drug_name:
                # Brand drug — manufacturer 70% discount
                patient_total = drug_cost * (1 - MEDICARE_2026["brand_gap_discount"])
            else:
                patient_total = drug_cost * MEDICARE_2026["generic_gap_coinsurance"]
            plan_pays = drug_cost - patient_total
            warnings.append("Patient is in Medicare Part D coverage gap (donut hole)")
        else:
            # Initial coverage — apply copay
            tier_copay = patient.copay_schedule.get(tier.value, 50.0)
            copay = min(tier_copay, drug_cost)
            patient_total = copay
            plan_pays = drug_cost - copay

        # Copay card eligibility
        copay_card_eligible = (
            tier in (FormularyTier.TIER_3, FormularyTier.TIER_4, FormularyTier.TIER_5)
            and patient.coverage_type == CoverageType.COMMERCIAL
        )
        copay_card_savings = 0.0
        if copay_card_eligible and patient_total > 30:
            copay_card_savings = min(patient_total - 30, 200)  # Typical copay card
            if patient.accumulator_type == AccumulatorType.ACCUMULATOR:
                warnings.append(
                    "⚠️ Copay accumulator program detected — copay card savings "
                    "will NOT count toward deductible/OOP maximum"
                )

        # Check quantity limits
        if formulary_entry.quantity_limit and quantity > formulary_entry.quantity_limit:
            warnings.append(
                f"Quantity {quantity} exceeds limit of {formulary_entry.quantity_limit}"
            )

        # PA/step therapy warnings
        if formulary_entry.pa_required:
            warnings.append("Prior authorization required")
        if formulary_entry.step_therapy_required:
            warnings.append("Step therapy required — patient must try preferred alternatives first")

        # Build alternatives
        alternatives = []
        if tier.value >= FormularyTier.TIER_3.value and formulary_entry.preferred_alternatives:
            for alt_name in formulary_entry.preferred_alternatives[:3]:
                alt_entry = None
                for fe in self.formulary.values():
                    if fe.drug_name.lower() == alt_name.lower():
                        alt_entry = fe
                        break
                if alt_entry:
                    alt_copay = patient.copay_schedule.get(alt_entry.tier.value, 50)
                    alternatives.append({
                        "drug_name": alt_entry.drug_name,
                        "tier": alt_entry.tier.value,
                        "estimated_copay": alt_copay,
                        "savings": round(patient_total - alt_copay, 2),
                    })

        remaining_ded = round(
            max(0, patient.deductible_individual - patient.deductible_met_individual - deductible_applied), 2
        )
        remaining_oop = round(
            max(0, patient.oop_max_individual - patient.oop_met_individual - patient_total), 2
        )

        estimate = CostEstimate(
            estimate_id=str(uuid.uuid4()),
            patient_id=patient_id,
            drug_name=formulary_entry.drug_name,
            ndc=ndc,
            tier=tier,
            quantity=quantity,
            days_supply=days_supply,
            ingredient_cost=round(drug_cost, 2),
            plan_pays=round(plan_pays, 2),
            patient_copay=round(copay, 2),
            patient_coinsurance=round(coinsurance, 2),
            patient_deductible_applied=round(deductible_applied, 2),
            patient_total=round(patient_total, 2),
            remaining_deductible=remaining_ded,
            remaining_oop=remaining_oop,
            coverage_phase=phase,
            copay_card_eligible=copay_card_eligible,
            copay_card_savings=round(copay_card_savings, 2),
            alternatives=alternatives,
            warnings=warnings,
        )

        self.estimates.append(estimate)
        return estimate

    def compare_fill_options(
        self,
        patient_id: str,
        ndc: str,
        ingredient_cost_per_unit: float,
    ) -> FillComparison:
        """Compare costs for 30, 60, and 90 day supplies."""
        options = []
        fills = [
            (30, 30),
            (60, 60),
            (90, 90),
        ]

        for qty, days in fills:
            cost = ingredient_cost_per_unit * qty
            try:
                estimate = self.estimate_cost(patient_id, ndc, qty, days, cost)
                per_day = estimate.patient_total / days if days > 0 else 0
                options.append({
                    "days_supply": days,
                    "quantity": qty,
                    "patient_cost": estimate.patient_total,
                    "cost_per_day": round(per_day, 2),
                    "copay_card_savings": estimate.copay_card_savings,
                })
            except Exception:
                pass

        # Find best option
        if options:
            best = min(options, key=lambda x: x["cost_per_day"])
            recommended = f"{best['days_supply']}-day supply"
            savings = options[0]["patient_cost"] * 3 - best["patient_cost"] if len(options) >= 3 else 0
        else:
            recommended = "30-day supply"
            savings = 0

        drug = self.formulary.get(ndc)
        drug_name = drug.drug_name if drug else ndc

        return FillComparison(
            drug_name=drug_name,
            options=options,
            recommended_option=recommended,
            savings_vs_30day=round(max(0, savings), 2),
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get benefit verification engine statistics."""
        by_tier = defaultdict(int)
        by_phase = defaultdict(int)
        total_patient_cost = 0
        total_plan_cost = 0

        for est in self.estimates:
            by_tier[est.tier.value] += 1
            by_phase[est.coverage_phase.value] += 1
            total_patient_cost += est.patient_total
            total_plan_cost += est.plan_pays

        return {
            "enrolled_patients": len(self.patients),
            "formulary_entries": len(self.formulary),
            "estimates_generated": len(self.estimates),
            "estimates_by_tier": dict(by_tier),
            "estimates_by_phase": dict(by_phase),
            "total_patient_cost": round(total_patient_cost, 2),
            "total_plan_cost": round(total_plan_cost, 2),
            "avg_patient_cost": round(total_patient_cost / len(self.estimates), 2) if self.estimates else 0,
        }


if __name__ == "__main__":
    engine = BenefitVerificationEngine()

    # Enroll patient
    patient = engine.enroll_patient(
        patient_id="PAT001",
        member_id="MEM123456",
        group_number="GRP789",
        bin_number="610014",
        pcn="MCAIDKY",
        plan_name="BCBS PPO Gold",
        coverage_type=CoverageType.COMMERCIAL,
        deductible=500.0,
        oop_max=5000.0,
    )

    # Add formulary entries
    engine.add_formulary_entry(
        ndc="0093-0058-01", drug_name="Atorvastatin 40mg",
        generic_name="Atorvastatin", tier=FormularyTier.TIER_1,
    )
    engine.add_formulary_entry(
        ndc="0069-3150-83", drug_name="Lipitor 40mg",
        generic_name="Atorvastatin", tier=FormularyTier.TIER_3,
        pa_required=True,
        alternatives=["Atorvastatin 40mg"],
    )
    engine.add_formulary_entry(
        ndc="0169-4772-12", drug_name="Ozempic 1mg",
        generic_name="Semaglutide", tier=FormularyTier.TIER_5,
        pa_required=True, step_therapy=True,
        quantity_limit=4,
    )

    # Verify eligibility
    elig = engine.verify_eligibility("PAT001")
    print(f"Eligibility: {json.dumps(elig, indent=2)}")

    # Estimate cost
    est = engine.estimate_cost("PAT001", "0093-0058-01", 90, 90, 8.50)
    print(f"\nCost Estimate for {est.drug_name}:")
    print(f"  Patient pays: ${est.patient_total:.2f}")
    print(f"  Plan pays: ${est.plan_pays:.2f}")
    print(f"  Phase: {est.coverage_phase.value}")
    print(f"  Warnings: {est.warnings}")

    # Compare fill options
    comp = engine.compare_fill_options("PAT001", "0093-0058-01", 0.10)
    print(f"\nFill comparison for {comp.drug_name}:")
    for opt in comp.options:
        print(f"  {opt['days_supply']}d: ${opt['patient_cost']:.2f} (${opt['cost_per_day']}/day)")
    print(f"  Recommended: {comp.recommended_option}")

    # Stats
    stats = engine.get_statistics()
    print(f"\nEngine stats: {json.dumps(stats, indent=2)}")
