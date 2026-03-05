"""
PBM Contract Rate Validation Engine
======================================
Validates actual claim reimbursements against contracted PBM rates,
detects underpayments, tracks rate compliance, and generates
dispute-ready reports for contract enforcement.

Features:
- Multi-tier contract rate modeling (brand, generic, specialty)
- Real-time claim-by-claim rate validation
- MAC list pricing verification against contract terms
- Dispensing fee compliance checking
- Effective rate analysis (ingredient cost + fees - DIR)
- Underpayment quantification and trending
- Dispute package generation with supporting evidence
- Contract term expiration tracking and renewal alerts

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import math
import hashlib
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class DrugType(Enum):
    GENERIC = "generic"
    BRAND = "brand"
    SPECIALTY = "specialty"
    OTC = "otc"
    COMPOUND = "compound"


class PricingBenchmark(Enum):
    AWP = "awp"                 # Average Wholesale Price
    WAC = "wac"                 # Wholesale Acquisition Cost
    NADAC = "nadac"             # National Average Drug Acquisition Cost
    MAC = "mac"                 # Maximum Allowable Cost
    ASP = "asp"                 # Average Sales Price
    FUL = "ful"                 # Federal Upper Limit


class DiscrepancyType(Enum):
    INGREDIENT_UNDERPAYMENT = "ingredient_underpayment"
    DISPENSING_FEE_SHORTAGE = "dispensing_fee_shortage"
    MAC_OVERRIDE_DENIED = "mac_override_denied"
    WRONG_BENCHMARK = "wrong_benchmark"
    EFFECTIVE_RATE_BELOW_COST = "effective_rate_below_cost"
    DIR_FEE_EXCESS = "dir_fee_excess"
    COPAY_CLAWBACK = "copay_clawback"
    RATE_NOT_IN_CONTRACT = "rate_not_in_contract"


class DiscrepancySeverity(Enum):
    CRITICAL = "critical"       # > $50 per claim or systematic
    HIGH = "high"               # $20-50 per claim
    MEDIUM = "medium"           # $5-20 per claim
    LOW = "low"                 # < $5 per claim
    INFO = "info"               # Technical deviation, no financial impact


@dataclass
class ContractRate:
    """A specific rate tier within a PBM contract."""
    rate_id: str
    drug_type: DrugType
    benchmark: PricingBenchmark
    discount_pct: float                  # Discount from benchmark (e.g., AWP - 15%)
    dispensing_fee: float                # Per-claim dispensing fee
    effective_date: str
    expiration_date: str
    minimum_reimbursement: float = 0.0   # Floor reimbursement per claim
    mac_override_policy: str = "appeal"  # appeal, automatic, denied
    specialty_threshold: float = 0.0     # Cost threshold for specialty tier
    day_supply_adjustments: Dict[str, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class PBMContract:
    """Full PBM contract with all rate tiers."""
    contract_id: str
    pbm_name: str
    effective_date: str
    expiration_date: str
    rates: List[ContractRate] = field(default_factory=list)
    dir_fee_terms: Dict = field(default_factory=dict)
    performance_metrics: Dict = field(default_factory=dict)
    auto_renewal: bool = False
    renewal_notice_days: int = 90
    dispute_window_days: int = 120       # Days to file rate disputes
    annual_reconciliation: bool = True
    network: str = "preferred"            # preferred, standard, specialty
    contact_email: str = ""
    contact_phone: str = ""

    def get_rate(self, drug_type: DrugType) -> Optional[ContractRate]:
        for rate in self.rates:
            if rate.drug_type == drug_type:
                return rate
        return None

    def is_active(self) -> bool:
        today = date.today().isoformat()
        return self.effective_date <= today <= self.expiration_date

    def days_until_expiration(self) -> int:
        exp = date.fromisoformat(self.expiration_date)
        return (exp - date.today()).days


@dataclass
class ClaimForValidation:
    """A single claim to validate against contract rates."""
    claim_id: str
    ndc: str
    drug_name: str
    drug_type: DrugType
    quantity: float
    days_supply: int
    date_of_service: str
    pbm_id: str
    benchmark_price: float               # AWP, WAC, etc. for this NDC
    actual_reimbursement: float          # What the PBM actually paid
    ingredient_cost_paid: float          # Ingredient cost component
    dispensing_fee_paid: float           # Dispensing fee component
    patient_copay: float = 0.0
    acquisition_cost: float = 0.0       # Pharmacy's actual acquisition cost
    nadac_price: float = 0.0
    is_mac_priced: bool = False
    mac_price: float = 0.0
    dir_fee_allocated: float = 0.0      # Allocated DIR fee per claim


@dataclass
class RateDiscrepancy:
    """A detected discrepancy between contracted and actual rates."""
    discrepancy_id: str
    claim_id: str
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    contracted_amount: float
    actual_amount: float
    difference: float
    pct_difference: float
    description: str
    contract_reference: str              # Specific contract clause
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    dispute_filed: bool = False
    dispute_status: str = ""
    resolution_amount: float = 0.0


class RateCalculator:
    """Calculates expected reimbursement based on contract terms."""

    def calculate_expected(self, claim: ClaimForValidation, rate: ContractRate) -> Dict:
        """Calculate the expected reimbursement for a claim under contract terms."""
        # Calculate ingredient cost based on benchmark
        benchmark_total = claim.benchmark_price * claim.quantity
        discount_amount = benchmark_total * (rate.discount_pct / 100)
        expected_ingredient = benchmark_total - discount_amount

        # Dispensing fee
        expected_fee = rate.dispensing_fee

        # Day supply adjustments
        ds_key = str(claim.days_supply)
        if ds_key in rate.day_supply_adjustments:
            expected_fee *= rate.day_supply_adjustments[ds_key]

        # Total expected
        expected_total = expected_ingredient + expected_fee

        # Apply minimum reimbursement floor
        if rate.minimum_reimbursement > 0:
            expected_total = max(expected_total, rate.minimum_reimbursement)

        # MAC pricing check
        if claim.is_mac_priced and claim.mac_price > 0:
            mac_total = claim.mac_price * claim.quantity + expected_fee
            if mac_total < expected_total and rate.mac_override_policy != "automatic":
                expected_total = mac_total

        return {
            "expected_ingredient": round(expected_ingredient, 2),
            "expected_fee": round(expected_fee, 2),
            "expected_total": round(expected_total, 2),
            "benchmark_used": rate.benchmark.value,
            "discount_applied": rate.discount_pct,
            "benchmark_total": round(benchmark_total, 2)
        }

    def calculate_effective_rate(self, claim: ClaimForValidation) -> Dict:
        """Calculate effective reimbursement rate accounting for DIR fees."""
        gross = claim.actual_reimbursement
        net = gross - claim.dir_fee_allocated
        effective_rate_pct = (net / (claim.benchmark_price * claim.quantity) * 100) if claim.benchmark_price > 0 else 0

        margin = net - claim.acquisition_cost if claim.acquisition_cost > 0 else None
        margin_pct = (margin / claim.acquisition_cost * 100) if margin is not None and claim.acquisition_cost > 0 else None

        return {
            "gross_reimbursement": round(gross, 2),
            "dir_fee_allocated": round(claim.dir_fee_allocated, 2),
            "net_reimbursement": round(net, 2),
            "effective_rate_pct": round(effective_rate_pct, 2),
            "acquisition_cost": round(claim.acquisition_cost, 2) if claim.acquisition_cost else None,
            "margin": round(margin, 2) if margin is not None else None,
            "margin_pct": round(margin_pct, 2) if margin_pct is not None else None,
            "is_underwater": margin is not None and margin < 0
        }


class ClaimValidator:
    """Validates individual claims against contract terms."""

    def __init__(self):
        self.calculator = RateCalculator()
        self._disc_counter = 0

    def validate_claim(self, claim: ClaimForValidation, contract: PBMContract) -> List[RateDiscrepancy]:
        """Validate a single claim against its contract and return any discrepancies."""
        discrepancies = []
        rate = contract.get_rate(claim.drug_type)

        if not rate:
            self._disc_counter += 1
            discrepancies.append(RateDiscrepancy(
                discrepancy_id=f"DISC-{self._disc_counter:08d}",
                claim_id=claim.claim_id,
                discrepancy_type=DiscrepancyType.RATE_NOT_IN_CONTRACT,
                severity=DiscrepancySeverity.HIGH,
                contracted_amount=0,
                actual_amount=claim.actual_reimbursement,
                difference=0,
                pct_difference=0,
                description=f"No contract rate found for drug type: {claim.drug_type.value}",
                contract_reference=f"Contract {contract.contract_id}"
            ))
            return discrepancies

        expected = self.calculator.calculate_expected(claim, rate)

        # Check ingredient cost
        ingredient_diff = expected["expected_ingredient"] - claim.ingredient_cost_paid
        if abs(ingredient_diff) > 0.50:  # $0.50 tolerance
            self._disc_counter += 1
            severity = self._classify_severity(abs(ingredient_diff))
            discrepancies.append(RateDiscrepancy(
                discrepancy_id=f"DISC-{self._disc_counter:08d}",
                claim_id=claim.claim_id,
                discrepancy_type=DiscrepancyType.INGREDIENT_UNDERPAYMENT,
                severity=severity,
                contracted_amount=expected["expected_ingredient"],
                actual_amount=claim.ingredient_cost_paid,
                difference=round(ingredient_diff, 2),
                pct_difference=round(ingredient_diff / expected["expected_ingredient"] * 100, 2) if expected["expected_ingredient"] > 0 else 0,
                description=f"Ingredient cost underpaid by ${abs(ingredient_diff):.2f} "
                            f"({expected['benchmark_used']} - {rate.discount_pct}%)",
                contract_reference=f"Rate ID: {rate.rate_id}, Benchmark: {rate.benchmark.value} - {rate.discount_pct}%"
            ))

        # Check dispensing fee
        fee_diff = expected["expected_fee"] - claim.dispensing_fee_paid
        if abs(fee_diff) > 0.25:  # $0.25 tolerance
            self._disc_counter += 1
            discrepancies.append(RateDiscrepancy(
                discrepancy_id=f"DISC-{self._disc_counter:08d}",
                claim_id=claim.claim_id,
                discrepancy_type=DiscrepancyType.DISPENSING_FEE_SHORTAGE,
                severity=self._classify_severity(abs(fee_diff)),
                contracted_amount=expected["expected_fee"],
                actual_amount=claim.dispensing_fee_paid,
                difference=round(fee_diff, 2),
                pct_difference=round(fee_diff / expected["expected_fee"] * 100, 2) if expected["expected_fee"] > 0 else 0,
                description=f"Dispensing fee underpaid by ${abs(fee_diff):.2f} "
                            f"(contracted: ${expected['expected_fee']:.2f})",
                contract_reference=f"Rate ID: {rate.rate_id}, Fee: ${rate.dispensing_fee:.2f}"
            ))

        # Check effective rate after DIR
        eff_rate = self.calculator.calculate_effective_rate(claim)
        if eff_rate["is_underwater"]:
            self._disc_counter += 1
            discrepancies.append(RateDiscrepancy(
                discrepancy_id=f"DISC-{self._disc_counter:08d}",
                claim_id=claim.claim_id,
                discrepancy_type=DiscrepancyType.EFFECTIVE_RATE_BELOW_COST,
                severity=DiscrepancySeverity.CRITICAL,
                contracted_amount=claim.acquisition_cost,
                actual_amount=eff_rate["net_reimbursement"],
                difference=round(eff_rate["margin"], 2),
                pct_difference=round(eff_rate["margin_pct"], 2),
                description=f"Effective reimbursement (${eff_rate['net_reimbursement']:.2f}) "
                            f"is below acquisition cost (${claim.acquisition_cost:.2f}) "
                            f"after DIR fee allocation",
                contract_reference=f"Contract {contract.contract_id}, DIR terms"
            ))

        # Check MAC override denials
        if claim.is_mac_priced and rate.mac_override_policy == "denied":
            mac_reimb = claim.mac_price * claim.quantity
            if mac_reimb < claim.acquisition_cost:
                self._disc_counter += 1
                discrepancies.append(RateDiscrepancy(
                    discrepancy_id=f"DISC-{self._disc_counter:08d}",
                    claim_id=claim.claim_id,
                    discrepancy_type=DiscrepancyType.MAC_OVERRIDE_DENIED,
                    severity=DiscrepancySeverity.HIGH,
                    contracted_amount=claim.acquisition_cost,
                    actual_amount=mac_reimb,
                    difference=round(claim.acquisition_cost - mac_reimb, 2),
                    pct_difference=round((claim.acquisition_cost - mac_reimb) / claim.acquisition_cost * 100, 2),
                    description=f"MAC price below acquisition cost; override policy: denied",
                    contract_reference=f"Rate ID: {rate.rate_id}, MAC Override: {rate.mac_override_policy}"
                ))

        return discrepancies

    def _classify_severity(self, amount: float) -> DiscrepancySeverity:
        if amount >= 50:
            return DiscrepancySeverity.CRITICAL
        elif amount >= 20:
            return DiscrepancySeverity.HIGH
        elif amount >= 5:
            return DiscrepancySeverity.MEDIUM
        elif amount >= 1:
            return DiscrepancySeverity.LOW
        else:
            return DiscrepancySeverity.INFO


class DisputePackageGenerator:
    """Generates dispute-ready documentation packages."""

    def generate_package(self, discrepancies: List[RateDiscrepancy],
                         contract: PBMContract, claims: List[ClaimForValidation]) -> Dict:
        """Generate a dispute package for a set of discrepancies."""
        # Group by type
        by_type = defaultdict(list)
        for d in discrepancies:
            by_type[d.discrepancy_type.value].append(d)

        total_owed = sum(abs(d.difference) for d in discrepancies if d.difference > 0)

        # Build claim evidence
        claim_lookup = {c.claim_id: c for c in claims}
        evidence_items = []

        for d in discrepancies[:50]:  # Cap at 50 items for readability
            claim = claim_lookup.get(d.claim_id)
            evidence_items.append({
                "claim_id": d.claim_id,
                "drug_name": claim.drug_name if claim else "Unknown",
                "ndc": claim.ndc if claim else "Unknown",
                "date_of_service": claim.date_of_service if claim else "",
                "discrepancy_type": d.discrepancy_type.value,
                "contracted_amount": d.contracted_amount,
                "actual_amount": d.actual_amount,
                "difference": d.difference,
                "contract_reference": d.contract_reference
            })

        package = {
            "dispute_id": hashlib.md5(datetime.utcnow().isoformat().encode()).hexdigest()[:12],
            "generated_at": datetime.utcnow().isoformat(),
            "pbm_name": contract.pbm_name,
            "contract_id": contract.contract_id,
            "contract_effective": contract.effective_date,
            "contract_expiration": contract.expiration_date,
            "dispute_deadline": (
                date.today() + timedelta(days=contract.dispute_window_days)
            ).isoformat(),
            "summary": {
                "total_discrepancies": len(discrepancies),
                "total_amount_owed": round(total_owed, 2),
                "by_type": {
                    dtype: {
                        "count": len(items),
                        "total_amount": round(sum(abs(d.difference) for d in items), 2)
                    }
                    for dtype, items in by_type.items()
                },
                "by_severity": {
                    sev.value: len([d for d in discrepancies if d.severity == sev])
                    for sev in DiscrepancySeverity
                }
            },
            "evidence": evidence_items,
            "contract_terms_referenced": list(set(d.contract_reference for d in discrepancies)),
            "recommended_actions": self._generate_recommendations(by_type, total_owed),
            "contact": {
                "email": contract.contact_email,
                "phone": contract.contact_phone
            }
        }

        return package

    def _generate_recommendations(self, by_type: Dict, total_owed: float) -> List[str]:
        recs = []

        if DiscrepancyType.INGREDIENT_UNDERPAYMENT.value in by_type:
            count = len(by_type[DiscrepancyType.INGREDIENT_UNDERPAYMENT.value])
            recs.append(f"File ingredient cost dispute for {count} claims with benchmark pricing evidence")

        if DiscrepancyType.DISPENSING_FEE_SHORTAGE.value in by_type:
            recs.append("Request dispensing fee reconciliation per contract terms")

        if DiscrepancyType.EFFECTIVE_RATE_BELOW_COST.value in by_type:
            count = len(by_type[DiscrepancyType.EFFECTIVE_RATE_BELOW_COST.value])
            recs.append(f"URGENT: {count} claims reimbursed below acquisition cost. "
                       "Escalate to contract negotiation team")

        if DiscrepancyType.MAC_OVERRIDE_DENIED.value in by_type:
            recs.append("Submit MAC appeals with current acquisition cost documentation")

        if total_owed > 10000:
            recs.append(f"High-value dispute (${total_owed:,.2f}). Consider legal review before filing")

        recs.append("Include NADAC pricing data as independent verification of acquisition costs")

        return recs


class ContractComplianceTracker:
    """Tracks contract rate compliance over time."""

    def __init__(self):
        self.validation_history: List[Dict] = []

    def record_validation(self, contract_id: str, total_claims: int,
                          discrepancies: List[RateDiscrepancy]):
        self.validation_history.append({
            "contract_id": contract_id,
            "total_claims": total_claims,
            "total_discrepancies": len(discrepancies),
            "total_amount": round(sum(abs(d.difference) for d in discrepancies), 2),
            "compliance_rate": round(
                (total_claims - len(discrepancies)) / total_claims * 100, 2
            ) if total_claims > 0 else 100,
            "by_type": dict(defaultdict(int, {
                d.discrepancy_type.value: 1 for d in discrepancies
            })),
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_compliance_trend(self, contract_id: str, periods: int = 12) -> Dict:
        records = [r for r in self.validation_history if r["contract_id"] == contract_id]
        recent = records[-periods:] if len(records) > periods else records

        if not recent:
            return {"contract_id": contract_id, "message": "No validation history"}

        return {
            "contract_id": contract_id,
            "periods_analyzed": len(recent),
            "avg_compliance_rate": round(
                sum(r["compliance_rate"] for r in recent) / len(recent), 2
            ),
            "total_amount_disputed": round(sum(r["total_amount"] for r in recent), 2),
            "trend": "improving" if len(recent) >= 2 and recent[-1]["compliance_rate"] > recent[0]["compliance_rate"] else "declining",
            "history": recent
        }


class ContractRateValidator:
    """
    Main orchestrator for PBM contract rate validation.
    
    Usage:
        validator = ContractRateValidator()
        validator.add_contract(contract)
        
        results = validator.validate_claims(claims, "contract_123")
        dispute = validator.generate_dispute_package("contract_123")
    """

    def __init__(self):
        self.contracts: Dict[str, PBMContract] = {}
        self.claim_validator = ClaimValidator()
        self.dispute_generator = DisputePackageGenerator()
        self.compliance_tracker = ContractComplianceTracker()
        self.all_discrepancies: List[RateDiscrepancy] = []
        self.validated_claims: List[ClaimForValidation] = []

    def add_contract(self, contract: PBMContract):
        self.contracts[contract.contract_id] = contract

    def validate_claims(self, claims: List[ClaimForValidation], contract_id: str) -> Dict:
        contract = self.contracts.get(contract_id)
        if not contract:
            return {"error": f"Contract {contract_id} not found"}

        if not contract.is_active():
            return {"warning": "Contract is not currently active", "contract_id": contract_id}

        discrepancies = []
        for claim in claims:
            found = self.claim_validator.validate_claim(claim, contract)
            discrepancies.extend(found)

        self.all_discrepancies.extend(discrepancies)
        self.validated_claims.extend(claims)
        self.compliance_tracker.record_validation(contract_id, len(claims), discrepancies)

        # Summary
        total_reimbursed = sum(c.actual_reimbursement for c in claims)
        total_underpaid = sum(abs(d.difference) for d in discrepancies if d.difference > 0)

        return {
            "contract_id": contract_id,
            "pbm_name": contract.pbm_name,
            "claims_validated": len(claims),
            "total_reimbursed": round(total_reimbursed, 2),
            "discrepancies_found": len(discrepancies),
            "total_underpaid": round(total_underpaid, 2),
            "compliance_rate": round(
                (len(claims) - len(discrepancies)) / len(claims) * 100, 2
            ) if claims else 100,
            "by_severity": {
                sev.value: len([d for d in discrepancies if d.severity == sev])
                for sev in DiscrepancySeverity if any(d.severity == sev for d in discrepancies)
            },
            "by_type": {
                dtype.value: {
                    "count": len([d for d in discrepancies if d.discrepancy_type == dtype]),
                    "total": round(sum(abs(d.difference) for d in discrepancies if d.discrepancy_type == dtype), 2)
                }
                for dtype in DiscrepancyType if any(d.discrepancy_type == dtype for d in discrepancies)
            },
            "validated_at": datetime.utcnow().isoformat()
        }

    def generate_dispute_package(self, contract_id: str) -> Dict:
        contract = self.contracts.get(contract_id)
        if not contract:
            return {"error": "Contract not found"}

        relevant = [d for d in self.all_discrepancies
                    if d.contract_reference and contract_id in d.contract_reference
                    or any(r.rate_id in d.contract_reference for r in contract.rates)]

        return self.dispute_generator.generate_package(
            relevant, contract, self.validated_claims
        )

    def get_contract_health(self, contract_id: str) -> Dict:
        contract = self.contracts.get(contract_id)
        if not contract:
            return {"error": "Contract not found"}

        compliance = self.compliance_tracker.get_compliance_trend(contract_id)
        days_left = contract.days_until_expiration()

        return {
            "contract_id": contract_id,
            "pbm_name": contract.pbm_name,
            "status": "active" if contract.is_active() else "expired",
            "days_until_expiration": days_left,
            "renewal_alert": days_left <= contract.renewal_notice_days,
            "compliance_trend": compliance,
            "total_discrepancies": len(self.all_discrepancies),
            "total_underpaid": round(
                sum(abs(d.difference) for d in self.all_discrepancies if d.difference > 0), 2
            ),
            "network": contract.network,
            "auto_renewal": contract.auto_renewal,
            "assessed_at": datetime.utcnow().isoformat()
        }


# FastAPI Integration
try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1/contract-validation", tags=["Contract Validation"])
    validator = ContractRateValidator()

    class ContractInput(BaseModel):
        contract_id: str
        pbm_name: str
        effective_date: str
        expiration_date: str
        network: str = "preferred"

    @router.post("/contracts")
    async def add_contract(req: ContractInput):
        contract = PBMContract(
            contract_id=req.contract_id,
            pbm_name=req.pbm_name,
            effective_date=req.effective_date,
            expiration_date=req.expiration_date,
            network=req.network
        )
        validator.add_contract(contract)
        return {"status": "added", "contract_id": req.contract_id}

    @router.get("/contracts/{contract_id}/health")
    async def contract_health(contract_id: str):
        result = validator.get_contract_health(contract_id)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result

    @router.get("/contracts/{contract_id}/dispute")
    async def dispute_package(contract_id: str):
        return validator.generate_dispute_package(contract_id)

except ImportError:
    router = None
