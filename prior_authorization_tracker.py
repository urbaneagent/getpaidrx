"""
GetPaidRx — Prior Authorization Tracker
Comprehensive prior authorization (PA) management system for pharmacies.
Tracks PA submissions, approvals, denials, appeals, and revenue impact.

Provides:
  - PA lifecycle management (submission → review → approval/denial → appeal)
  - Payer-specific PA requirement database
  - Turnaround time (TAT) tracking and SLA monitoring
  - Revenue impact analysis (lost sales from PA delays/denials)
  - PA appeal management with success rate tracking
  - Prescriber notification automation
  - Step therapy tracking and override management
  - Quantity limit exception handling
  - FastAPI routes for PA dashboard
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

class PAStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DENIED = "denied"
    APPEAL_SUBMITTED = "appeal_submitted"
    APPEAL_APPROVED = "appeal_approved"
    APPEAL_DENIED = "appeal_denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PAType(str, Enum):
    STANDARD_PA = "standard_pa"
    STEP_THERAPY = "step_therapy"
    QUANTITY_LIMIT = "quantity_limit"
    SPECIALTY_PA = "specialty_pa"
    NON_FORMULARY = "non_formulary"
    AGE_LIMIT = "age_limit"
    GENDER_LIMIT = "gender_limit"
    DIAGNOSIS_REQUIRED = "diagnosis_required"


class UrgencyLevel(str, Enum):
    ROUTINE = "routine"        # 72-hour review
    URGENT = "urgent"          # 24-hour review
    EMERGENCY = "emergency"    # 4-hour review


# SLA targets (hours) by urgency
SLA_HOURS = {
    UrgencyLevel.ROUTINE: 72,
    UrgencyLevel.URGENT: 24,
    UrgencyLevel.EMERGENCY: 4,
}

# PA types that commonly require clinical documentation
CLINICAL_DOC_REQUIRED = {
    PAType.STEP_THERAPY,
    PAType.NON_FORMULARY,
    PAType.SPECIALTY_PA,
    PAType.DIAGNOSIS_REQUIRED,
}

TERMINAL_STATUSES = {
    PAStatus.APPROVED, PAStatus.DENIED, PAStatus.APPEAL_APPROVED,
    PAStatus.APPEAL_DENIED, PAStatus.EXPIRED, PAStatus.CANCELLED,
}


# ============================================================
# Data Models
# ============================================================

class PriorAuthorization:
    """A single prior authorization request."""

    def __init__(
        self,
        patient_id: str,
        patient_name: str,
        prescriber_npi: str,
        prescriber_name: str,
        ndc: str,
        drug_name: str,
        payer_name: str,
        pa_type: PAType,
        urgency: UrgencyLevel = UrgencyLevel.ROUTINE,
        quantity_requested: float = 30,
        days_supply: int = 30,
        diagnosis_codes: Optional[List[str]] = None,
        clinical_notes: str = "",
        estimated_claim_value: float = 0,
    ):
        self.pa_id = f"PA-{str(uuid.uuid4())[:8].upper()}"
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.prescriber_npi = prescriber_npi
        self.prescriber_name = prescriber_name
        self.ndc = ndc
        self.drug_name = drug_name
        self.payer_name = payer_name
        self.pa_type = pa_type
        self.urgency = urgency
        self.quantity_requested = quantity_requested
        self.days_supply = days_supply
        self.diagnosis_codes = diagnosis_codes or []
        self.clinical_notes = clinical_notes
        self.estimated_claim_value = estimated_claim_value

        # Status tracking
        self.status = PAStatus.SUBMITTED
        self.submitted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.resolved_at: Optional[datetime] = None

        # Authorization details (when approved)
        self.auth_number: Optional[str] = None
        self.auth_start_date: Optional[str] = None
        self.auth_end_date: Optional[str] = None
        self.approved_quantity: Optional[float] = None
        self.approved_days_supply: Optional[int] = None

        # Denial details
        self.denial_reason: Optional[str] = None
        self.denial_code: Optional[str] = None

        # Appeal tracking
        self.appeals: List[Dict[str, Any]] = []
        self.appeal_count: int = 0

        # Timeline events
        self.events: List[Dict[str, Any]] = [
            {
                "event": "submitted",
                "timestamp": self.submitted_at.isoformat(),
                "detail": f"{pa_type.value} PA submitted for {drug_name}",
            }
        ]

        # Step therapy history (for step therapy PAs)
        self.step_therapy_history: List[Dict[str, Any]] = []

        # Notifications sent
        self.notifications: List[Dict[str, Any]] = []

    @property
    def sla_deadline(self) -> datetime:
        hours = SLA_HOURS.get(self.urgency, 72)
        return self.submitted_at + timedelta(hours=hours)

    @property
    def is_sla_breached(self) -> bool:
        if self.status in TERMINAL_STATUSES:
            return False
        return datetime.utcnow() > self.sla_deadline

    @property
    def turnaround_hours(self) -> Optional[float]:
        if self.resolved_at:
            return round((self.resolved_at - self.submitted_at).total_seconds() / 3600, 1)
        return None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def update_status(self, new_status: PAStatus, detail: str = "", **kwargs):
        """Update PA status and record event."""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        self.events.append({
            "event": new_status.value,
            "timestamp": self.updated_at.isoformat(),
            "detail": detail,
        })

        if new_status in TERMINAL_STATUSES:
            self.resolved_at = self.updated_at

        # Handle specific status updates
        if new_status == PAStatus.APPROVED:
            self.auth_number = kwargs.get("auth_number", f"AUTH-{uuid.uuid4().hex[:8].upper()}")
            self.auth_start_date = kwargs.get("auth_start_date", datetime.utcnow().strftime("%Y-%m-%d"))
            self.auth_end_date = kwargs.get("auth_end_date",
                (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d"))
            self.approved_quantity = kwargs.get("approved_quantity", self.quantity_requested)
            self.approved_days_supply = kwargs.get("approved_days_supply", self.days_supply)

        elif new_status == PAStatus.DENIED:
            self.denial_reason = kwargs.get("denial_reason", "")
            self.denial_code = kwargs.get("denial_code", "")

    def submit_appeal(self, reason: str, supporting_docs: str = "", appeal_type: str = "standard") -> str:
        """Submit an appeal for a denied PA."""
        if self.status not in (PAStatus.DENIED, PAStatus.APPEAL_DENIED):
            return ""

        appeal_id = f"APL-{uuid.uuid4().hex[:6].upper()}"
        self.appeal_count += 1
        appeal = {
            "appeal_id": appeal_id,
            "appeal_number": self.appeal_count,
            "appeal_type": appeal_type,
            "reason": reason,
            "supporting_docs": supporting_docs,
            "submitted_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
            "outcome": None,
        }
        self.appeals.append(appeal)
        self.update_status(PAStatus.APPEAL_SUBMITTED, f"Appeal #{self.appeal_count}: {reason}")
        return appeal_id

    def add_step_therapy_trial(self, drug_name: str, ndc: str, start_date: str, end_date: str,
                                outcome: str, reason_for_failure: str = ""):
        """Record a step therapy trial."""
        self.step_therapy_history.append({
            "drug_name": drug_name,
            "ndc": ndc,
            "start_date": start_date,
            "end_date": end_date,
            "outcome": outcome,
            "reason_for_failure": reason_for_failure,
            "recorded_at": datetime.utcnow().isoformat(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pa_id": self.pa_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "prescriber_npi": self.prescriber_npi,
            "prescriber_name": self.prescriber_name,
            "ndc": self.ndc,
            "drug_name": self.drug_name,
            "payer_name": self.payer_name,
            "pa_type": self.pa_type.value,
            "urgency": self.urgency.value,
            "status": self.status.value,
            "quantity_requested": self.quantity_requested,
            "days_supply": self.days_supply,
            "diagnosis_codes": self.diagnosis_codes,
            "estimated_claim_value": self.estimated_claim_value,
            "submitted_at": self.submitted_at.isoformat(),
            "sla_deadline": self.sla_deadline.isoformat(),
            "is_sla_breached": self.is_sla_breached,
            "turnaround_hours": self.turnaround_hours,
            "auth_number": self.auth_number,
            "auth_start_date": self.auth_start_date,
            "auth_end_date": self.auth_end_date,
            "approved_quantity": self.approved_quantity,
            "denial_reason": self.denial_reason,
            "denial_code": self.denial_code,
            "appeal_count": self.appeal_count,
            "step_therapy_trials": len(self.step_therapy_history),
            "event_count": len(self.events),
        }


# ============================================================
# PA Requirements Database
# ============================================================

class PARequirementsDB:
    """Database of payer-specific PA requirements by drug."""

    def __init__(self):
        # (payer, ndc/drug_class) → requirement config
        self.requirements: Dict[str, Dict[str, Any]] = {}

    def add_requirement(
        self,
        payer_name: str,
        drug_identifier: str,  # NDC or drug class
        pa_type: PAType,
        criteria: str = "",
        step_therapy_drugs: Optional[List[str]] = None,
        quantity_limit: Optional[float] = None,
        quantity_limit_days: Optional[int] = None,
        age_range: Optional[Tuple[int, int]] = None,
        required_diagnoses: Optional[List[str]] = None,
    ):
        key = f"{payer_name}::{drug_identifier}"
        self.requirements[key] = {
            "payer_name": payer_name,
            "drug_identifier": drug_identifier,
            "pa_type": pa_type.value,
            "criteria": criteria,
            "step_therapy_drugs": step_therapy_drugs or [],
            "quantity_limit": quantity_limit,
            "quantity_limit_days": quantity_limit_days,
            "age_range": age_range,
            "required_diagnoses": required_diagnoses or [],
            "added_at": datetime.utcnow().isoformat(),
        }

    def check_pa_needed(self, payer_name: str, ndc: str, drug_class: str = "") -> Optional[Dict]:
        """Check if a PA is required for this payer/drug combination."""
        # Check NDC-specific first
        key_ndc = f"{payer_name}::{ndc}"
        if key_ndc in self.requirements:
            return self.requirements[key_ndc]

        # Check drug class
        if drug_class:
            key_class = f"{payer_name}::{drug_class}"
            if key_class in self.requirements:
                return self.requirements[key_class]

        return None

    def get_payer_requirements(self, payer_name: str) -> List[Dict]:
        return [v for k, v in self.requirements.items() if k.startswith(f"{payer_name}::")]


# ============================================================
# Prior Authorization Tracker Engine
# ============================================================

class PriorAuthorizationTracker:
    """
    Central PA management engine. Tracks PA lifecycle, analytics,
    and revenue impact.
    """

    def __init__(self):
        self.authorizations: Dict[str, PriorAuthorization] = {}
        self.requirements_db = PARequirementsDB()

    # ----------------------------------------------------------
    # PA Lifecycle
    # ----------------------------------------------------------

    def submit_pa(self, **kwargs) -> PriorAuthorization:
        pa = PriorAuthorization(**kwargs)
        self.authorizations[pa.pa_id] = pa
        return pa

    def get_pa(self, pa_id: str) -> Optional[PriorAuthorization]:
        return self.authorizations.get(pa_id)

    def approve_pa(self, pa_id: str, **kwargs) -> Tuple[bool, str]:
        pa = self.authorizations.get(pa_id)
        if not pa:
            return False, "PA not found"
        if pa.status not in (PAStatus.SUBMITTED, PAStatus.IN_REVIEW, PAStatus.APPEAL_SUBMITTED):
            return False, f"Cannot approve PA in status {pa.status.value}"

        if pa.status == PAStatus.APPEAL_SUBMITTED:
            pa.update_status(PAStatus.APPEAL_APPROVED, "Appeal approved", **kwargs)
            # Update last appeal
            if pa.appeals:
                pa.appeals[-1]["resolved_at"] = datetime.utcnow().isoformat()
                pa.appeals[-1]["outcome"] = "approved"
        else:
            pa.update_status(PAStatus.APPROVED, "PA approved", **kwargs)

        return True, f"PA {pa_id} approved. Auth#: {pa.auth_number}"

    def deny_pa(self, pa_id: str, denial_reason: str = "", denial_code: str = "") -> Tuple[bool, str]:
        pa = self.authorizations.get(pa_id)
        if not pa:
            return False, "PA not found"
        if pa.status not in (PAStatus.SUBMITTED, PAStatus.IN_REVIEW, PAStatus.APPEAL_SUBMITTED):
            return False, f"Cannot deny PA in status {pa.status.value}"

        if pa.status == PAStatus.APPEAL_SUBMITTED:
            pa.update_status(PAStatus.APPEAL_DENIED, denial_reason,
                           denial_reason=denial_reason, denial_code=denial_code)
            if pa.appeals:
                pa.appeals[-1]["resolved_at"] = datetime.utcnow().isoformat()
                pa.appeals[-1]["outcome"] = "denied"
        else:
            pa.update_status(PAStatus.DENIED, denial_reason,
                           denial_reason=denial_reason, denial_code=denial_code)

        return True, f"PA {pa_id} denied: {denial_reason}"

    def submit_appeal(self, pa_id: str, reason: str, supporting_docs: str = "") -> Tuple[bool, str]:
        pa = self.authorizations.get(pa_id)
        if not pa:
            return False, "PA not found"
        appeal_id = pa.submit_appeal(reason, supporting_docs)
        if appeal_id:
            return True, f"Appeal {appeal_id} submitted for PA {pa_id}"
        return False, "Can only appeal denied PAs"

    # ----------------------------------------------------------
    # Dashboard Queries
    # ----------------------------------------------------------

    def get_active_pas(self, payer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all non-terminal PAs."""
        active = []
        for pa in self.authorizations.values():
            if pa.is_terminal:
                continue
            if payer_name and pa.payer_name != payer_name:
                continue
            active.append(pa.to_dict())

        active.sort(key=lambda p: p["submitted_at"])
        return active

    def get_sla_breaches(self) -> List[Dict[str, Any]]:
        """Get PAs that have breached SLA."""
        breached = []
        for pa in self.authorizations.values():
            if pa.is_sla_breached:
                breached.append({
                    **pa.to_dict(),
                    "hours_overdue": round(
                        (datetime.utcnow() - pa.sla_deadline).total_seconds() / 3600, 1
                    ),
                })
        breached.sort(key=lambda p: p["hours_overdue"], reverse=True)
        return breached

    def get_pa_dashboard(self) -> Dict[str, Any]:
        """Comprehensive PA dashboard metrics."""
        all_pas = list(self.authorizations.values())
        if not all_pas:
            return {"message": "No PAs tracked yet", "total": 0}

        total = len(all_pas)
        status_counts = defaultdict(int)
        type_counts = defaultdict(int)
        payer_counts = defaultdict(lambda: {"total": 0, "approved": 0, "denied": 0, "pending": 0})

        turnaround_times = []
        approved_values = []
        denied_values = []
        sla_breaches = 0

        for pa in all_pas:
            status_counts[pa.status.value] += 1
            type_counts[pa.pa_type.value] += 1

            pc = payer_counts[pa.payer_name]
            pc["total"] += 1
            if pa.status in (PAStatus.APPROVED, PAStatus.APPEAL_APPROVED):
                pc["approved"] += 1
                approved_values.append(pa.estimated_claim_value)
            elif pa.status in (PAStatus.DENIED, PAStatus.APPEAL_DENIED):
                pc["denied"] += 1
                denied_values.append(pa.estimated_claim_value)
            else:
                pc["pending"] += 1

            if pa.turnaround_hours is not None:
                turnaround_times.append(pa.turnaround_hours)

            if pa.is_sla_breached:
                sla_breaches += 1

        # Approval rate
        resolved = [pa for pa in all_pas if pa.is_terminal and pa.status != PAStatus.CANCELLED]
        approved = [pa for pa in resolved if pa.status in (PAStatus.APPROVED, PAStatus.APPEAL_APPROVED)]
        approval_rate = round(len(approved) / max(len(resolved), 1) * 100, 1)

        # Appeal success rate
        appeal_pas = [pa for pa in all_pas if pa.appeal_count > 0]
        appeal_successes = sum(1 for pa in appeal_pas if pa.status == PAStatus.APPEAL_APPROVED)
        appeal_success_rate = round(appeal_successes / max(len(appeal_pas), 1) * 100, 1)

        # Revenue impact
        total_approved_revenue = sum(approved_values)
        total_denied_revenue = sum(denied_values)

        avg_tat = round(statistics.mean(turnaround_times), 1) if turnaround_times else 0
        median_tat = round(statistics.median(turnaround_times), 1) if turnaround_times else 0

        return {
            "total_pas": total,
            "status_distribution": dict(status_counts),
            "type_distribution": dict(type_counts),
            "approval_rate_pct": approval_rate,
            "appeal_success_rate_pct": appeal_success_rate,
            "avg_turnaround_hours": avg_tat,
            "median_turnaround_hours": median_tat,
            "sla_breaches": sla_breaches,
            "sla_breach_rate_pct": round(sla_breaches / max(total, 1) * 100, 1),
            "revenue_impact": {
                "approved_claim_value": round(total_approved_revenue, 2),
                "denied_claim_value": round(total_denied_revenue, 2),
                "pending_claim_value": round(
                    sum(pa.estimated_claim_value for pa in all_pas if not pa.is_terminal), 2
                ),
                "annualized_denied_revenue": round(total_denied_revenue * (365 / 30), 2),
            },
            "payer_breakdown": [
                {
                    "payer": k,
                    "total": v["total"],
                    "approved": v["approved"],
                    "denied": v["denied"],
                    "pending": v["pending"],
                    "approval_rate": round(v["approved"] / max(v["total"], 1) * 100, 1),
                }
                for k, v in sorted(payer_counts.items(), key=lambda x: x[1]["total"], reverse=True)
            ],
        }

    # ----------------------------------------------------------
    # Revenue Impact Analysis
    # ----------------------------------------------------------

    def revenue_impact_report(self, lookback_days: int = 30) -> Dict[str, Any]:
        """
        Calculate the revenue impact of PA denials and delays.
        Includes opportunity cost of delayed fills.
        """
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        period_pas = [pa for pa in self.authorizations.values() if pa.submitted_at >= cutoff]

        if not period_pas:
            return {"message": "No PAs in period", "lookback_days": lookback_days}

        # Revenue by outcome
        approved_revenue = 0
        denied_revenue = 0
        pending_revenue = 0
        delayed_revenue = 0  # Claims delayed by PA process

        drug_denial_map = defaultdict(lambda: {"count": 0, "value": 0, "drug_name": ""})
        payer_denial_map = defaultdict(lambda: {"count": 0, "value": 0})

        for pa in period_pas:
            if pa.status in (PAStatus.APPROVED, PAStatus.APPEAL_APPROVED):
                approved_revenue += pa.estimated_claim_value
                # Calculate delay cost (opportunity cost of waiting)
                if pa.turnaround_hours and pa.turnaround_hours > 24:
                    delay_days = pa.turnaround_hours / 24
                    daily_value = pa.estimated_claim_value / max(pa.days_supply, 1)
                    delayed_revenue += daily_value * min(delay_days, pa.days_supply)
            elif pa.status in (PAStatus.DENIED, PAStatus.APPEAL_DENIED):
                denied_revenue += pa.estimated_claim_value
                dd = drug_denial_map[pa.ndc]
                dd["count"] += 1
                dd["value"] += pa.estimated_claim_value
                dd["drug_name"] = pa.drug_name
                pd = payer_denial_map[pa.payer_name]
                pd["count"] += 1
                pd["value"] += pa.estimated_claim_value
            elif not pa.is_terminal:
                pending_revenue += pa.estimated_claim_value

        top_denied_drugs = sorted(drug_denial_map.items(), key=lambda x: x[1]["value"], reverse=True)[:10]
        top_denied_payers = sorted(payer_denial_map.items(), key=lambda x: x[1]["value"], reverse=True)[:10]

        return {
            "lookback_days": lookback_days,
            "total_pas": len(period_pas),
            "approved_revenue": round(approved_revenue, 2),
            "denied_revenue": round(denied_revenue, 2),
            "pending_revenue": round(pending_revenue, 2),
            "delay_opportunity_cost": round(delayed_revenue, 2),
            "total_revenue_at_risk": round(denied_revenue + pending_revenue + delayed_revenue, 2),
            "annualized_denial_loss": round(denied_revenue * (365 / lookback_days), 2),
            "top_denied_drugs": [
                {"ndc": ndc, "drug_name": d["drug_name"], "denial_count": d["count"], "value_lost": round(d["value"], 2)}
                for ndc, d in top_denied_drugs
            ],
            "top_denial_payers": [
                {"payer": p, "denial_count": d["count"], "value_denied": round(d["value"], 2)}
                for p, d in top_denied_payers
            ],
        }

    # ----------------------------------------------------------
    # Prescriber PA Report
    # ----------------------------------------------------------

    def prescriber_report(self, prescriber_npi: str) -> Dict[str, Any]:
        """Generate a report for a specific prescriber's PAs."""
        prescriber_pas = [
            pa for pa in self.authorizations.values()
            if pa.prescriber_npi == prescriber_npi
        ]
        if not prescriber_pas:
            return {"error": "No PAs found for this prescriber"}

        name = prescriber_pas[0].prescriber_name
        total = len(prescriber_pas)
        resolved = [pa for pa in prescriber_pas if pa.is_terminal and pa.status != PAStatus.CANCELLED]
        approved = [pa for pa in resolved if pa.status in (PAStatus.APPROVED, PAStatus.APPEAL_APPROVED)]

        # Drugs that frequently need PAs for this prescriber
        drug_pa_counts = defaultdict(int)
        for pa in prescriber_pas:
            drug_pa_counts[pa.drug_name] += 1
        top_drugs = sorted(drug_pa_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        tat = [pa.turnaround_hours for pa in prescriber_pas if pa.turnaround_hours is not None]

        return {
            "prescriber_npi": prescriber_npi,
            "prescriber_name": name,
            "total_pas": total,
            "approval_rate_pct": round(len(approved) / max(len(resolved), 1) * 100, 1),
            "avg_turnaround_hours": round(statistics.mean(tat), 1) if tat else 0,
            "frequent_pa_drugs": [{"drug": d, "count": c} for d, c in top_drugs],
            "pending_count": sum(1 for pa in prescriber_pas if not pa.is_terminal),
        }

    # ----------------------------------------------------------
    # Notification Generator
    # ----------------------------------------------------------

    def generate_prescriber_notification(self, pa_id: str) -> Optional[Dict[str, Any]]:
        """Generate a notification to send to the prescriber about a PA."""
        pa = self.authorizations.get(pa_id)
        if not pa:
            return None

        templates = {
            PAStatus.SUBMITTED: (
                f"PA Submitted: {pa.drug_name}",
                f"A prior authorization has been submitted to {pa.payer_name} for patient {pa.patient_name}. "
                f"PA Type: {pa.pa_type.value}. Expected response within {SLA_HOURS[pa.urgency]} hours."
            ),
            PAStatus.APPROVED: (
                f"✅ PA Approved: {pa.drug_name}",
                f"Good news! PA for {pa.drug_name} for patient {pa.patient_name} has been approved. "
                f"Auth#: {pa.auth_number}. Valid: {pa.auth_start_date} to {pa.auth_end_date}."
            ),
            PAStatus.DENIED: (
                f"❌ PA Denied: {pa.drug_name}",
                f"PA for {pa.drug_name} for patient {pa.patient_name} was denied by {pa.payer_name}. "
                f"Reason: {pa.denial_reason}. An appeal may be submitted with additional clinical documentation."
            ),
        }

        if pa.status in templates:
            subject, body = templates[pa.status]
            notification = {
                "pa_id": pa.pa_id,
                "prescriber_npi": pa.prescriber_npi,
                "prescriber_name": pa.prescriber_name,
                "subject": subject,
                "body": body,
                "urgency": pa.urgency.value,
                "generated_at": datetime.utcnow().isoformat(),
            }
            pa.notifications.append(notification)
            return notification
        return None


# ============================================================
# FastAPI Route Registration
# ============================================================

def register_pa_routes(app, tracker: Optional[PriorAuthorizationTracker] = None):
    """Register PA tracker API routes."""
    from fastapi import Body

    if tracker is None:
        tracker = PriorAuthorizationTracker()

    @app.post("/api/v1/pa/submit")
    async def submit_pa(payload: Dict[str, Any] = Body(...)):
        pa = tracker.submit_pa(
            patient_id=payload["patient_id"],
            patient_name=payload["patient_name"],
            prescriber_npi=payload["prescriber_npi"],
            prescriber_name=payload["prescriber_name"],
            ndc=payload["ndc"],
            drug_name=payload["drug_name"],
            payer_name=payload["payer_name"],
            pa_type=PAType(payload.get("pa_type", "standard_pa")),
            urgency=UrgencyLevel(payload.get("urgency", "routine")),
            quantity_requested=payload.get("quantity_requested", 30),
            days_supply=payload.get("days_supply", 30),
            diagnosis_codes=payload.get("diagnosis_codes", []),
            clinical_notes=payload.get("clinical_notes", ""),
            estimated_claim_value=payload.get("estimated_claim_value", 0),
        )
        return pa.to_dict()

    @app.get("/api/v1/pa/{pa_id}")
    async def get_pa(pa_id: str):
        pa = tracker.get_pa(pa_id)
        return pa.to_dict() if pa else {"error": "Not found"}

    @app.post("/api/v1/pa/{pa_id}/approve")
    async def approve_pa(pa_id: str, payload: Dict[str, Any] = Body(default={})):
        success, msg = tracker.approve_pa(pa_id, **payload)
        return {"success": success, "message": msg}

    @app.post("/api/v1/pa/{pa_id}/deny")
    async def deny_pa(pa_id: str, payload: Dict[str, Any] = Body(...)):
        success, msg = tracker.deny_pa(pa_id, payload.get("reason", ""), payload.get("code", ""))
        return {"success": success, "message": msg}

    @app.post("/api/v1/pa/{pa_id}/appeal")
    async def appeal_pa(pa_id: str, payload: Dict[str, Any] = Body(...)):
        success, msg = tracker.submit_appeal(pa_id, payload["reason"], payload.get("supporting_docs", ""))
        return {"success": success, "message": msg}

    @app.get("/api/v1/pa/active")
    async def get_active(payer: Optional[str] = None):
        return tracker.get_active_pas(payer)

    @app.get("/api/v1/pa/sla-breaches")
    async def get_breaches():
        return tracker.get_sla_breaches()

    @app.get("/api/v1/pa/dashboard")
    async def get_dashboard():
        return tracker.get_pa_dashboard()

    @app.get("/api/v1/pa/revenue-impact")
    async def get_revenue_impact(lookback_days: int = 30):
        return tracker.revenue_impact_report(lookback_days)

    @app.get("/api/v1/pa/prescriber/{npi}")
    async def get_prescriber_report(npi: str):
        return tracker.prescriber_report(npi)

    return tracker
