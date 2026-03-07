"""
GetPaidRx — 340B Drug Pricing Program Compliance Monitor
Monitors compliance with the 340B program to prevent duplicate discounts,
track covered entity eligibility, and ensure proper contract pharmacy
utilization.

Features:
  - 340B ceiling price verification against WAC/NADAC benchmarks
  - Duplicate discount prevention (340B + Medicaid rebate detection)
  - Covered entity eligibility tracking (HRSA database integration)
  - Contract pharmacy utilization analysis
  - Split billing and carve-in/carve-out compliance
  - Manufacturer rebate conflict detection
  - 340B savings quantification per drug/entity/quarter
  - HRSA audit readiness scoring
"""

import json
import uuid
import math
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class EntityType(str, Enum):
    DSH = "disproportionate_share_hospital"
    CHC = "community_health_center"
    FQHC = "federally_qualified_health_center"
    STD_CLINIC = "std_clinic"
    TB_CLINIC = "tb_clinic"
    HEMOPHILIA = "hemophilia_treatment_center"
    RYAN_WHITE = "ryan_white_hiv_aids"
    BLACK_LUNG = "black_lung_clinic"
    FAMILY_PLANNING = "family_planning"
    CHILDREN_HOSPITAL = "free_standing_childrens_hospital"
    CRITICAL_ACCESS = "critical_access_hospital"
    SOLE_COMMUNITY = "sole_community_hospital"
    RURAL_REFERRAL = "rural_referral_center"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    UNDER_REVIEW = "under_review"
    EXEMPT = "exempt"


class DiscountType(str, Enum):
    CEILING_PRICE = "340b_ceiling_price"
    SUB_CEILING = "sub_ceiling"
    PHS_PRICE = "phs_price"
    NOMINAL_PRICE = "nominal_price"


class BillingModel(str, Enum):
    CARVE_IN = "carve_in"      # 340B drugs billed to Medicaid
    CARVE_OUT = "carve_out"    # 340B drugs NOT billed to Medicaid
    SPLIT_BILLING = "split_billing"  # Mixed approach


class AuditRisk(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# 340B ceiling price formula: AMP * (1 - unit rebate amount percentage)
# For generics: AMP * (1 - URA%) where URA = 13% for innovator, 23.1% for generics
INNOVATOR_REBATE_PCT = 0.235  # 23.5% (2026 effective rate)
GENERIC_REBATE_PCT = 0.13     # 13%
PEDIATRIC_ADDITIONAL_PCT = 0.17  # Additional 17% for certain pediatric drugs

# Compliance thresholds
DUPLICATE_DISCOUNT_THRESHOLD = 0.01  # $0.01 tolerance for floating point
CEILING_PRICE_TOLERANCE_PCT = 0.005  # 0.5% tolerance above ceiling
MIN_SAVINGS_THRESHOLD = 0.50  # Flag if savings per unit < $0.50


# ============================================================
# Data Classes
# ============================================================

@dataclass
class CoveredEntity:
    """A 340B covered entity (hospital, clinic, etc.)."""
    entity_id: str
    hrsa_id: str
    name: str
    entity_type: EntityType
    address: str
    state: str
    dsh_pct: Optional[float]   # DSH adjustment percentage
    is_eligible: bool
    registration_date: str
    last_recertification: str
    contract_pharmacies: List[str]
    billing_model: BillingModel
    medicaid_provider_number: Optional[str]
    npi: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "hrsa_id": self.hrsa_id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "state": self.state,
            "is_eligible": self.is_eligible,
            "billing_model": self.billing_model.value,
            "contract_pharmacies": len(self.contract_pharmacies),
        }


@dataclass
class Drug340BRecord:
    """A drug record for 340B pricing analysis."""
    ndc: str
    drug_name: str
    manufacturer: str
    is_innovator: bool  # True = brand/innovator, False = generic
    amp: float          # Average Manufacturer Price
    wac: float          # Wholesale Acquisition Cost
    nadac: Optional[float]  # NADAC price if available
    ceiling_price: float    # Calculated 340B ceiling price
    actual_340b_price: float  # What the entity actually paid
    unit_of_measure: str
    package_size: int
    is_pediatric: bool
    is_specialty: bool

    @property
    def savings_per_unit(self) -> float:
        return self.wac - self.actual_340b_price

    @property
    def savings_pct(self) -> float:
        return (self.savings_per_unit / self.wac * 100) if self.wac > 0 else 0


@dataclass
class ClaimRecord340B:
    """A claim that may involve 340B drugs."""
    claim_id: str
    entity_id: str
    ndc: str
    drug_name: str
    quantity: float
    claim_date: str
    payer_type: str      # medicaid, medicare, commercial, uninsured
    is_340b_eligible: bool
    is_340b_dispensed: bool
    billed_amount: float
    paid_amount: float
    ceiling_price_unit: float
    actual_acquisition_cost: float
    has_medicaid_rebate: bool
    has_manufacturer_rebate: bool
    contract_pharmacy_id: Optional[str]
    patient_id: str


@dataclass
class DuplicateDiscountAlert:
    """Alert for potential duplicate discount violation."""
    alert_id: str
    claim_id: str
    entity_id: str
    ndc: str
    drug_name: str
    violation_type: str
    description: str
    estimated_overpayment: float
    severity: AuditRisk
    detected_at: str
    resolved: bool = False


@dataclass
class ComplianceReport:
    """340B compliance report for an entity."""
    report_id: str
    entity_id: str
    entity_name: str
    period_start: str
    period_end: str
    overall_status: ComplianceStatus
    audit_risk: AuditRisk
    audit_readiness_score: float  # 0-100
    total_claims: int
    eligible_claims: int
    flagged_claims: int
    duplicate_discount_alerts: int
    ceiling_price_violations: int
    total_savings: float
    savings_at_risk: float
    recommendations: List[str]
    findings: List[Dict[str, Any]]


# ============================================================
# 340B Compliance Engine
# ============================================================

class Program340BCompliance:
    """
    Monitors 340B program compliance, detects duplicate discounts,
    verifies ceiling prices, and generates audit-ready reports.
    """

    def __init__(self):
        self.entities: Dict[str, CoveredEntity] = {}
        self.drug_catalog: Dict[str, Drug340BRecord] = {}  # NDC -> record
        self.claims: List[ClaimRecord340B] = []
        self.alerts: List[DuplicateDiscountAlert] = []
        self.claim_index_by_entity: Dict[str, List[int]] = defaultdict(list)
        self.claim_index_by_ndc: Dict[str, List[int]] = defaultdict(list)
        self.claim_index_by_patient: Dict[str, List[int]] = defaultdict(list)

    def register_entity(
        self,
        hrsa_id: str,
        name: str,
        entity_type: EntityType,
        address: str,
        state: str,
        billing_model: BillingModel = BillingModel.CARVE_OUT,
        dsh_pct: Optional[float] = None,
        contract_pharmacies: Optional[List[str]] = None,
        medicaid_provider_number: Optional[str] = None,
        npi: Optional[str] = None,
    ) -> CoveredEntity:
        """Register a 340B covered entity."""
        entity_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        entity = CoveredEntity(
            entity_id=entity_id,
            hrsa_id=hrsa_id,
            name=name,
            entity_type=entity_type,
            address=address,
            state=state,
            dsh_pct=dsh_pct,
            is_eligible=True,
            registration_date=now,
            last_recertification=now,
            contract_pharmacies=contract_pharmacies or [],
            billing_model=billing_model,
            medicaid_provider_number=medicaid_provider_number,
            npi=npi,
        )
        self.entities[entity_id] = entity
        return entity

    def calculate_ceiling_price(
        self, amp: float, is_innovator: bool, is_pediatric: bool = False
    ) -> float:
        """Calculate the 340B ceiling price for a drug."""
        if is_innovator:
            rebate_pct = INNOVATOR_REBATE_PCT
        else:
            rebate_pct = GENERIC_REBATE_PCT

        if is_pediatric:
            rebate_pct += PEDIATRIC_ADDITIONAL_PCT

        ceiling = amp * (1 - rebate_pct)

        # Floor: ceiling price cannot be less than $0.01 per unit
        return max(0.01, round(ceiling, 4))

    def add_drug(
        self,
        ndc: str,
        drug_name: str,
        manufacturer: str,
        is_innovator: bool,
        amp: float,
        wac: float,
        actual_340b_price: float,
        nadac: Optional[float] = None,
        unit_of_measure: str = "each",
        package_size: int = 1,
        is_pediatric: bool = False,
        is_specialty: bool = False,
    ) -> Drug340BRecord:
        """Add a drug to the 340B catalog with ceiling price calculation."""
        ceiling = self.calculate_ceiling_price(amp, is_innovator, is_pediatric)

        record = Drug340BRecord(
            ndc=ndc,
            drug_name=drug_name,
            manufacturer=manufacturer,
            is_innovator=is_innovator,
            amp=amp,
            wac=wac,
            nadac=nadac,
            ceiling_price=ceiling,
            actual_340b_price=actual_340b_price,
            unit_of_measure=unit_of_measure,
            package_size=package_size,
            is_pediatric=is_pediatric,
            is_specialty=is_specialty,
        )
        self.drug_catalog[ndc] = record
        return record

    def submit_claim(self, claim: ClaimRecord340B) -> List[DuplicateDiscountAlert]:
        """Submit a claim and check for compliance violations."""
        idx = len(self.claims)
        self.claims.append(claim)
        self.claim_index_by_entity[claim.entity_id].append(idx)
        self.claim_index_by_ndc[claim.ndc].append(idx)
        self.claim_index_by_patient[claim.patient_id].append(idx)

        # Run compliance checks
        alerts = []

        # Check 1: Duplicate discount (340B + Medicaid rebate)
        if claim.is_340b_dispensed and claim.has_medicaid_rebate:
            alert = DuplicateDiscountAlert(
                alert_id=str(uuid.uuid4()),
                claim_id=claim.claim_id,
                entity_id=claim.entity_id,
                ndc=claim.ndc,
                drug_name=claim.drug_name,
                violation_type="duplicate_discount_340b_medicaid",
                description=(
                    f"Drug dispensed at 340B price AND Medicaid rebate claimed. "
                    f"This is a prohibited duplicate discount under 340B statute."
                ),
                estimated_overpayment=claim.paid_amount * INNOVATOR_REBATE_PCT,
                severity=AuditRisk.CRITICAL,
                detected_at=datetime.utcnow().isoformat() + "Z",
            )
            alerts.append(alert)
            self.alerts.append(alert)

        # Check 2: Ceiling price violation
        drug = self.drug_catalog.get(claim.ndc)
        if drug and claim.actual_acquisition_cost > drug.ceiling_price * (1 + CEILING_PRICE_TOLERANCE_PCT):
            overpayment = (claim.actual_acquisition_cost - drug.ceiling_price) * claim.quantity
            alert = DuplicateDiscountAlert(
                alert_id=str(uuid.uuid4()),
                claim_id=claim.claim_id,
                entity_id=claim.entity_id,
                ndc=claim.ndc,
                drug_name=claim.drug_name,
                violation_type="ceiling_price_exceeded",
                description=(
                    f"Acquisition cost ${claim.actual_acquisition_cost:.4f} exceeds "
                    f"340B ceiling price ${drug.ceiling_price:.4f} by "
                    f"{((claim.actual_acquisition_cost/drug.ceiling_price - 1) * 100):.1f}%"
                ),
                estimated_overpayment=overpayment,
                severity=AuditRisk.HIGH,
                detected_at=datetime.utcnow().isoformat() + "Z",
            )
            alerts.append(alert)
            self.alerts.append(alert)

        # Check 3: Manufacturer rebate + 340B conflict
        if claim.is_340b_dispensed and claim.has_manufacturer_rebate:
            alert = DuplicateDiscountAlert(
                alert_id=str(uuid.uuid4()),
                claim_id=claim.claim_id,
                entity_id=claim.entity_id,
                ndc=claim.ndc,
                drug_name=claim.drug_name,
                violation_type="manufacturer_rebate_conflict",
                description=(
                    "Manufacturer rebate claimed on 340B-dispensed drug. "
                    "May constitute a duplicate discount depending on payer."
                ),
                estimated_overpayment=claim.paid_amount * 0.10,
                severity=AuditRisk.MODERATE,
                detected_at=datetime.utcnow().isoformat() + "Z",
            )
            alerts.append(alert)
            self.alerts.append(alert)

        # Check 4: Carve-in model Medicaid claim without 340B flag
        entity = self.entities.get(claim.entity_id)
        if entity and entity.billing_model == BillingModel.CARVE_IN:
            if claim.payer_type == "medicaid" and not claim.is_340b_dispensed:
                # In carve-in model, Medicaid claims should use 340B drugs
                alert = DuplicateDiscountAlert(
                    alert_id=str(uuid.uuid4()),
                    claim_id=claim.claim_id,
                    entity_id=claim.entity_id,
                    ndc=claim.ndc,
                    drug_name=claim.drug_name,
                    violation_type="carve_in_non_340b",
                    description=(
                        "Entity uses carve-in model but Medicaid claim not flagged as 340B. "
                        "May be missing 340B savings or creating compliance gap."
                    ),
                    estimated_overpayment=0,
                    severity=AuditRisk.LOW,
                    detected_at=datetime.utcnow().isoformat() + "Z",
                )
                alerts.append(alert)
                self.alerts.append(alert)

        return alerts

    def check_entity_eligibility(self, entity_id: str) -> Dict[str, Any]:
        """Check if an entity is still eligible for 340B."""
        entity = self.entities.get(entity_id)
        if not entity:
            return {"eligible": False, "reason": "Entity not found"}

        issues = []

        # Check recertification (annual requirement)
        last_recert = datetime.fromisoformat(entity.last_recertification.replace("Z", ""))
        days_since_recert = (datetime.utcnow() - last_recert).days
        if days_since_recert > 365:
            issues.append(f"Recertification overdue by {days_since_recert - 365} days")

        # Check DSH percentage for DSH hospitals
        if entity.entity_type == EntityType.DSH:
            if entity.dsh_pct is not None and entity.dsh_pct < 11.75:
                issues.append(
                    f"DSH adjustment % ({entity.dsh_pct}%) below 11.75% threshold"
                )

        # Check contract pharmacy requirements
        if len(entity.contract_pharmacies) > 0:
            # Entities with >1 contract pharmacy need enhanced reporting
            if len(entity.contract_pharmacies) > 5:
                issues.append(
                    f"High contract pharmacy count ({len(entity.contract_pharmacies)}) "
                    "— enhanced monitoring required"
                )

        return {
            "entity_id": entity_id,
            "name": entity.name,
            "eligible": len(issues) == 0,
            "issues": issues,
            "days_since_recertification": days_since_recert,
            "entity_type": entity.entity_type.value,
        }

    def quantify_savings(
        self,
        entity_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Quantify 340B savings for an entity over a period."""
        indices = self.claim_index_by_entity.get(entity_id, [])
        claims = [self.claims[i] for i in indices]

        if period_start:
            start_str = period_start.isoformat()
            claims = [c for c in claims if c.claim_date >= start_str]
        if period_end:
            end_str = period_end.isoformat()
            claims = [c for c in claims if c.claim_date <= end_str]

        total_savings = 0.0
        savings_by_drug = defaultdict(float)
        savings_by_payer = defaultdict(float)
        claim_count_340b = 0

        for claim in claims:
            if claim.is_340b_dispensed:
                claim_count_340b += 1
                drug = self.drug_catalog.get(claim.ndc)
                if drug:
                    unit_savings = drug.wac - claim.actual_acquisition_cost
                    claim_savings = unit_savings * claim.quantity
                    total_savings += claim_savings
                    savings_by_drug[claim.drug_name] += claim_savings
                    savings_by_payer[claim.payer_type] += claim_savings

        # Top drugs by savings
        top_drugs = sorted(savings_by_drug.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "entity_id": entity_id,
            "total_claims": len(claims),
            "claims_340b": claim_count_340b,
            "utilization_rate": (claim_count_340b / len(claims) * 100) if claims else 0,
            "total_savings": round(total_savings, 2),
            "average_savings_per_claim": round(total_savings / claim_count_340b, 2) if claim_count_340b else 0,
            "savings_by_payer": {k: round(v, 2) for k, v in savings_by_payer.items()},
            "top_drugs_by_savings": [
                {"drug": name, "savings": round(s, 2)} for name, s in top_drugs
            ],
        }

    def generate_compliance_report(
        self,
        entity_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> ComplianceReport:
        """Generate a comprehensive 340B compliance report."""
        entity = self.entities.get(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        indices = self.claim_index_by_entity.get(entity_id, [])
        start_str = period_start.isoformat()
        end_str = period_end.isoformat()
        period_claims = [
            self.claims[i] for i in indices
            if start_str <= self.claims[i].claim_date <= end_str
        ]

        # Count eligible and flagged
        eligible = sum(1 for c in period_claims if c.is_340b_eligible)
        entity_alerts = [
            a for a in self.alerts
            if a.entity_id == entity_id
            and not a.resolved
        ]

        duplicate_alerts = sum(
            1 for a in entity_alerts
            if a.violation_type == "duplicate_discount_340b_medicaid"
        )
        ceiling_violations = sum(
            1 for a in entity_alerts
            if a.violation_type == "ceiling_price_exceeded"
        )

        # Savings
        savings_data = self.quantify_savings(entity_id, period_start, period_end)
        total_savings = savings_data["total_savings"]

        # Savings at risk (from alerts)
        savings_at_risk = sum(a.estimated_overpayment for a in entity_alerts)

        # Audit readiness score
        readiness = self._calculate_audit_readiness(
            entity, len(period_claims), eligible, len(entity_alerts),
            duplicate_alerts, ceiling_violations,
        )

        # Determine overall status
        if duplicate_alerts > 0 or ceiling_violations > 2:
            overall_status = ComplianceStatus.VIOLATION
            audit_risk = AuditRisk.CRITICAL
        elif ceiling_violations > 0 or len(entity_alerts) > 5:
            overall_status = ComplianceStatus.WARNING
            audit_risk = AuditRisk.HIGH
        elif len(entity_alerts) > 0:
            overall_status = ComplianceStatus.UNDER_REVIEW
            audit_risk = AuditRisk.MODERATE
        else:
            overall_status = ComplianceStatus.COMPLIANT
            audit_risk = AuditRisk.LOW

        # Recommendations
        recommendations = []
        if duplicate_alerts > 0:
            recommendations.append(
                "URGENT: Review and resolve all duplicate discount alerts immediately. "
                "Consider switching to carve-out model for Medicaid claims."
            )
        if ceiling_violations > 0:
            recommendations.append(
                "Verify ceiling prices with manufacturers. File ceiling price "
                "complaints with HRSA for confirmed overcharges."
            )
        if entity.billing_model == BillingModel.CARVE_IN and duplicate_alerts > 0:
            recommendations.append(
                "Strong recommendation to switch from carve-in to carve-out "
                "billing model to prevent future duplicate discount violations."
            )
        eligibility = self.check_entity_eligibility(entity_id)
        if not eligibility["eligible"]:
            recommendations.append(
                f"Eligibility issues detected: {'; '.join(eligibility['issues'])}"
            )
        if not recommendations:
            recommendations.append(
                "Entity is in good compliance standing. Continue current practices "
                "and maintain documentation for annual HRSA audit."
            )

        # Findings
        findings = []
        if entity_alerts:
            by_type = defaultdict(int)
            for a in entity_alerts:
                by_type[a.violation_type] += 1
            for vtype, count in by_type.items():
                findings.append({
                    "type": vtype,
                    "count": count,
                    "severity": "critical" if "duplicate" in vtype else "high",
                })

        return ComplianceReport(
            report_id=str(uuid.uuid4()),
            entity_id=entity_id,
            entity_name=entity.name,
            period_start=start_str,
            period_end=end_str,
            overall_status=overall_status,
            audit_risk=audit_risk,
            audit_readiness_score=readiness,
            total_claims=len(period_claims),
            eligible_claims=eligible,
            flagged_claims=len(entity_alerts),
            duplicate_discount_alerts=duplicate_alerts,
            ceiling_price_violations=ceiling_violations,
            total_savings=total_savings,
            savings_at_risk=savings_at_risk,
            recommendations=recommendations,
            findings=findings,
        )

    def _calculate_audit_readiness(
        self,
        entity: CoveredEntity,
        total_claims: int,
        eligible_claims: int,
        total_alerts: int,
        duplicate_alerts: int,
        ceiling_violations: int,
    ) -> float:
        """Calculate an audit readiness score (0-100)."""
        score = 100.0

        # Deductions for violations
        score -= duplicate_alerts * 20   # Major violation
        score -= ceiling_violations * 10  # Significant
        score -= total_alerts * 2        # Each alert costs 2 points

        # Bonus for high eligibility rate
        if total_claims > 0:
            elig_rate = eligible_claims / total_claims
            if elig_rate >= 0.95:
                score += 5

        # Deduction for overdue recertification
        last_recert = datetime.fromisoformat(entity.last_recertification.replace("Z", ""))
        days_overdue = max(0, (datetime.utcnow() - last_recert).days - 365)
        score -= min(20, days_overdue * 0.1)

        # Contract pharmacy complexity penalty
        if len(entity.contract_pharmacies) > 10:
            score -= 5

        return max(0.0, min(100.0, round(score, 1)))

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall 340B program statistics."""
        total_savings = 0
        for entity_id in self.entities:
            savings = self.quantify_savings(entity_id)
            total_savings += savings["total_savings"]

        return {
            "registered_entities": len(self.entities),
            "drugs_in_catalog": len(self.drug_catalog),
            "total_claims_processed": len(self.claims),
            "total_alerts": len(self.alerts),
            "unresolved_alerts": sum(1 for a in self.alerts if not a.resolved),
            "critical_alerts": sum(1 for a in self.alerts if a.severity == AuditRisk.CRITICAL),
            "total_program_savings": round(total_savings, 2),
            "entity_types": dict(defaultdict(int, {
                e.entity_type.value: 1 for e in self.entities.values()
            })),
        }


if __name__ == "__main__":
    monitor = Program340BCompliance()

    # Register an entity
    entity = monitor.register_entity(
        hrsa_id="340B-12345",
        name="Community Memorial Hospital",
        entity_type=EntityType.DSH,
        address="100 Medical Pkwy, Lexington, KY 40506",
        state="KY",
        billing_model=BillingModel.CARVE_OUT,
        dsh_pct=15.2,
        contract_pharmacies=["pharmacy_001", "pharmacy_002"],
        npi="1234567890",
    )

    # Add drugs to catalog
    monitor.add_drug(
        ndc="0069-3150-83",
        drug_name="Lipitor 40mg",
        manufacturer="Pfizer",
        is_innovator=True,
        amp=4.50,
        wac=7.25,
        actual_340b_price=3.44,
    )

    monitor.add_drug(
        ndc="0378-1805-01",
        drug_name="Metformin 500mg",
        manufacturer="Mylan",
        is_innovator=False,
        amp=0.12,
        wac=0.45,
        actual_340b_price=0.10,
    )

    # Submit claims
    claim1 = ClaimRecord340B(
        claim_id="CLM001",
        entity_id=entity.entity_id,
        ndc="0069-3150-83",
        drug_name="Lipitor 40mg",
        quantity=90,
        claim_date=datetime.utcnow().isoformat(),
        payer_type="commercial",
        is_340b_eligible=True,
        is_340b_dispensed=True,
        billed_amount=652.50,
        paid_amount=550.00,
        ceiling_price_unit=3.44,
        actual_acquisition_cost=3.44,
        has_medicaid_rebate=False,
        has_manufacturer_rebate=False,
        contract_pharmacy_id=None,
        patient_id="PAT001",
    )

    alerts = monitor.submit_claim(claim1)
    print(f"Claim 1 alerts: {len(alerts)}")

    # Submit a problematic claim (duplicate discount)
    claim2 = ClaimRecord340B(
        claim_id="CLM002",
        entity_id=entity.entity_id,
        ndc="0378-1805-01",
        drug_name="Metformin 500mg",
        quantity=180,
        claim_date=datetime.utcnow().isoformat(),
        payer_type="medicaid",
        is_340b_eligible=True,
        is_340b_dispensed=True,
        billed_amount=81.00,
        paid_amount=65.00,
        ceiling_price_unit=0.10,
        actual_acquisition_cost=0.10,
        has_medicaid_rebate=True,  # This is a violation!
        has_manufacturer_rebate=False,
        contract_pharmacy_id="pharmacy_001",
        patient_id="PAT002",
    )

    alerts2 = monitor.submit_claim(claim2)
    print(f"Claim 2 alerts: {len(alerts2)}")
    for a in alerts2:
        print(f"  ⚠️ {a.violation_type}: {a.description}")

    # Generate compliance report
    report = monitor.generate_compliance_report(
        entity.entity_id,
        datetime.utcnow() - timedelta(days=90),
        datetime.utcnow(),
    )
    print(f"\nCompliance Report:")
    print(f"  Status: {report.overall_status.value}")
    print(f"  Audit Risk: {report.audit_risk.value}")
    print(f"  Readiness Score: {report.audit_readiness_score}/100")
    print(f"  Total Savings: ${report.total_savings:,.2f}")
    print(f"  Savings at Risk: ${report.savings_at_risk:,.2f}")

    # Stats
    stats = monitor.get_statistics()
    print(f"\nProgram stats: {json.dumps(stats, indent=2)}")
