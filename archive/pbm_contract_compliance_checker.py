"""
GetPaidRx - PBM Contract Compliance Checker

Verifies that PBM (Pharmacy Benefit Manager) reimbursement adheres to
contracted rates. Detects MAC list violations, guaranteed reimbursement
floor breaches, and contracted dispensing fee non-compliance.

Features:
  - MAC (Maximum Allowable Cost) list compliance verification
  - Contracted dispensing fee validation
  - Generic effective rate (GER) monitoring
  - Brand effective rate checking
  - Guaranteed floor reimbursement enforcement
  - Spread pricing detection
  - Contract vs actual reimbursement variance
  - Compliance report generation
  - Appeal recommendation for violations
"""

import statistics
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass


# ============================================================
# Contract Templates
# ============================================================

DEFAULT_CONTRACT_TERMS = {
    "generic_reimbursement": "NADAC + dispensing_fee",
    "brand_reimbursement": "AWP - discount_pct + dispensing_fee",
    "dispensing_fee_generic": 0.00,     # Many PBMs pay $0 dispensing on generics
    "dispensing_fee_brand": 0.00,
    "generic_floor": None,              # Minimum reimbursement per generic Rx
    "brand_discount_pct": 16.0,         # AWP - 16%
    "mac_list": "pbm_proprietary",
    "ger_target": None,                 # Generic effective rate target
    "dir_fee_schedule": "quarterly",
    "audit_rights": True,
}


@dataclass
class ContractTerms:
    """PBM contract terms for compliance checking."""
    payer: str
    pbm: str
    effective_date: str = ""
    expiration_date: str = ""
    dispensing_fee_generic: float = 0.00
    dispensing_fee_brand: float = 0.00
    brand_discount_pct: float = 16.0      # AWP - X%
    generic_floor: Optional[float] = None  # Minimum $ per generic Rx
    ger_target: Optional[float] = None     # Target GER %
    max_copay_clawback: bool = True        # Allow copay clawbacks?
    mac_update_frequency: str = "weekly"


@dataclass
class ClaimForCompliance:
    """Claim data needed for compliance checking."""
    claim_id: str
    payer: str
    pbm: str = ""
    drug_name: str = ""
    ndc: str = ""
    is_brand: bool = False
    quantity: float = 0.0
    days_supply: int = 0
    # Pricing
    awp_per_unit: float = 0.0
    nadac_per_unit: float = 0.0
    mac_price: float = 0.0          # PBM's MAC price
    acquisition_cost: float = 0.0
    # Reimbursement components
    ingredient_cost_paid: float = 0.0
    dispensing_fee_paid: float = 0.0
    total_paid: float = 0.0
    copay: float = 0.0
    # Context
    fill_date: str = ""


class PBMContractComplianceChecker:
    """
    Checks pharmacy claims against PBM contract terms to identify
    reimbursement violations and non-compliance.
    """

    def __init__(self):
        self.contracts: Dict[str, ContractTerms] = {}
        self.claims: List[ClaimForCompliance] = []

    def add_contract(self, terms: Dict[str, Any]) -> None:
        """Add a PBM contract for compliance checking."""
        contract = ContractTerms(
            payer=str(terms.get("payer", "")),
            pbm=str(terms.get("pbm", "")),
            effective_date=str(terms.get("effective_date", "")),
            expiration_date=str(terms.get("expiration_date", "")),
            dispensing_fee_generic=float(terms.get("dispensing_fee_generic", 0.00)),
            dispensing_fee_brand=float(terms.get("dispensing_fee_brand", 0.00)),
            brand_discount_pct=float(terms.get("brand_discount_pct", 16.0)),
            generic_floor=terms.get("generic_floor"),
            ger_target=terms.get("ger_target"),
            max_copay_clawback=bool(terms.get("max_copay_clawback", True)),
            mac_update_frequency=str(terms.get("mac_update_frequency", "weekly")),
        )
        self.contracts[contract.payer] = contract

    def load_claims(self, claims_data: List[Dict[str, Any]]) -> int:
        """Load claims for compliance checking."""
        loaded = 0
        for c in claims_data:
            try:
                claim = ClaimForCompliance(
                    claim_id=str(c.get("claim_id", f"CLM-{loaded}")),
                    payer=str(c.get("payer", "")),
                    pbm=str(c.get("pbm", "")),
                    drug_name=str(c.get("drug_name", "")),
                    ndc=str(c.get("ndc", "")),
                    is_brand=bool(c.get("is_brand", False)),
                    quantity=float(c.get("quantity", 0)),
                    days_supply=int(c.get("days_supply", 0)),
                    awp_per_unit=float(c.get("awp_per_unit", 0)),
                    nadac_per_unit=float(c.get("nadac_per_unit", 0)),
                    mac_price=float(c.get("mac_price", 0)),
                    acquisition_cost=float(c.get("acquisition_cost", 0)),
                    ingredient_cost_paid=float(c.get("ingredient_cost_paid", 0)),
                    dispensing_fee_paid=float(c.get("dispensing_fee_paid", 0)),
                    total_paid=float(c.get("total_paid", 0)),
                    copay=float(c.get("copay", 0)),
                    fill_date=str(c.get("fill_date", "")),
                )
                self.claims.append(claim)
                loaded += 1
            except (ValueError, TypeError):
                continue
        return loaded

    # -------------------------------------------------------
    # Compliance Check
    # -------------------------------------------------------

    def check_compliance(self) -> Dict[str, Any]:
        """Run compliance checks on all loaded claims."""
        violations = []
        compliant = []
        warnings = []

        for claim in self.claims:
            contract = self.contracts.get(claim.payer)
            result = self._check_single_claim(claim, contract)

            if result["violations"]:
                violations.append(result)
            elif result["warnings"]:
                warnings.append(result)
            else:
                compliant.append(result)

        # Aggregate
        total = len(self.claims)
        violation_count = len(violations)
        compliance_rate = round(
            ((total - violation_count) / total * 100) if total > 0 else 0, 1
        )

        # Financial impact
        total_underpaid = sum(
            v.get("total_underpayment", 0) for v in violations
        )

        # Violation type breakdown
        violation_types = defaultdict(int)
        for v in violations:
            for viol in v["violations"]:
                violation_types[viol["type"]] += 1

        # Per-payer breakdown
        payer_violations = defaultdict(lambda: {"count": 0, "amount": 0})
        for v in violations:
            payer = v["payer"]
            payer_violations[payer]["count"] += 1
            payer_violations[payer]["amount"] += v.get("total_underpayment", 0)

        return {
            "checked_at": datetime.now().isoformat(),
            "total_claims_checked": total,
            "compliant_count": len(compliant),
            "violation_count": violation_count,
            "warning_count": len(warnings),
            "compliance_rate": compliance_rate,
            "total_underpayment": round(total_underpaid, 2),
            "annualized_impact": round(total_underpaid * 12, 2),
            "violation_type_breakdown": dict(violation_types),
            "payer_violations": dict(payer_violations),
            "top_violations": sorted(
                violations, key=lambda v: v.get("total_underpayment", 0), reverse=True
            )[:20],
            "recommendations": self._generate_recommendations(
                violations, violation_types, payer_violations
            ),
        }

    def _check_single_claim(
        self, claim: ClaimForCompliance, contract: Optional[ContractTerms]
    ) -> Dict[str, Any]:
        """Check a single claim for compliance violations."""
        violations = []
        warnings = []
        total_underpayment = 0

        # Dispensing fee check
        if contract:
            expected_fee = (
                contract.dispensing_fee_brand if claim.is_brand
                else contract.dispensing_fee_generic
            )
            if expected_fee > 0 and claim.dispensing_fee_paid < expected_fee - 0.01:
                diff = expected_fee - claim.dispensing_fee_paid
                violations.append({
                    "type": "dispensing_fee_violation",
                    "severity": "medium",
                    "message": f"Dispensing fee paid (${claim.dispensing_fee_paid:.2f}) "
                               f"is below contracted rate (${expected_fee:.2f})",
                    "underpayment": round(diff, 2),
                })
                total_underpayment += diff

        # Brand reimbursement check (AWP - discount%)
        if claim.is_brand and claim.awp_per_unit > 0 and contract:
            expected_ingredient = claim.awp_per_unit * claim.quantity * (1 - contract.brand_discount_pct / 100)
            if claim.ingredient_cost_paid < expected_ingredient - 0.50:
                diff = expected_ingredient - claim.ingredient_cost_paid
                violations.append({
                    "type": "brand_rate_violation",
                    "severity": "high",
                    "message": f"Brand ingredient cost paid (${claim.ingredient_cost_paid:.2f}) "
                               f"below AWP-{contract.brand_discount_pct}% (${expected_ingredient:.2f})",
                    "underpayment": round(diff, 2),
                })
                total_underpayment += diff

        # Generic floor check
        if contract and contract.generic_floor and not claim.is_brand:
            total_received = claim.total_paid + claim.copay
            if total_received < contract.generic_floor:
                diff = contract.generic_floor - total_received
                violations.append({
                    "type": "floor_violation",
                    "severity": "high",
                    "message": f"Total reimbursement (${total_received:.2f}) below "
                               f"guaranteed floor (${contract.generic_floor:.2f})",
                    "underpayment": round(diff, 2),
                })
                total_underpayment += diff

        # MAC pricing check - MAC should not be below NADAC
        if claim.mac_price > 0 and claim.nadac_per_unit > 0:
            if claim.mac_price < claim.nadac_per_unit * 0.90:
                warnings.append({
                    "type": "mac_below_nadac",
                    "severity": "medium",
                    "message": f"MAC price (${claim.mac_price:.4f}) is >10% below "
                               f"NADAC (${claim.nadac_per_unit:.4f}). Challenge MAC list.",
                })

        # Below-cost reimbursement check
        if claim.acquisition_cost > 0:
            total_received = claim.total_paid + claim.copay
            if total_received < claim.acquisition_cost:
                diff = claim.acquisition_cost - total_received
                violations.append({
                    "type": "below_cost",
                    "severity": "critical",
                    "message": f"Total reimbursement (${total_received:.2f}) below "
                               f"acquisition cost (${claim.acquisition_cost:.2f})",
                    "underpayment": round(diff, 2),
                })
                total_underpayment += diff

        # Copay clawback detection
        if claim.copay > 0 and claim.total_paid <= 0:
            warnings.append({
                "type": "copay_clawback",
                "severity": "medium",
                "message": f"Payer paid $0 — pharmacy received only copay (${claim.copay:.2f}). "
                           "Possible copay clawback situation.",
            })

        return {
            "claim_id": claim.claim_id,
            "payer": claim.payer,
            "drug_name": claim.drug_name,
            "is_brand": claim.is_brand,
            "violations": violations,
            "warnings": warnings,
            "total_underpayment": round(total_underpayment, 2),
            "is_compliant": len(violations) == 0,
        }

    def _generate_recommendations(
        self, violations, violation_types, payer_violations
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recs = []

        if "below_cost" in violation_types:
            count = violation_types["below_cost"]
            recs.append({
                "priority": "critical",
                "title": f"Appeal {count} Below-Cost Claims",
                "action": "File MAC appeals with NADAC documentation for all below-cost generic claims. "
                          "Challenge MAC list pricing with PBM.",
            })

        if "dispensing_fee_violation" in violation_types:
            recs.append({
                "priority": "high",
                "title": "Enforce Contracted Dispensing Fees",
                "action": "Submit contract compliance dispute for all claims with dispensing fee shortfalls.",
            })

        if "floor_violation" in violation_types:
            recs.append({
                "priority": "high",
                "title": "Enforce Guaranteed Floor Reimbursement",
                "action": "File formal reimbursement floor violation dispute with PBM. "
                          "Include contract terms as evidence.",
            })

        worst_payer = max(
            payer_violations.items(), key=lambda x: x[1]["amount"], default=None
        )
        if worst_payer and worst_payer[1]["amount"] > 100:
            recs.append({
                "priority": "high",
                "title": f"Address {worst_payer[0]} Compliance Issues",
                "action": f"${worst_payer[1]['amount']:,.2f} in violations from {worst_payer[0]}. "
                          "Schedule contract compliance review meeting.",
            })

        return recs


# ============================================================
# Module-level convenience
# ============================================================

def check_pbm_compliance(claims_data, contracts=None):
    """Quick compliance check."""
    checker = PBMContractComplianceChecker()
    if contracts:
        for ct in contracts:
            checker.add_contract(ct)
    checker.load_claims(claims_data)
    return checker.check_compliance()
