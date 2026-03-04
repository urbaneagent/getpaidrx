"""
GetPaidRx — Prior Authorization Automation Engine
Automates the prior authorization (PA) process for pharmacy claims
including criteria matching, appeal generation, and turnaround tracking.

Features:
  - PA criteria matching engine (drug-payer matrix)
  - Auto-determination for common PA scenarios
  - Step therapy validation (fail-first protocol tracking)
  - Quantity limit exception processing
  - Appeal letter generation with clinical justification
  - PA turnaround time tracking and SLA monitoring
  - Payer-specific PA form auto-population
  - PA expiration monitoring and renewal alerts
"""

import json
import uuid
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class PAStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    APPEALING = "appealing"
    APPEAL_APPROVED = "appeal_approved"
    APPEAL_DENIED = "appeal_denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PAType(str, Enum):
    STANDARD = "standard"           # Normal review (72h)
    URGENT = "urgent"               # Expedited review (24h)
    RETROSPECTIVE = "retrospective" # After dispensing
    QUANTITY_LIMIT = "quantity_limit"
    STEP_THERAPY = "step_therapy"
    FORMULARY_EXCEPTION = "formulary_exception"
    TIER_EXCEPTION = "tier_exception"


class DenialReason(str, Enum):
    NOT_MEDICALLY_NECESSARY = "not_medically_necessary"
    STEP_THERAPY_NOT_MET = "step_therapy_not_met"
    QUANTITY_EXCEEDS_LIMIT = "quantity_exceeds_limit"
    NOT_ON_FORMULARY = "not_on_formulary"
    DOCUMENTATION_INCOMPLETE = "documentation_incomplete"
    ALTERNATIVE_AVAILABLE = "alternative_available"
    AGE_RESTRICTION = "age_restriction"
    DIAGNOSIS_NOT_COVERED = "diagnosis_not_covered"
    DUPLICATE_THERAPY = "duplicate_therapy"
    EXPERIMENTAL = "experimental"


class AppealLevel(str, Enum):
    FIRST_LEVEL = "first_level"
    SECOND_LEVEL = "second_level"
    EXTERNAL_REVIEW = "external_review"
    STATE_FAIR_HEARING = "state_fair_hearing"


class CriteriaResult(str, Enum):
    MET = "met"
    NOT_MET = "not_met"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


# SLA targets for PA turnaround (in hours)
PA_SLA_HOURS = {
    PAType.STANDARD: 72,
    PAType.URGENT: 24,
    PAType.RETROSPECTIVE: 168,  # 7 days
    PAType.QUANTITY_LIMIT: 72,
    PAType.STEP_THERAPY: 72,
    PAType.FORMULARY_EXCEPTION: 72,
    PAType.TIER_EXCEPTION: 72,
}


# ============================================================
# Data Classes
# ============================================================

@dataclass
class PACriteria:
    """Prior authorization criteria for a drug-payer combination."""
    criteria_id: str
    drug_name: str
    ndc_prefix: str
    payer_id: str
    payer_name: str
    pa_required: bool
    pa_type: PAType
    approved_diagnoses: List[str]   # ICD-10 codes
    step_therapy_drugs: List[str]   # Drugs patient must try first
    step_therapy_min_days: int      # Min days on each step drug
    quantity_limit_per_30: Optional[float]  # Max quantity per 30 days
    age_min: Optional[int]
    age_max: Optional[int]
    requires_specialist: bool
    specialist_types: List[str]
    clinical_notes_required: bool
    lab_results_required: List[str]
    renewal_interval_days: int      # How often PA needs renewal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria_id": self.criteria_id,
            "drug_name": self.drug_name,
            "payer_name": self.payer_name,
            "pa_required": self.pa_required,
            "pa_type": self.pa_type.value,
            "step_therapy_drugs": self.step_therapy_drugs,
            "quantity_limit_per_30": self.quantity_limit_per_30,
        }


@dataclass
class PatientHistory:
    """Patient medication and diagnosis history for PA evaluation."""
    patient_id: str
    date_of_birth: str
    diagnoses: List[str]       # Active ICD-10 codes
    medication_history: List[Dict[str, Any]]  # Previous/current meds
    lab_results: Dict[str, Any]
    specialist_visits: List[Dict[str, str]]
    allergies: List[str]
    contraindications: List[str]

    @property
    def age(self) -> int:
        dob = datetime.fromisoformat(self.date_of_birth)
        return (datetime.utcnow() - dob).days // 365


@dataclass
class PARequest:
    """A prior authorization request."""
    pa_id: str
    patient_id: str
    prescriber_npi: str
    prescriber_name: str
    drug_name: str
    ndc: str
    payer_id: str
    payer_name: str
    diagnosis_codes: List[str]
    quantity_requested: float
    days_supply: int
    pa_type: PAType
    status: PAStatus
    submitted_at: str
    decided_at: Optional[str]
    expires_at: Optional[str]
    denial_reason: Optional[DenialReason]
    appeal_level: Optional[AppealLevel]
    criteria_evaluation: Dict[str, CriteriaResult]
    notes: List[str]
    turnaround_hours: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pa_id": self.pa_id,
            "patient_id": self.patient_id,
            "drug_name": self.drug_name,
            "payer_name": self.payer_name,
            "status": self.status.value,
            "pa_type": self.pa_type.value,
            "submitted_at": self.submitted_at,
            "decided_at": self.decided_at,
            "denial_reason": self.denial_reason.value if self.denial_reason else None,
            "turnaround_hours": self.turnaround_hours,
        }


@dataclass
class AppealLetter:
    """Generated appeal letter for a denied PA."""
    letter_id: str
    pa_id: str
    appeal_level: AppealLevel
    patient_id: str
    drug_name: str
    payer_name: str
    denial_reason: DenialReason
    clinical_justification: str
    supporting_evidence: List[str]
    generated_at: str
    letter_body: str


# ============================================================
# Prior Auth Engine
# ============================================================

class PriorAuthEngine:
    """
    Automates prior authorization processing including criteria
    matching, auto-determination, and appeal generation.
    """

    def __init__(self):
        self.criteria_db: Dict[str, List[PACriteria]] = defaultdict(list)  # drug_name -> criteria
        self.pa_requests: Dict[str, PARequest] = {}
        self.appeal_letters: List[AppealLetter] = []
        self.payer_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def add_criteria(
        self,
        drug_name: str,
        ndc_prefix: str,
        payer_id: str,
        payer_name: str,
        pa_type: PAType = PAType.STANDARD,
        approved_diagnoses: Optional[List[str]] = None,
        step_therapy_drugs: Optional[List[str]] = None,
        step_therapy_min_days: int = 30,
        quantity_limit_per_30: Optional[float] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        requires_specialist: bool = False,
        specialist_types: Optional[List[str]] = None,
        clinical_notes_required: bool = True,
        lab_results_required: Optional[List[str]] = None,
        renewal_interval_days: int = 365,
    ) -> PACriteria:
        """Add PA criteria for a drug-payer combination."""
        criteria = PACriteria(
            criteria_id=str(uuid.uuid4()),
            drug_name=drug_name,
            ndc_prefix=ndc_prefix,
            payer_id=payer_id,
            payer_name=payer_name,
            pa_required=True,
            pa_type=pa_type,
            approved_diagnoses=approved_diagnoses or [],
            step_therapy_drugs=step_therapy_drugs or [],
            step_therapy_min_days=step_therapy_min_days,
            quantity_limit_per_30=quantity_limit_per_30,
            age_min=age_min,
            age_max=age_max,
            requires_specialist=requires_specialist,
            specialist_types=specialist_types or [],
            clinical_notes_required=clinical_notes_required,
            lab_results_required=lab_results_required or [],
            renewal_interval_days=renewal_interval_days,
        )
        self.criteria_db[drug_name.lower()].append(criteria)
        return criteria

    def evaluate_criteria(
        self,
        drug_name: str,
        payer_id: str,
        patient: PatientHistory,
        quantity: float,
        days_supply: int,
    ) -> Tuple[Dict[str, CriteriaResult], bool, List[str]]:
        """
        Evaluate PA criteria for a prescription.
        Returns: (criteria_results, auto_approvable, notes)
        """
        criteria_list = self.criteria_db.get(drug_name.lower(), [])
        matching = [c for c in criteria_list if c.payer_id == payer_id]

        if not matching:
            return {}, True, ["No PA criteria found — auto-approve"]

        criteria = matching[0]
        results = {}
        notes = []
        all_met = True

        # Diagnosis check
        if criteria.approved_diagnoses:
            patient_dx = set(patient.diagnoses)
            approved_dx = set(criteria.approved_diagnoses)
            if patient_dx & approved_dx:
                results["diagnosis"] = CriteriaResult.MET
                matched = patient_dx & approved_dx
                notes.append(f"Diagnosis match: {', '.join(matched)}")
            else:
                results["diagnosis"] = CriteriaResult.NOT_MET
                notes.append(f"No matching diagnosis. Approved: {', '.join(criteria.approved_diagnoses)}")
                all_met = False
        else:
            results["diagnosis"] = CriteriaResult.MET

        # Step therapy check
        if criteria.step_therapy_drugs:
            tried_drugs = {
                m["drug_name"].lower() for m in patient.medication_history
                if m.get("days_used", 0) >= criteria.step_therapy_min_days
            }
            required = {d.lower() for d in criteria.step_therapy_drugs}
            if required.issubset(tried_drugs):
                results["step_therapy"] = CriteriaResult.MET
                notes.append("Step therapy requirements met")
            elif tried_drugs & required:
                results["step_therapy"] = CriteriaResult.PARTIAL
                missing = required - tried_drugs
                notes.append(f"Partial step therapy. Missing: {', '.join(missing)}")
                all_met = False
            else:
                results["step_therapy"] = CriteriaResult.NOT_MET
                notes.append(f"Step therapy not started. Required: {', '.join(criteria.step_therapy_drugs)}")
                all_met = False

        # Quantity limit check
        if criteria.quantity_limit_per_30 is not None:
            per_30 = (quantity / days_supply) * 30
            if per_30 <= criteria.quantity_limit_per_30:
                results["quantity_limit"] = CriteriaResult.MET
            else:
                results["quantity_limit"] = CriteriaResult.NOT_MET
                notes.append(
                    f"Quantity {per_30:.0f}/30d exceeds limit of {criteria.quantity_limit_per_30}/30d"
                )
                all_met = False

        # Age check
        if criteria.age_min is not None or criteria.age_max is not None:
            age = patient.age
            if criteria.age_min and age < criteria.age_min:
                results["age"] = CriteriaResult.NOT_MET
                notes.append(f"Patient age {age} below minimum {criteria.age_min}")
                all_met = False
            elif criteria.age_max and age > criteria.age_max:
                results["age"] = CriteriaResult.NOT_MET
                notes.append(f"Patient age {age} above maximum {criteria.age_max}")
                all_met = False
            else:
                results["age"] = CriteriaResult.MET

        # Specialist requirement
        if criteria.requires_specialist:
            specialist_types_lower = {s.lower() for s in criteria.specialist_types}
            patient_specialists = {
                v.get("specialty", "").lower() for v in patient.specialist_visits
            }
            if specialist_types_lower & patient_specialists:
                results["specialist"] = CriteriaResult.MET
            else:
                results["specialist"] = CriteriaResult.NOT_MET
                notes.append(f"Specialist visit required: {', '.join(criteria.specialist_types)}")
                all_met = False

        # Lab results
        if criteria.lab_results_required:
            available_labs = set(patient.lab_results.keys())
            required_labs = set(criteria.lab_results_required)
            if required_labs.issubset(available_labs):
                results["lab_results"] = CriteriaResult.MET
            else:
                missing = required_labs - available_labs
                results["lab_results"] = CriteriaResult.NOT_MET
                notes.append(f"Missing lab results: {', '.join(missing)}")
                all_met = False

        return results, all_met, notes

    def submit_pa(
        self,
        patient: PatientHistory,
        prescriber_npi: str,
        prescriber_name: str,
        drug_name: str,
        ndc: str,
        payer_id: str,
        payer_name: str,
        diagnosis_codes: List[str],
        quantity: float,
        days_supply: int,
        pa_type: PAType = PAType.STANDARD,
    ) -> PARequest:
        """Submit a prior authorization request with auto-evaluation."""
        # Evaluate criteria
        criteria_eval, auto_approve, notes = self.evaluate_criteria(
            drug_name, payer_id, patient, quantity, days_supply
        )

        now = datetime.utcnow()
        sla_hours = PA_SLA_HOURS.get(pa_type, 72)

        if auto_approve:
            status = PAStatus.APPROVED
            decided = now.isoformat() + "Z"
            expires = (now + timedelta(days=365)).isoformat() + "Z"
            denial_reason = None
            turnaround = 0.0
        else:
            status = PAStatus.SUBMITTED
            decided = None
            expires = None
            denial_reason = None
            turnaround = None

        pa = PARequest(
            pa_id=str(uuid.uuid4()),
            patient_id=patient.patient_id,
            prescriber_npi=prescriber_npi,
            prescriber_name=prescriber_name,
            drug_name=drug_name,
            ndc=ndc,
            payer_id=payer_id,
            payer_name=payer_name,
            diagnosis_codes=diagnosis_codes,
            quantity_requested=quantity,
            days_supply=days_supply,
            pa_type=pa_type,
            status=status,
            submitted_at=now.isoformat() + "Z",
            decided_at=decided,
            expires_at=expires,
            denial_reason=denial_reason,
            appeal_level=None,
            criteria_evaluation={k: v.value for k, v in criteria_eval.items()},
            notes=notes,
            turnaround_hours=turnaround,
        )

        self.pa_requests[pa.pa_id] = pa
        self.payer_stats[payer_id][status.value] += 1

        return pa

    def process_decision(
        self,
        pa_id: str,
        approved: bool,
        denial_reason: Optional[DenialReason] = None,
        notes: Optional[str] = None,
    ) -> PARequest:
        """Process a PA decision from the payer."""
        pa = self.pa_requests.get(pa_id)
        if not pa:
            raise ValueError(f"PA {pa_id} not found")

        now = datetime.utcnow()
        pa.decided_at = now.isoformat() + "Z"

        submitted = datetime.fromisoformat(pa.submitted_at.replace("Z", ""))
        pa.turnaround_hours = round((now - submitted).total_seconds() / 3600, 1)

        if approved:
            pa.status = PAStatus.APPROVED
            pa.expires_at = (now + timedelta(days=365)).isoformat() + "Z"
        else:
            pa.status = PAStatus.DENIED
            pa.denial_reason = denial_reason

        if notes:
            pa.notes.append(notes)

        self.payer_stats[pa.payer_id][pa.status.value] += 1

        return pa

    def generate_appeal(
        self,
        pa_id: str,
        patient: PatientHistory,
        appeal_level: AppealLevel = AppealLevel.FIRST_LEVEL,
    ) -> AppealLetter:
        """Generate an appeal letter for a denied PA."""
        pa = self.pa_requests.get(pa_id)
        if not pa:
            raise ValueError(f"PA {pa_id} not found")
        if pa.status not in (PAStatus.DENIED, PAStatus.APPEAL_DENIED):
            raise ValueError("Can only appeal denied PAs")

        # Build clinical justification based on denial reason
        justification_parts = []
        evidence = []

        if pa.denial_reason == DenialReason.STEP_THERAPY_NOT_MET:
            tried = [m for m in patient.medication_history if m.get("days_used", 0) > 0]
            if tried:
                justification_parts.append(
                    "The patient has previously trialed the following medications: "
                    + ", ".join(f"{m['drug_name']} ({m.get('days_used', 'unknown')} days, "
                               f"outcome: {m.get('outcome', 'unknown')})" for m in tried)
                )
            if patient.allergies:
                justification_parts.append(
                    f"Patient has documented allergies/contraindications to: "
                    f"{', '.join(patient.allergies)}"
                )
                evidence.append("Allergy documentation on file")

        elif pa.denial_reason == DenialReason.NOT_MEDICALLY_NECESSARY:
            justification_parts.append(
                f"The requested medication ({pa.drug_name}) is medically necessary for "
                f"the treatment of {', '.join(pa.diagnosis_codes)}."
            )
            if patient.lab_results:
                labs_str = ", ".join(
                    f"{k}: {v}" for k, v in list(patient.lab_results.items())[:5]
                )
                justification_parts.append(f"Supporting lab results: {labs_str}")
                evidence.append("Laboratory results supporting diagnosis")

        elif pa.denial_reason == DenialReason.ALTERNATIVE_AVAILABLE:
            failed = [
                m for m in patient.medication_history
                if m.get("outcome") in ("failed", "adverse_effect", "intolerant")
            ]
            if failed:
                justification_parts.append(
                    "Alternatives have been tried and failed: "
                    + ", ".join(f"{m['drug_name']} (reason: {m.get('outcome', 'unknown')})"
                               for m in failed)
                )
                evidence.append("Documentation of prior treatment failures")

        elif pa.denial_reason == DenialReason.QUANTITY_EXCEEDS_LIMIT:
            justification_parts.append(
                f"The prescribed quantity ({pa.quantity_requested} units / "
                f"{pa.days_supply} days) is clinically appropriate based on "
                f"the patient's condition severity and treatment protocol."
            )

        else:
            justification_parts.append(
                f"This appeal seeks reversal of the denial for {pa.drug_name}. "
                f"The denial reason ({pa.denial_reason.value if pa.denial_reason else 'unspecified'}) "
                f"does not adequately account for this patient's clinical circumstances."
            )

        # Add specialist support
        if patient.specialist_visits:
            recent = patient.specialist_visits[-1] if patient.specialist_visits else None
            if recent:
                justification_parts.append(
                    f"The patient is under the care of {recent.get('provider', 'a specialist')} "
                    f"({recent.get('specialty', 'specialist')}) who supports this prescription."
                )
                evidence.append("Specialist consultation notes")

        clinical_justification = " ".join(justification_parts)

        # Generate letter body
        now = datetime.utcnow()
        letter_body = f"""
PRIOR AUTHORIZATION APPEAL — {appeal_level.value.upper().replace('_', ' ')}
Date: {now.strftime('%B %d, %Y')}
PA Reference: {pa.pa_id}

To: {pa.payer_name} — Prior Authorization Department
Re: Appeal of Denied Prior Authorization for {pa.drug_name}
Patient ID: {pa.patient_id}
Prescriber: {pa.prescriber_name} (NPI: {pa.prescriber_npi})

Dear Prior Authorization Review Committee,

I am writing to appeal the denial of prior authorization for {pa.drug_name} 
(NDC: {pa.ndc}) for patient {pa.patient_id}.

DENIAL REASON: {pa.denial_reason.value.replace('_', ' ').title() if pa.denial_reason else 'Not specified'}

CLINICAL JUSTIFICATION:
{clinical_justification}

DIAGNOSES: {', '.join(pa.diagnosis_codes)}

SUPPORTING EVIDENCE:
{chr(10).join(f'  • {e}' for e in evidence) if evidence else '  • Clinical notes attached'}

REQUEST:
Based on the clinical evidence presented, we respectfully request that the 
prior authorization for {pa.drug_name} ({pa.quantity_requested} units, 
{pa.days_supply} day supply) be approved.

The patient's clinical needs cannot be adequately addressed by formulary 
alternatives, and continued delay in treatment may result in adverse 
health outcomes.

Sincerely,
{pa.prescriber_name}
NPI: {pa.prescriber_npi}
"""

        letter = AppealLetter(
            letter_id=str(uuid.uuid4()),
            pa_id=pa_id,
            appeal_level=appeal_level,
            patient_id=pa.patient_id,
            drug_name=pa.drug_name,
            payer_name=pa.payer_name,
            denial_reason=pa.denial_reason or DenialReason.NOT_MEDICALLY_NECESSARY,
            clinical_justification=clinical_justification,
            supporting_evidence=evidence,
            generated_at=now.isoformat() + "Z",
            letter_body=letter_body.strip(),
        )

        self.appeal_letters.append(letter)
        pa.appeal_level = appeal_level
        pa.status = PAStatus.APPEALING

        return letter

    def get_expiring_pas(self, days_ahead: int = 30) -> List[PARequest]:
        """Get PAs expiring within N days."""
        cutoff = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        now = datetime.utcnow().isoformat() + "Z"

        return [
            pa for pa in self.pa_requests.values()
            if pa.status == PAStatus.APPROVED
            and pa.expires_at
            and now <= pa.expires_at <= cutoff
        ]

    def get_sla_violations(self) -> List[PARequest]:
        """Get PAs that have exceeded their SLA turnaround time."""
        violations = []
        now = datetime.utcnow()

        for pa in self.pa_requests.values():
            if pa.status in (PAStatus.SUBMITTED, PAStatus.PENDING):
                submitted = datetime.fromisoformat(pa.submitted_at.replace("Z", ""))
                elapsed_hours = (now - submitted).total_seconds() / 3600
                sla = PA_SLA_HOURS.get(pa.pa_type, 72)
                if elapsed_hours > sla:
                    violations.append(pa)

        return violations

    def get_payer_performance(self) -> Dict[str, Dict[str, Any]]:
        """Get approval/denial rates per payer."""
        payer_data = defaultdict(lambda: {
            "total": 0, "approved": 0, "denied": 0,
            "turnaround_hours": [],
        })

        for pa in self.pa_requests.values():
            pd = payer_data[pa.payer_name]
            pd["total"] += 1
            if pa.status in (PAStatus.APPROVED, PAStatus.APPEAL_APPROVED):
                pd["approved"] += 1
            elif pa.status in (PAStatus.DENIED, PAStatus.APPEAL_DENIED):
                pd["denied"] += 1
            if pa.turnaround_hours is not None:
                pd["turnaround_hours"].append(pa.turnaround_hours)

        result = {}
        for payer, data in payer_data.items():
            ta_hours = data["turnaround_hours"]
            result[payer] = {
                "total_requests": data["total"],
                "approved": data["approved"],
                "denied": data["denied"],
                "approval_rate": round(data["approved"] / data["total"] * 100, 1) if data["total"] else 0,
                "avg_turnaround_hours": round(statistics.mean(ta_hours), 1) if ta_hours else None,
                "median_turnaround_hours": round(statistics.median(ta_hours), 1) if ta_hours else None,
            }

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall PA engine statistics."""
        by_status = defaultdict(int)
        by_type = defaultdict(int)
        turnaround_times = []

        for pa in self.pa_requests.values():
            by_status[pa.status.value] += 1
            by_type[pa.pa_type.value] += 1
            if pa.turnaround_hours is not None:
                turnaround_times.append(pa.turnaround_hours)

        return {
            "total_pa_requests": len(self.pa_requests),
            "by_status": dict(by_status),
            "by_type": dict(by_type),
            "total_appeals": len(self.appeal_letters),
            "avg_turnaround_hours": round(statistics.mean(turnaround_times), 1) if turnaround_times else None,
            "sla_violations": len(self.get_sla_violations()),
            "expiring_30_days": len(self.get_expiring_pas(30)),
        }


if __name__ == "__main__":
    engine = PriorAuthEngine()

    # Add criteria
    engine.add_criteria(
        drug_name="Ozempic",
        ndc_prefix="0169-4772",
        payer_id="BCBS_KY",
        payer_name="BlueCross BlueShield of Kentucky",
        pa_type=PAType.STEP_THERAPY,
        approved_diagnoses=["E11.9", "E11.65"],  # Type 2 diabetes
        step_therapy_drugs=["Metformin", "Glipizide"],
        step_therapy_min_days=90,
        quantity_limit_per_30=4,
        requires_specialist=False,
        lab_results_required=["HbA1c"],
    )

    # Create patient
    patient = PatientHistory(
        patient_id="PAT001",
        date_of_birth="1975-03-15",
        diagnoses=["E11.9", "E78.5"],
        medication_history=[
            {"drug_name": "Metformin", "days_used": 180, "outcome": "inadequate_response"},
            {"drug_name": "Glipizide", "days_used": 120, "outcome": "adverse_effect"},
        ],
        lab_results={"HbA1c": "8.5%", "fasting_glucose": "185 mg/dL"},
        specialist_visits=[{"specialty": "endocrinology", "provider": "Dr. Chen", "date": "2026-01-15"}],
        allergies=["Sulfonylureas"],
        contraindications=[],
    )

    # Submit PA
    pa = engine.submit_pa(
        patient=patient,
        prescriber_npi="1234567890",
        prescriber_name="Dr. Sarah Miller",
        drug_name="Ozempic",
        ndc="0169-4772-12",
        payer_id="BCBS_KY",
        payer_name="BlueCross BlueShield of Kentucky",
        diagnosis_codes=["E11.9"],
        quantity=4,
        days_supply=30,
        pa_type=PAType.STEP_THERAPY,
    )

    print(f"PA Status: {pa.status.value}")
    print(f"Criteria evaluation: {json.dumps(pa.criteria_evaluation, indent=2)}")
    print(f"Notes: {pa.notes}")

    # If auto-approved
    if pa.status == PAStatus.APPROVED:
        print("✅ Auto-approved! Step therapy requirements met.")
    else:
        # Simulate denial
        pa = engine.process_decision(
            pa.pa_id, approved=False,
            denial_reason=DenialReason.STEP_THERAPY_NOT_MET,
        )
        print(f"\n❌ Denied: {pa.denial_reason.value}")

        # Generate appeal
        appeal = engine.generate_appeal(pa.pa_id, patient)
        print(f"\n📝 Appeal letter generated ({len(appeal.letter_body)} chars)")
        print(appeal.letter_body[:500])

    # Stats
    stats = engine.get_statistics()
    print(f"\nEngine stats: {json.dumps(stats, indent=2)}")
