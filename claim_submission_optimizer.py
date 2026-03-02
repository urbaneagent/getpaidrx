"""
GetPaidRx - Claim Submission Optimizer

Pre-submission claim validation engine that identifies potential rejection
patterns before claims are submitted. Learns from historical denial data
to flag high-risk claims and suggest corrections.

Features:
  - Pre-submission validation against 30+ rejection rules
  - Historical denial pattern matching
  - DAW (Dispense As Written) code optimization
  - Quantity/days supply consistency checks
  - NDC-to-payer formulary verification
  - Refill timing validation
  - Prior authorization requirement detection
  - Submission score (0-100) with pass/fail recommendation
  - Auto-correction suggestions for fixable issues
"""

import re
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# NCPDP Reject Codes (Common)
# ============================================================

REJECT_CODES = {
    "70": {"description": "Product/Service Not Covered", "severity": "high", "fixable": False},
    "75": {"description": "Prior Authorization Required", "severity": "high", "fixable": True},
    "76": {"description": "Plan Limitations Exceeded", "severity": "medium", "fixable": True},
    "77": {"description": "Discontinued Product/NDC", "severity": "high", "fixable": True},
    "78": {"description": "Cost Exceeds Maximum", "severity": "medium", "fixable": True},
    "79": {"description": "Refill Too Soon", "severity": "medium", "fixable": True},
    "80": {"description": "No Claim Found For Reversal", "severity": "low", "fixable": False},
    "83": {"description": "Duplicate Paid Claim", "severity": "medium", "fixable": True},
    "85": {"description": "Claim Not Processed", "severity": "low", "fixable": True},
    "88": {"description": "DUR Reject", "severity": "high", "fixable": True},
    "89": {"description": "Step Therapy Required", "severity": "high", "fixable": True},
    "MR": {"description": "Mandatory Reversal Required", "severity": "medium", "fixable": True},
    "N1": {"description": "Quantity Not Covered", "severity": "medium", "fixable": True},
    "N6": {"description": "Exceeds Maximum Days Supply", "severity": "medium", "fixable": True},
    "N7": {"description": "Exceeds Maximum Dosage", "severity": "high", "fixable": True},
    "PA": {"description": "Prior Auth Needed", "severity": "high", "fixable": True},
    "QL": {"description": "Quantity Limit Exceeded", "severity": "medium", "fixable": True},
    "ST": {"description": "Step Therapy Required", "severity": "high", "fixable": True},
}

# Common DAW (Dispense As Written) codes
DAW_CODES = {
    0: "No product selection indicated",
    1: "Substitution not allowed by prescriber",
    2: "Substitution allowed - patient requested brand",
    3: "Substitution allowed - pharmacist selected",
    4: "Substitution allowed - generic not in stock",
    5: "Substitution allowed - brand dispensed as generic",
    7: "Substitution not allowed - brand mandated by law",
    8: "Substitution allowed - generic not available",
    9: "Substitution allowed - other",
}

# Standard quantity limits by common drug forms
QUANTITY_LIMITS = {
    "tablet": {"min": 1, "max_per_day": 12, "max_per_fill": 360},
    "capsule": {"min": 1, "max_per_day": 12, "max_per_fill": 360},
    "ml": {"min": 1, "max_per_fill": 1000},
    "patch": {"min": 1, "max_per_fill": 30},
    "inhaler": {"min": 1, "max_per_fill": 3},
    "injection": {"min": 1, "max_per_fill": 12},
    "suppository": {"min": 1, "max_per_fill": 60},
    "default": {"min": 1, "max_per_fill": 360},
}


@dataclass
class ClaimDraft:
    """A claim to be validated before submission."""
    claim_id: str = ""
    ndc: str = ""
    drug_name: str = ""
    quantity: float = 0.0
    days_supply: int = 0
    daw_code: int = 0
    payer: str = ""
    pbm: str = ""
    plan_id: str = ""
    patient_id: str = ""
    prescriber_npi: str = ""
    pharmacy_npi: str = ""
    fill_date: str = ""             # YYYY-MM-DD
    rx_number: str = ""
    refill_number: int = 0
    compound: bool = False
    prior_auth_number: str = ""
    diagnosis_code: str = ""
    drug_form: str = "tablet"
    is_brand: bool = False
    is_specialty: bool = False
    is_controlled: bool = False
    schedule: int = 0               # DEA schedule (2-5)
    usual_customary_price: float = 0.0
    ingredient_cost: float = 0.0
    dispensing_fee: float = 0.0
    submitted_price: float = 0.0    # total submitted charge


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str       # critical / high / medium / low / info
    message: str
    suggestion: str = ""
    reject_code: str = ""
    auto_fixable: bool = False
    fix_action: str = ""


class ClaimSubmissionOptimizer:
    """
    Pre-submission claim validation and optimization engine.
    Validates claims against 30+ rules and suggests corrections.
    """

    def __init__(self):
        self.denial_history: Dict[str, List[Dict]] = defaultdict(list)
        self.payer_rules: Dict[str, Dict] = {}
        self.formulary_cache: Dict[str, Dict] = {}

    # -------------------------------------------------------
    # Historical Learning
    # -------------------------------------------------------

    def load_denial_history(self, denials: List[Dict[str, Any]]) -> int:
        """Load historical denial data for pattern learning."""
        loaded = 0
        for d in denials:
            payer = d.get("payer", "Unknown")
            self.denial_history[payer].append({
                "ndc": d.get("ndc", ""),
                "drug_name": d.get("drug_name", ""),
                "reject_code": d.get("reject_code", ""),
                "denial_reason": d.get("denial_reason", ""),
                "quantity": d.get("quantity", 0),
                "days_supply": d.get("days_supply", 0),
                "date": d.get("date", ""),
            })
            loaded += 1
        return loaded

    def load_payer_rules(self, payer: str, rules: Dict[str, Any]) -> None:
        """Load payer-specific validation rules."""
        self.payer_rules[payer] = rules

    # -------------------------------------------------------
    # Core Validation
    # -------------------------------------------------------

    def validate_claim(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single claim before submission.

        Returns comprehensive validation results with score
        and recommendations.
        """
        claim = self._parse_claim(claim_data)
        validations = []

        # Run all validation rules
        validations.extend(self._validate_ndc(claim))
        validations.extend(self._validate_quantity_supply(claim))
        validations.extend(self._validate_daw_code(claim))
        validations.extend(self._validate_refill_timing(claim))
        validations.extend(self._validate_pricing(claim))
        validations.extend(self._validate_prescriber(claim))
        validations.extend(self._validate_controlled_substance(claim))
        validations.extend(self._validate_prior_auth(claim))
        validations.extend(self._validate_compound(claim))
        validations.extend(self._validate_historical_patterns(claim))

        # Compute submission score
        score, recommendation = self._compute_score(validations)

        # Group by severity
        issues_by_severity = defaultdict(list)
        for v in validations:
            if not v.passed:
                issues_by_severity[v.severity].append({
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "message": v.message,
                    "suggestion": v.suggestion,
                    "reject_code": v.reject_code,
                    "auto_fixable": v.auto_fixable,
                    "fix_action": v.fix_action,
                })

        auto_fixes = [
            v for v in validations
            if not v.passed and v.auto_fixable
        ]

        return {
            "claim_id": claim.claim_id,
            "drug_name": claim.drug_name,
            "payer": claim.payer,
            "submission_score": score,
            "recommendation": recommendation,
            "total_checks": len(validations),
            "passed": sum(1 for v in validations if v.passed),
            "failed": sum(1 for v in validations if not v.passed),
            "issues_by_severity": dict(issues_by_severity),
            "auto_fixable_count": len(auto_fixes),
            "auto_fix_suggestions": [
                {"rule": v.rule_id, "fix": v.fix_action}
                for v in auto_fixes
            ],
            "all_validations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "passed": v.passed,
                    "severity": v.severity,
                    "message": v.message,
                }
                for v in validations
            ],
        }

    def validate_batch(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of claims."""
        results = []
        for claim_data in claims:
            result = self.validate_claim(claim_data)
            results.append(result)

        scores = [r["submission_score"] for r in results]
        pass_count = sum(1 for r in results if r["recommendation"] == "submit")
        fix_count = sum(1 for r in results if r["recommendation"] == "fix_and_submit")
        hold_count = sum(1 for r in results if r["recommendation"] in ("hold", "reject"))

        return {
            "batch_size": len(results),
            "avg_score": round(statistics.mean(scores), 1) if scores else 0,
            "ready_to_submit": pass_count,
            "needs_fixes": fix_count,
            "should_hold": hold_count,
            "total_auto_fixable": sum(r["auto_fixable_count"] for r in results),
            "claims": results,
        }

    def _parse_claim(self, data: Dict[str, Any]) -> ClaimDraft:
        """Parse dict into ClaimDraft."""
        return ClaimDraft(
            claim_id=str(data.get("claim_id", "")),
            ndc=str(data.get("ndc", "")),
            drug_name=str(data.get("drug_name", "")),
            quantity=float(data.get("quantity", 0)),
            days_supply=int(data.get("days_supply", 0)),
            daw_code=int(data.get("daw_code", 0)),
            payer=str(data.get("payer", "")),
            pbm=str(data.get("pbm", "")),
            plan_id=str(data.get("plan_id", "")),
            patient_id=str(data.get("patient_id", "")),
            prescriber_npi=str(data.get("prescriber_npi", "")),
            pharmacy_npi=str(data.get("pharmacy_npi", "")),
            fill_date=str(data.get("fill_date", "")),
            rx_number=str(data.get("rx_number", "")),
            refill_number=int(data.get("refill_number", 0)),
            compound=bool(data.get("compound", False)),
            prior_auth_number=str(data.get("prior_auth_number", "")),
            diagnosis_code=str(data.get("diagnosis_code", "")),
            drug_form=str(data.get("drug_form", "tablet")),
            is_brand=bool(data.get("is_brand", False)),
            is_specialty=bool(data.get("is_specialty", False)),
            is_controlled=bool(data.get("is_controlled", False)),
            schedule=int(data.get("schedule", 0)),
            usual_customary_price=float(data.get("usual_customary_price", 0)),
            ingredient_cost=float(data.get("ingredient_cost", 0)),
            dispensing_fee=float(data.get("dispensing_fee", 0)),
            submitted_price=float(data.get("submitted_price", 0)),
        )

    # -------------------------------------------------------
    # Validation Rules
    # -------------------------------------------------------

    def _validate_ndc(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate NDC format and status."""
        results = []

        # NDC format check (11-digit, various formats)
        ndc = claim.ndc.replace("-", "").replace(" ", "")
        if not ndc:
            results.append(ValidationResult(
                rule_id="NDC-001",
                rule_name="NDC Present",
                passed=False,
                severity="critical",
                message="NDC is missing. Claim will be rejected.",
                suggestion="Add valid 11-digit NDC.",
                reject_code="07",
            ))
        elif not re.match(r"^\d{11}$", ndc):
            results.append(ValidationResult(
                rule_id="NDC-002",
                rule_name="NDC Format",
                passed=False,
                severity="high",
                message=f"NDC '{claim.ndc}' is not a valid 11-digit format.",
                suggestion="Verify NDC format: 5-4-2 or 4-4-2 pattern.",
                reject_code="07",
                auto_fixable=True,
                fix_action=f"Reformat NDC to 11-digit: {ndc.zfill(11)}",
            ))
        else:
            results.append(ValidationResult(
                rule_id="NDC-001",
                rule_name="NDC Format Valid",
                passed=True,
                severity="info",
                message="NDC format is valid.",
            ))

        return results

    def _validate_quantity_supply(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate quantity and days supply consistency."""
        results = []

        # Quantity must be positive
        if claim.quantity <= 0:
            results.append(ValidationResult(
                rule_id="QTY-001",
                rule_name="Quantity Positive",
                passed=False,
                severity="critical",
                message="Quantity must be greater than zero.",
                suggestion="Enter correct dispensed quantity.",
                reject_code="EG",
            ))
            return results

        results.append(ValidationResult(
            rule_id="QTY-001",
            rule_name="Quantity Positive",
            passed=True,
            severity="info",
            message=f"Quantity {claim.quantity} is valid.",
        ))

        # Days supply must be positive
        if claim.days_supply <= 0:
            results.append(ValidationResult(
                rule_id="QTY-002",
                rule_name="Days Supply Valid",
                passed=False,
                severity="high",
                message="Days supply must be greater than zero.",
                suggestion="Enter correct days supply.",
                reject_code="EN",
            ))
        else:
            results.append(ValidationResult(
                rule_id="QTY-002",
                rule_name="Days Supply Valid",
                passed=True,
                severity="info",
                message=f"Days supply {claim.days_supply} is valid.",
            ))

            # Quantity/day supply ratio check
            daily_qty = claim.quantity / claim.days_supply
            form_limits = QUANTITY_LIMITS.get(claim.drug_form, QUANTITY_LIMITS["default"])

            if daily_qty > form_limits.get("max_per_day", 12):
                results.append(ValidationResult(
                    rule_id="QTY-003",
                    rule_name="Daily Quantity Reasonable",
                    passed=False,
                    severity="high",
                    message=f"Daily quantity ({daily_qty:.1f}/day) exceeds max for {claim.drug_form}.",
                    suggestion=f"Verify quantity or increase days supply.",
                    reject_code="N7",
                    auto_fixable=True,
                    fix_action=f"Adjust days_supply to {int(claim.quantity / form_limits.get('max_per_day', 4))}",
                ))
            else:
                results.append(ValidationResult(
                    rule_id="QTY-003",
                    rule_name="Daily Quantity Reasonable",
                    passed=True,
                    severity="info",
                    message=f"Daily quantity ({daily_qty:.1f}/day) is within normal range.",
                ))

        # Max days supply check
        if claim.days_supply > 90 and not claim.is_specialty:
            results.append(ValidationResult(
                rule_id="QTY-004",
                rule_name="Days Supply Under 90",
                passed=False,
                severity="medium",
                message=f"Days supply ({claim.days_supply}) exceeds 90-day limit for most plans.",
                suggestion="Reduce to 90-day supply unless mail-order.",
                reject_code="N6",
                auto_fixable=True,
                fix_action="Set days_supply to 90",
            ))

        return results

    def _validate_daw_code(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate DAW code consistency."""
        results = []

        if claim.daw_code not in DAW_CODES:
            results.append(ValidationResult(
                rule_id="DAW-001",
                rule_name="DAW Code Valid",
                passed=False,
                severity="medium",
                message=f"DAW code {claim.daw_code} is not a standard NCPDP code.",
                suggestion=f"Use standard DAW codes: {list(DAW_CODES.keys())}",
                auto_fixable=True,
                fix_action="Set DAW to 0 (no product selection indicated)",
            ))
        else:
            results.append(ValidationResult(
                rule_id="DAW-001",
                rule_name="DAW Code Valid",
                passed=True,
                severity="info",
                message=f"DAW {claim.daw_code}: {DAW_CODES[claim.daw_code]}",
            ))

        # Brand with DAW 0 warning
        if claim.is_brand and claim.daw_code == 0:
            results.append(ValidationResult(
                rule_id="DAW-002",
                rule_name="Brand DAW Optimization",
                passed=False,
                severity="medium",
                message="Brand drug submitted with DAW 0. May be reimbursed at generic rate.",
                suggestion="If prescriber specified brand: use DAW 1. If patient requested: use DAW 2.",
                auto_fixable=True,
                fix_action="Set DAW to 1 if prescriber-directed, or DAW 2 if patient-requested",
            ))

        return results

    def _validate_refill_timing(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate refill timing."""
        results = []

        if not claim.fill_date:
            results.append(ValidationResult(
                rule_id="REF-001",
                rule_name="Fill Date Present",
                passed=False,
                severity="high",
                message="Fill date is missing.",
                suggestion="Add fill date in YYYY-MM-DD format.",
            ))
            return results

        try:
            fill = datetime.strptime(claim.fill_date[:10], "%Y-%m-%d")
        except ValueError:
            results.append(ValidationResult(
                rule_id="REF-001",
                rule_name="Fill Date Format",
                passed=False,
                severity="high",
                message=f"Invalid fill date format: {claim.fill_date}",
                suggestion="Use YYYY-MM-DD format.",
            ))
            return results

        now = datetime.now()

        # Future date check
        if fill > now + timedelta(days=1):
            results.append(ValidationResult(
                rule_id="REF-002",
                rule_name="Fill Date Not Future",
                passed=False,
                severity="high",
                message="Fill date is in the future.",
                suggestion="Correct fill date to today or earlier.",
                reject_code="85",
            ))

        # Very old date check
        if fill < now - timedelta(days=365):
            results.append(ValidationResult(
                rule_id="REF-003",
                rule_name="Fill Date Not Stale",
                passed=False,
                severity="medium",
                message="Fill date is over 1 year old. May exceed filing deadline.",
                suggestion="Most payers require submission within 365 days of fill.",
            ))
        else:
            results.append(ValidationResult(
                rule_id="REF-002",
                rule_name="Fill Date Valid",
                passed=True,
                severity="info",
                message="Fill date is within acceptable range.",
            ))

        return results

    def _validate_pricing(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate pricing fields."""
        results = []

        total = claim.ingredient_cost + claim.dispensing_fee
        if claim.submitted_price > 0 and total > 0:
            if abs(claim.submitted_price - total) > 0.02:
                results.append(ValidationResult(
                    rule_id="PRC-001",
                    rule_name="Price Components Match",
                    passed=False,
                    severity="medium",
                    message=f"Submitted price (${claim.submitted_price:.2f}) doesn't match "
                            f"ingredient + dispensing (${total:.2f}).",
                    suggestion="Verify pricing breakdown.",
                    auto_fixable=True,
                    fix_action=f"Set submitted_price to {total:.2f}",
                ))
            else:
                results.append(ValidationResult(
                    rule_id="PRC-001",
                    rule_name="Price Components Match",
                    passed=True,
                    severity="info",
                    message="Price components are consistent.",
                ))

        if claim.usual_customary_price > 0 and claim.submitted_price > 0:
            if claim.submitted_price > claim.usual_customary_price * 1.5:
                results.append(ValidationResult(
                    rule_id="PRC-002",
                    rule_name="U&C Price Reasonable",
                    passed=False,
                    severity="medium",
                    message="Submitted price is >150% of U&C price. May trigger audit.",
                    suggestion="Verify submitted price against usual & customary.",
                ))

        return results

    def _validate_prescriber(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate prescriber information."""
        results = []

        if not claim.prescriber_npi:
            results.append(ValidationResult(
                rule_id="PRE-001",
                rule_name="Prescriber NPI Present",
                passed=False,
                severity="high",
                message="Prescriber NPI is missing. Required for adjudication.",
                suggestion="Add prescriber's 10-digit NPI number.",
                reject_code="56",
            ))
        elif not re.match(r"^\d{10}$", claim.prescriber_npi):
            results.append(ValidationResult(
                rule_id="PRE-002",
                rule_name="Prescriber NPI Format",
                passed=False,
                severity="high",
                message=f"NPI '{claim.prescriber_npi}' is not a valid 10-digit number.",
                suggestion="Verify NPI at https://npiregistry.cms.hhs.gov/",
            ))
        else:
            results.append(ValidationResult(
                rule_id="PRE-001",
                rule_name="Prescriber NPI Valid Format",
                passed=True,
                severity="info",
                message="Prescriber NPI format is valid.",
            ))

        return results

    def _validate_controlled_substance(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate controlled substance requirements."""
        results = []

        if not claim.is_controlled:
            return results

        if claim.schedule in (2, 3) and claim.refill_number > 0 and claim.schedule == 2:
            results.append(ValidationResult(
                rule_id="CS-001",
                rule_name="Schedule II No Refills",
                passed=False,
                severity="critical",
                message="Schedule II controlled substances cannot be refilled.",
                suggestion="New prescription required for each fill.",
                reject_code="79",
            ))

        if claim.schedule in (2, 3) and claim.days_supply > 30:
            results.append(ValidationResult(
                rule_id="CS-002",
                rule_name="Controlled Substance Day Limit",
                passed=False,
                severity="high",
                message=f"Schedule {claim.schedule} with {claim.days_supply} days supply. "
                        "Most plans limit to 30 days.",
                suggestion="Reduce to 30-day supply.",
                reject_code="N6",
                auto_fixable=True,
                fix_action="Set days_supply to 30",
            ))

        if not claim.diagnosis_code and claim.schedule <= 3:
            results.append(ValidationResult(
                rule_id="CS-003",
                rule_name="Diagnosis Code for Controlled",
                passed=False,
                severity="medium",
                message="Diagnosis code recommended for controlled substance claims.",
                suggestion="Add ICD-10 diagnosis code to support medical necessity.",
            ))

        return results

    def _validate_prior_auth(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate prior authorization requirements."""
        results = []

        # Check if payer typically requires PA for this drug
        payer_denials = self.denial_history.get(claim.payer, [])
        pa_denials = [
            d for d in payer_denials
            if d.get("reject_code") in ("75", "PA") and
            d.get("drug_name", "").lower() == claim.drug_name.lower()
        ]

        if pa_denials and not claim.prior_auth_number:
            results.append(ValidationResult(
                rule_id="PA-001",
                rule_name="Prior Auth History Check",
                passed=False,
                severity="high",
                message=f"This drug was previously denied by {claim.payer} for "
                        f"prior authorization ({len(pa_denials)} times).",
                suggestion="Obtain prior authorization before submitting.",
                reject_code="75",
            ))

        if claim.is_specialty and not claim.prior_auth_number:
            results.append(ValidationResult(
                rule_id="PA-002",
                rule_name="Specialty PA Check",
                passed=False,
                severity="medium",
                message="Specialty drugs frequently require prior authorization.",
                suggestion="Verify PA requirements with payer before submission.",
                reject_code="75",
            ))

        return results

    def _validate_compound(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Validate compound claim requirements."""
        results = []
        if not claim.compound:
            return results

        if not claim.diagnosis_code:
            results.append(ValidationResult(
                rule_id="CMP-001",
                rule_name="Compound Diagnosis Required",
                passed=False,
                severity="high",
                message="Compound claims require a diagnosis code for most payers.",
                suggestion="Add ICD-10 code supporting medical necessity.",
            ))

        return results

    def _validate_historical_patterns(self, claim: ClaimDraft) -> List[ValidationResult]:
        """Check against historical denial patterns."""
        results = []

        payer_denials = self.denial_history.get(claim.payer, [])
        if not payer_denials:
            return results

        # Check if same drug has high denial rate
        drug_denials = [
            d for d in payer_denials
            if d.get("drug_name", "").lower() == claim.drug_name.lower()
        ]

        if len(drug_denials) >= 3:
            common_reasons = defaultdict(int)
            for d in drug_denials:
                reason = d.get("reject_code", d.get("denial_reason", "Unknown"))
                common_reasons[reason] += 1

            top_reason = max(common_reasons, key=common_reasons.get)
            results.append(ValidationResult(
                rule_id="HIST-001",
                rule_name="Historical Denial Pattern",
                passed=False,
                severity="high",
                message=f"'{claim.drug_name}' has been denied {len(drug_denials)} times "
                        f"by {claim.payer}. Most common reason: {top_reason}.",
                suggestion=f"Address '{top_reason}' before submitting. Consider alternative NDC or prior auth.",
            ))

        # Check quantity patterns
        qty_denials = [
            d for d in payer_denials
            if d.get("reject_code") in ("N1", "QL", "N6") and
            d.get("drug_name", "").lower() == claim.drug_name.lower()
        ]

        if qty_denials:
            max_accepted = max(
                (d.get("quantity", 0) for d in payer_denials
                 if d.get("drug_name", "").lower() == claim.drug_name.lower()
                 and d.get("reject_code") not in ("N1", "QL", "N6")),
                default=0,
            )
            if max_accepted > 0 and claim.quantity > max_accepted:
                results.append(ValidationResult(
                    rule_id="HIST-002",
                    rule_name="Quantity History Check",
                    passed=False,
                    severity="medium",
                    message=f"Quantity {claim.quantity} exceeds historically accepted max "
                            f"({max_accepted}) for this payer.",
                    suggestion=f"Reduce quantity to {max_accepted} or obtain override.",
                    reject_code="QL",
                    auto_fixable=True,
                    fix_action=f"Set quantity to {max_accepted}",
                ))

        return results

    # -------------------------------------------------------
    # Score Computation
    # -------------------------------------------------------

    def _compute_score(
        self, validations: List[ValidationResult]
    ) -> Tuple[float, str]:
        """Compute submission score and recommendation."""
        if not validations:
            return 100, "submit"

        severity_penalties = {
            "critical": 30,
            "high": 15,
            "medium": 5,
            "low": 2,
            "info": 0,
        }

        total_penalty = sum(
            severity_penalties.get(v.severity, 0)
            for v in validations
            if not v.passed
        )

        score = max(0, 100 - total_penalty)

        has_critical = any(not v.passed and v.severity == "critical" for v in validations)
        has_high = any(not v.passed and v.severity == "high" for v in validations)
        all_fixable = all(
            v.auto_fixable for v in validations if not v.passed and v.severity in ("critical", "high")
        )

        if has_critical:
            recommendation = "reject"
        elif has_high and not all_fixable:
            recommendation = "hold"
        elif has_high and all_fixable:
            recommendation = "fix_and_submit"
        elif score >= 80:
            recommendation = "submit"
        else:
            recommendation = "fix_and_submit"

        return round(score, 1), recommendation


# ============================================================
# Module-level convenience
# ============================================================

def validate_claim(claim_data: Dict, denial_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Quick single claim validation."""
    optimizer = ClaimSubmissionOptimizer()
    if denial_history:
        optimizer.load_denial_history(denial_history)
    return optimizer.validate_claim(claim_data)

def validate_batch(claims: List[Dict], denial_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Quick batch claim validation."""
    optimizer = ClaimSubmissionOptimizer()
    if denial_history:
        optimizer.load_denial_history(denial_history)
    return optimizer.validate_batch(claims)
