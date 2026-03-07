"""
GetPaidRx — Patient Assistance Program (PAP) Finder
Matches patients to manufacturer copay cards, foundation grants,
and state/federal assistance programs to reduce out-of-pocket costs
and improve medication adherence.

Provides:
  - Manufacturer copay card/coupon database
  - Foundation patient assistance program matching
  - Income-based eligibility screening
  - Insurance gap analysis (donut hole / coverage gap)
  - Program enrollment tracking
  - Savings calculation and ROI reporting
  - Patient medication cost optimization recommendations
  - FastAPI routes for PAP dashboard
"""

import json
import uuid
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class ProgramType(str, Enum):
    MANUFACTURER_COPAY = "manufacturer_copay"
    MANUFACTURER_FREE = "manufacturer_free_drug"
    FOUNDATION_GRANT = "foundation_grant"
    STATE_PROGRAM = "state_program"
    FEDERAL_340B = "federal_340b"
    PHARMACY_DISCOUNT = "pharmacy_discount"
    BRIDGE_SUPPLY = "bridge_supply"


class InsuranceType(str, Enum):
    COMMERCIAL = "commercial"
    MEDICARE_PART_D = "medicare_part_d"
    MEDICAID = "medicaid"
    UNINSURED = "uninsured"
    TRICARE = "tricare"
    VA = "va"
    EXCHANGE = "exchange"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    LIKELY_ELIGIBLE = "likely_eligible"
    INELIGIBLE = "ineligible"
    NEEDS_REVIEW = "needs_review"
    ENROLLED = "enrolled"
    EXPIRED = "expired"


class EnrollmentStatus(str, Enum):
    IDENTIFIED = "identified"
    APPLICATION_SENT = "application_sent"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DENIED = "denied"
    ACTIVE = "active"
    EXPIRED = "expired"
    RENEWED = "renewed"


# Federal Poverty Level (2026 estimates)
FPL_2026 = {
    1: 15_600,
    2: 21_150,
    3: 26_700,
    4: 32_250,
    5: 37_800,
    6: 43_350,
    7: 48_900,
    8: 54_450,
}


# ============================================================
# Data Models
# ============================================================

class AssistanceProgram:
    """A patient assistance or copay program."""

    def __init__(
        self,
        program_name: str,
        program_type: ProgramType,
        manufacturer: str,
        drug_names: List[str],
        ndcs: List[str],
        max_annual_benefit: float = 0,
        copay_cap: Optional[float] = None,
        income_limit_fpl_pct: Optional[float] = None,
        insurance_requirements: Optional[List[InsuranceType]] = None,
        exclusions: Optional[List[InsuranceType]] = None,
        application_url: str = "",
        phone: str = "",
        renewal_months: int = 12,
        notes: str = "",
    ):
        self.program_id = str(uuid.uuid4())[:10]
        self.program_name = program_name
        self.program_type = program_type
        self.manufacturer = manufacturer
        self.drug_names = drug_names
        self.ndcs = ndcs
        self.max_annual_benefit = max_annual_benefit
        self.copay_cap = copay_cap  # e.g., patient pays max $10/fill
        self.income_limit_fpl_pct = income_limit_fpl_pct  # e.g., 400 = 400% FPL
        self.insurance_requirements = insurance_requirements  # Required insurance types
        self.exclusions = exclusions or []  # Excluded insurance types
        self.application_url = application_url
        self.phone = phone
        self.renewal_months = renewal_months
        self.notes = notes
        self.active = True
        self.created_at = datetime.utcnow()

    def check_eligibility(
        self,
        insurance_type: InsuranceType,
        household_size: int = 1,
        annual_income: Optional[float] = None,
    ) -> EligibilityStatus:
        """Check basic eligibility for this program."""
        # Insurance exclusion check
        if insurance_type in self.exclusions:
            return EligibilityStatus.INELIGIBLE

        # Insurance requirement check
        if self.insurance_requirements:
            if insurance_type not in self.insurance_requirements:
                return EligibilityStatus.INELIGIBLE

        # Income check
        if self.income_limit_fpl_pct and annual_income is not None:
            fpl = FPL_2026.get(min(household_size, 8), FPL_2026[8])
            income_pct_fpl = (annual_income / fpl) * 100
            if income_pct_fpl > self.income_limit_fpl_pct:
                return EligibilityStatus.INELIGIBLE

        # Manufacturer copay cards: generally available to commercially insured
        if self.program_type == ProgramType.MANUFACTURER_COPAY:
            if insurance_type == InsuranceType.COMMERCIAL:
                return EligibilityStatus.ELIGIBLE
            elif insurance_type in (InsuranceType.MEDICARE_PART_D, InsuranceType.MEDICAID):
                return EligibilityStatus.INELIGIBLE  # Federal healthcare = excluded
            else:
                return EligibilityStatus.NEEDS_REVIEW

        # Free drug programs: usually income-based, accept uninsured
        if self.program_type == ProgramType.MANUFACTURER_FREE:
            if annual_income is not None:
                return EligibilityStatus.ELIGIBLE  # Already passed income check
            return EligibilityStatus.LIKELY_ELIGIBLE

        return EligibilityStatus.LIKELY_ELIGIBLE

    def calculate_savings(
        self, current_copay: float, fills_per_year: int = 12
    ) -> Dict[str, Any]:
        """Estimate annual savings from this program."""
        if self.copay_cap is not None:
            savings_per_fill = max(current_copay - self.copay_cap, 0)
        elif self.program_type == ProgramType.MANUFACTURER_FREE:
            savings_per_fill = current_copay
        else:
            savings_per_fill = current_copay * 0.5  # Conservative estimate

        annual_savings = savings_per_fill * fills_per_year
        if self.max_annual_benefit > 0:
            annual_savings = min(annual_savings, self.max_annual_benefit)

        return {
            "program_name": self.program_name,
            "current_copay": current_copay,
            "estimated_copay_with_program": max(current_copay - savings_per_fill, 0),
            "savings_per_fill": round(savings_per_fill, 2),
            "annual_savings": round(annual_savings, 2),
            "fills_per_year": fills_per_year,
            "max_annual_benefit": self.max_annual_benefit,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "program_name": self.program_name,
            "program_type": self.program_type.value,
            "manufacturer": self.manufacturer,
            "drug_names": self.drug_names,
            "ndcs": self.ndcs,
            "max_annual_benefit": self.max_annual_benefit,
            "copay_cap": self.copay_cap,
            "income_limit_fpl_pct": self.income_limit_fpl_pct,
            "insurance_requirements": [i.value for i in (self.insurance_requirements or [])],
            "exclusions": [e.value for e in self.exclusions],
            "application_url": self.application_url,
            "phone": self.phone,
            "renewal_months": self.renewal_months,
            "notes": self.notes,
            "active": self.active,
        }


class PatientEnrollment:
    """Tracks a patient's enrollment in an assistance program."""

    def __init__(
        self,
        patient_id: str,
        patient_name: str,
        program_id: str,
        program_name: str,
        drug_name: str,
    ):
        self.enrollment_id = str(uuid.uuid4())[:10]
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.program_id = program_id
        self.program_name = program_name
        self.drug_name = drug_name
        self.status = EnrollmentStatus.IDENTIFIED
        self.created_at = datetime.utcnow()
        self.approved_at: Optional[datetime] = None
        self.expires_at: Optional[datetime] = None
        self.total_savings: float = 0
        self.fills_covered: int = 0
        self.notes: str = ""

    def advance_status(self, new_status: EnrollmentStatus, notes: str = ""):
        self.status = new_status
        self.notes = notes
        if new_status == EnrollmentStatus.APPROVED:
            self.approved_at = datetime.utcnow()
        elif new_status == EnrollmentStatus.ACTIVE:
            self.approved_at = self.approved_at or datetime.utcnow()

    def record_fill(self, savings_amount: float):
        self.fills_covered += 1
        self.total_savings += savings_amount

    @property
    def is_active(self) -> bool:
        return self.status in (EnrollmentStatus.APPROVED, EnrollmentStatus.ACTIVE, EnrollmentStatus.RENEWED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enrollment_id": self.enrollment_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "program_id": self.program_id,
            "program_name": self.program_name,
            "drug_name": self.drug_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "total_savings": round(self.total_savings, 2),
            "fills_covered": self.fills_covered,
        }


# ============================================================
# Patient Assistance Finder Engine
# ============================================================

class PatientAssistanceFinder:
    """
    Engine for matching patients to assistance programs,
    tracking enrollments, and calculating savings.
    """

    def __init__(self):
        self.programs: Dict[str, AssistanceProgram] = {}
        self.enrollments: Dict[str, PatientEnrollment] = {}
        # Index: ndc → [program_ids]
        self.ndc_index: Dict[str, List[str]] = defaultdict(list)
        # Index: drug_name (lower) → [program_ids]
        self.drug_index: Dict[str, List[str]] = defaultdict(list)

    # ----------------------------------------------------------
    # Program Management
    # ----------------------------------------------------------

    def add_program(self, **kwargs) -> AssistanceProgram:
        program = AssistanceProgram(**kwargs)
        self.programs[program.program_id] = program
        # Build indexes
        for ndc in program.ndcs:
            self.ndc_index[ndc].append(program.program_id)
        for drug in program.drug_names:
            self.drug_index[drug.lower()].append(program.program_id)
        return program

    def search_programs(
        self,
        ndc: Optional[str] = None,
        drug_name: Optional[str] = None,
        insurance_type: Optional[InsuranceType] = None,
        household_size: int = 1,
        annual_income: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search for matching assistance programs."""
        candidate_ids = set()

        if ndc:
            candidate_ids.update(self.ndc_index.get(ndc, []))
        if drug_name:
            candidate_ids.update(self.drug_index.get(drug_name.lower(), []))
            # Fuzzy: check if drug_name is a substring of any indexed drug
            for indexed_name, pids in self.drug_index.items():
                if drug_name.lower() in indexed_name or indexed_name in drug_name.lower():
                    candidate_ids.update(pids)

        if not candidate_ids:
            return []

        results = []
        for pid in candidate_ids:
            program = self.programs.get(pid)
            if not program or not program.active:
                continue

            eligibility = None
            if insurance_type:
                eligibility = program.check_eligibility(
                    insurance_type, household_size, annual_income
                )
                if eligibility == EligibilityStatus.INELIGIBLE:
                    continue

            result = program.to_dict()
            result["eligibility"] = eligibility.value if eligibility else "unknown"
            results.append(result)

        # Sort: eligible first, then by max benefit
        def sort_key(r):
            elig_order = {"eligible": 0, "likely_eligible": 1, "needs_review": 2, "unknown": 3}
            return (elig_order.get(r.get("eligibility", "unknown"), 4), -r.get("max_annual_benefit", 0))

        results.sort(key=sort_key)
        return results

    # ----------------------------------------------------------
    # Patient Matching
    # ----------------------------------------------------------

    def match_patient(
        self,
        patient_medications: List[Dict[str, Any]],
        insurance_type: InsuranceType,
        household_size: int = 1,
        annual_income: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Match a patient's entire medication list against available programs.
        Returns recommendations sorted by savings potential.
        """
        recommendations = []
        total_potential_savings = 0

        for med in patient_medications:
            ndc = med.get("ndc", "")
            drug_name = med.get("drug_name", "")
            current_copay = float(med.get("current_copay", 0))
            fills_per_year = int(med.get("fills_per_year", 12))

            programs = self.search_programs(
                ndc=ndc,
                drug_name=drug_name,
                insurance_type=insurance_type,
                household_size=household_size,
                annual_income=annual_income,
            )

            if not programs:
                continue

            med_savings = []
            for prog_dict in programs:
                prog = self.programs[prog_dict["program_id"]]
                savings = prog.calculate_savings(current_copay, fills_per_year)
                savings["eligibility"] = prog_dict.get("eligibility", "unknown")
                savings["program_id"] = prog_dict["program_id"]
                savings["program_type"] = prog_dict["program_type"]
                savings["application_url"] = prog_dict.get("application_url", "")
                med_savings.append(savings)

            # Sort by annual savings descending
            med_savings.sort(key=lambda s: s["annual_savings"], reverse=True)
            best_savings = med_savings[0]["annual_savings"] if med_savings else 0
            total_potential_savings += best_savings

            recommendations.append({
                "ndc": ndc,
                "drug_name": drug_name,
                "current_copay": current_copay,
                "fills_per_year": fills_per_year,
                "current_annual_cost": round(current_copay * fills_per_year, 2),
                "best_annual_savings": round(best_savings, 2),
                "programs_available": len(med_savings),
                "top_program": med_savings[0] if med_savings else None,
                "all_programs": med_savings,
            })

        # Sort by savings opportunity
        recommendations.sort(key=lambda r: r["best_annual_savings"], reverse=True)

        return {
            "insurance_type": insurance_type.value,
            "medications_checked": len(patient_medications),
            "medications_with_programs": len(recommendations),
            "total_potential_annual_savings": round(total_potential_savings, 2),
            "recommendations": recommendations,
        }

    # ----------------------------------------------------------
    # Enrollment Management
    # ----------------------------------------------------------

    def create_enrollment(
        self,
        patient_id: str,
        patient_name: str,
        program_id: str,
        drug_name: str,
    ) -> Optional[PatientEnrollment]:
        program = self.programs.get(program_id)
        if not program:
            return None
        enrollment = PatientEnrollment(
            patient_id=patient_id,
            patient_name=patient_name,
            program_id=program_id,
            program_name=program.program_name,
            drug_name=drug_name,
        )
        self.enrollments[enrollment.enrollment_id] = enrollment
        return enrollment

    def update_enrollment_status(self, enrollment_id: str, status: EnrollmentStatus, notes: str = "") -> bool:
        enrollment = self.enrollments.get(enrollment_id)
        if not enrollment:
            return False
        enrollment.advance_status(status, notes)
        return True

    def record_enrollment_fill(self, enrollment_id: str, savings: float) -> bool:
        enrollment = self.enrollments.get(enrollment_id)
        if not enrollment:
            return False
        enrollment.record_fill(savings)
        return True

    def get_patient_enrollments(self, patient_id: str) -> List[Dict[str, Any]]:
        return [
            e.to_dict() for e in self.enrollments.values()
            if e.patient_id == patient_id
        ]

    def get_expiring_enrollments(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get enrollments expiring within the next N days."""
        cutoff = datetime.utcnow() + timedelta(days=days_ahead)
        expiring = []
        for e in self.enrollments.values():
            if e.is_active and e.expires_at and e.expires_at <= cutoff:
                expiring.append({
                    **e.to_dict(),
                    "days_until_expiry": (e.expires_at - datetime.utcnow()).days,
                })
        expiring.sort(key=lambda x: x.get("days_until_expiry", 999))
        return expiring

    # ----------------------------------------------------------
    # Savings Dashboard
    # ----------------------------------------------------------

    def savings_dashboard(self) -> Dict[str, Any]:
        """Aggregate savings metrics across all enrollments."""
        if not self.enrollments:
            return {"message": "No enrollments yet", "total_enrollments": 0}

        active = [e for e in self.enrollments.values() if e.is_active]
        total_savings = sum(e.total_savings for e in self.enrollments.values())
        total_fills = sum(e.fills_covered for e in self.enrollments.values())

        # By program type
        type_savings = defaultdict(lambda: {"enrollments": 0, "savings": 0, "fills": 0})
        for e in self.enrollments.values():
            prog = self.programs.get(e.program_id)
            if prog:
                t = type_savings[prog.program_type.value]
                t["enrollments"] += 1
                t["savings"] += e.total_savings
                t["fills"] += e.fills_covered

        # By status
        status_counts = defaultdict(int)
        for e in self.enrollments.values():
            status_counts[e.status.value] += 1

        return {
            "total_enrollments": len(self.enrollments),
            "active_enrollments": len(active),
            "total_savings": round(total_savings, 2),
            "total_fills_covered": total_fills,
            "avg_savings_per_enrollment": round(total_savings / max(len(self.enrollments), 1), 2),
            "avg_savings_per_fill": round(total_savings / max(total_fills, 1), 2),
            "status_distribution": dict(status_counts),
            "savings_by_program_type": {k: dict(v) for k, v in type_savings.items()},
            "programs_in_database": len(self.programs),
            "active_programs": sum(1 for p in self.programs.values() if p.active),
        }

    # ----------------------------------------------------------
    # Coverage Gap (Donut Hole) Analyzer
    # ----------------------------------------------------------

    def analyze_coverage_gap(
        self,
        patient_id: str,
        total_drug_costs_ytd: float,
        patient_oop_ytd: float,
        insurance_type: InsuranceType = InsuranceType.MEDICARE_PART_D,
    ) -> Dict[str, Any]:
        """
        Analyze Medicare Part D coverage gap (donut hole) status
        and recommend programs to bridge the gap.
        2026 Coverage Gap thresholds (estimated):
        - Initial coverage limit: $5,030
        - Catastrophic threshold: $8,000 (true OOP)
        """
        INITIAL_COVERAGE_LIMIT = 5030.0
        CATASTROPHIC_THRESHOLD = 8000.0

        phase = "initial_coverage"
        if total_drug_costs_ytd >= INITIAL_COVERAGE_LIMIT and patient_oop_ytd < CATASTROPHIC_THRESHOLD:
            phase = "coverage_gap"
        elif patient_oop_ytd >= CATASTROPHIC_THRESHOLD:
            phase = "catastrophic"

        remaining_to_gap = max(INITIAL_COVERAGE_LIMIT - total_drug_costs_ytd, 0)
        remaining_to_catastrophic = max(CATASTROPHIC_THRESHOLD - patient_oop_ytd, 0)

        # In coverage gap, find patient's enrollments and available programs
        available_programs = []
        if phase == "coverage_gap":
            for e in self.enrollments.values():
                if e.patient_id == patient_id and e.is_active:
                    available_programs.append(e.to_dict())

        return {
            "patient_id": patient_id,
            "insurance_type": insurance_type.value,
            "total_drug_costs_ytd": round(total_drug_costs_ytd, 2),
            "patient_oop_ytd": round(patient_oop_ytd, 2),
            "current_phase": phase,
            "initial_coverage_limit": INITIAL_COVERAGE_LIMIT,
            "catastrophic_threshold": CATASTROPHIC_THRESHOLD,
            "remaining_to_coverage_gap": round(remaining_to_gap, 2),
            "remaining_to_catastrophic": round(remaining_to_catastrophic, 2),
            "active_assistance_programs": available_programs,
            "recommendation": self._gap_recommendation(phase, remaining_to_gap, remaining_to_catastrophic),
        }

    def _gap_recommendation(self, phase: str, to_gap: float, to_catastrophic: float) -> str:
        if phase == "initial_coverage":
            if to_gap < 500:
                return f"Approaching coverage gap in ~${to_gap:.0f}. Review manufacturer copay programs and foundation grants NOW to prepare."
            return "In initial coverage phase. Monitor drug spend and pre-enroll in assistance programs."
        elif phase == "coverage_gap":
            return (
                f"Patient is IN the coverage gap. ${to_catastrophic:.0f} remaining to catastrophic coverage. "
                "Activate manufacturer discount programs and foundation grants immediately to reduce OOP burden."
            )
        else:
            return "Patient has reached catastrophic coverage. Most costs are now covered by Medicare."


# ============================================================
# FastAPI Route Registration
# ============================================================

def register_pap_routes(app, finder: Optional[PatientAssistanceFinder] = None):
    """Register patient assistance program routes."""
    from fastapi import Body

    if finder is None:
        finder = PatientAssistanceFinder()

    @app.post("/api/v1/pap/programs")
    async def add_program(payload: Dict[str, Any] = Body(...)):
        program = finder.add_program(
            program_name=payload["program_name"],
            program_type=ProgramType(payload["program_type"]),
            manufacturer=payload["manufacturer"],
            drug_names=payload["drug_names"],
            ndcs=payload.get("ndcs", []),
            max_annual_benefit=payload.get("max_annual_benefit", 0),
            copay_cap=payload.get("copay_cap"),
            income_limit_fpl_pct=payload.get("income_limit_fpl_pct"),
            insurance_requirements=[InsuranceType(i) for i in payload.get("insurance_requirements", [])],
            exclusions=[InsuranceType(e) for e in payload.get("exclusions", [])],
            application_url=payload.get("application_url", ""),
            phone=payload.get("phone", ""),
        )
        return program.to_dict()

    @app.get("/api/v1/pap/search")
    async def search_programs(
        ndc: Optional[str] = None,
        drug_name: Optional[str] = None,
        insurance: Optional[str] = None,
        income: Optional[float] = None,
        household: int = 1,
    ):
        ins_type = InsuranceType(insurance) if insurance else None
        return finder.search_programs(ndc, drug_name, ins_type, household, income)

    @app.post("/api/v1/pap/match-patient")
    async def match_patient(payload: Dict[str, Any] = Body(...)):
        return finder.match_patient(
            patient_medications=payload["medications"],
            insurance_type=InsuranceType(payload["insurance_type"]),
            household_size=payload.get("household_size", 1),
            annual_income=payload.get("annual_income"),
        )

    @app.post("/api/v1/pap/enrollments")
    async def create_enrollment(payload: Dict[str, Any] = Body(...)):
        enrollment = finder.create_enrollment(
            patient_id=payload["patient_id"],
            patient_name=payload["patient_name"],
            program_id=payload["program_id"],
            drug_name=payload["drug_name"],
        )
        return enrollment.to_dict() if enrollment else {"error": "Program not found"}

    @app.get("/api/v1/pap/enrollments/{patient_id}")
    async def get_enrollments(patient_id: str):
        return finder.get_patient_enrollments(patient_id)

    @app.get("/api/v1/pap/expiring")
    async def get_expiring(days: int = 30):
        return finder.get_expiring_enrollments(days)

    @app.get("/api/v1/pap/savings-dashboard")
    async def savings_dashboard():
        return finder.savings_dashboard()

    @app.post("/api/v1/pap/coverage-gap")
    async def analyze_gap(payload: Dict[str, Any] = Body(...)):
        return finder.analyze_coverage_gap(
            patient_id=payload["patient_id"],
            total_drug_costs_ytd=payload["total_drug_costs_ytd"],
            patient_oop_ytd=payload["patient_oop_ytd"],
        )

    return finder
