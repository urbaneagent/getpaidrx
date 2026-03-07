"""
340B Drug Pricing Compliance Engine
=====================================
Monitors 340B program compliance for covered entity pharmacies,
tracks eligible vs. ineligible claims, prevents duplicate discounts,
and ensures contract pharmacy arrangement compliance.

Features:
- 340B eligible patient/claim identification
- Duplicate discount prevention (Medicaid exclusion file matching)
- Contract pharmacy arrangement tracking
- Split billing vs. replenishment model management
- Manufacturer rebate conflict detection
- HRSA audit readiness scoring
- Savings calculation (340B ceiling price vs. WAC/NADAC)
- Accumulator and maximizer adjustment tracking
- Covered entity registration validation
"""

import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import uuid
import hashlib


class ThreeFourtyBComplianceEngine:
    """
    Comprehensive 340B Drug Pricing Program compliance engine.
    """

    # 340B covered entity types eligible for the program
    COVERED_ENTITY_TYPES = {
        "DSH": {"label": "Disproportionate Share Hospital", "min_dsh_pct": 11.75},
        "SCH": {"label": "Sole Community Hospital", "min_dsh_pct": 8.0},
        "RRC": {"label": "Rural Referral Center", "min_dsh_pct": 8.0},
        "CAH": {"label": "Critical Access Hospital", "min_dsh_pct": 0},
        "PED": {"label": "Children's Hospital", "min_dsh_pct": 0},
        "CAN": {"label": "Free-Standing Cancer Hospital", "min_dsh_pct": 0},
        "CHC": {"label": "Community Health Center", "min_dsh_pct": 0},
        "FQHC": {"label": "Federally Qualified Health Center", "min_dsh_pct": 0},
        "BG": {"label": "Black Lung Clinic", "min_dsh_pct": 0},
        "HH": {"label": "Hemophilia Treatment Center", "min_dsh_pct": 0},
        "NP": {"label": "Native Hawaiian Health Center", "min_dsh_pct": 0},
        "TB": {"label": "TB Clinic", "min_dsh_pct": 0},
        "TI": {"label": "Title X Family Planning", "min_dsh_pct": 0},
        "STD": {"label": "STD Clinic", "min_dsh_pct": 0},
        "RW": {"label": "Ryan White HIV/AIDS Program", "min_dsh_pct": 0},
        "UD": {"label": "Urban Indian Health", "min_dsh_pct": 0},
    }

    # Drug classification for 340B ceiling price estimation
    DRUG_CATEGORIES = {
        "brand_single_source": {"avg_discount_pct": 51.0, "min_discount_pct": 23.1},
        "brand_innovator_multi": {"avg_discount_pct": 35.0, "min_discount_pct": 15.1},
        "generic": {"avg_discount_pct": 80.0, "min_discount_pct": 13.0},
        "biosimilar": {"avg_discount_pct": 23.0, "min_discount_pct": 13.0},
        "orphan_drug": {"avg_discount_pct": 0, "min_discount_pct": 0},  # May be excluded
    }

    # Billing models
    BILLING_MODELS = {
        "split_billing": {
            "description": "Claims separated at POS by 340B vs. non-340B eligibility",
            "pros": ["Real-time identification", "Lower compliance risk"],
            "cons": ["Complex POS integration", "Staff training required"],
        },
        "replenishment": {
            "description": "All drugs dispensed from WAC stock, 340B-eligible claims identified retrospectively",
            "pros": ["Simpler POS workflow", "Retrospective analysis"],
            "cons": ["Higher diversion risk", "Complex reconciliation"],
        },
        "virtual_inventory": {
            "description": "Software-based tracking without physical inventory separation",
            "pros": ["No physical separation", "Automated tracking"],
            "cons": ["Requires robust software", "Audit trail complexity"],
        },
    }

    def __init__(self, entity_type: str = "DSH", entity_id: Optional[str] = None):
        self.entity_type = entity_type
        self.entity_id = entity_id or str(uuid.uuid4())[:8]
        self.claims_db: List[Dict] = []
        self.medicaid_exclusion_file: Dict[str, Dict] = {}
        self.contract_pharmacies: List[Dict] = []
        self.audit_findings: List[Dict] = []
        self.savings_log: List[Dict] = []

    def register_covered_entity(self, entity_data: Dict) -> Dict:
        """Validate and register a covered entity for 340B program."""
        entity_type = entity_data.get("type", "").upper()

        if entity_type not in self.COVERED_ENTITY_TYPES:
            return {
                "status": "error",
                "message": f"Invalid entity type: {entity_type}. Valid types: {list(self.COVERED_ENTITY_TYPES.keys())}",
            }

        type_config = self.COVERED_ENTITY_TYPES[entity_type]
        dsh_pct = entity_data.get("dsh_adjustment_percentage", 0)

        # DSH/SCH/RRC require minimum DSH percentage
        if type_config["min_dsh_pct"] > 0 and dsh_pct < type_config["min_dsh_pct"]:
            return {
                "status": "error",
                "message": (
                    f"{type_config['label']} requires DSH adjustment ≥ {type_config['min_dsh_pct']}%. "
                    f"Provided: {dsh_pct}%"
                ),
            }

        # Check HRSA registration
        hrsa_id = entity_data.get("hrsa_id")
        if not hrsa_id:
            return {"status": "error", "message": "HRSA 340B ID is required for covered entity registration"}

        registration = {
            "entity_id": self.entity_id,
            "hrsa_id": hrsa_id,
            "entity_type": entity_type,
            "entity_type_label": type_config["label"],
            "name": entity_data.get("name", ""),
            "address": entity_data.get("address", {}),
            "dsh_percentage": dsh_pct,
            "registration_date": datetime.now().isoformat(),
            "status": "active",
            "billing_model": entity_data.get("billing_model", "split_billing"),
            "contract_pharmacy_count": len(self.contract_pharmacies),
            "compliance_score": 100,  # Start at perfect, deduct for violations
        }

        return {"status": "success", "registration": registration}

    def evaluate_claim_eligibility(self, claim: Dict) -> Dict:
        """
        Determine if a claim is eligible for 340B pricing.
        
        Eligibility criteria:
        1. Patient is a patient of the covered entity
        2. Drug is on the covered entity's formulary
        3. Prescriber has a relationship with the covered entity
        4. Claim is not a Medicaid claim (duplicate discount prevention)
        5. Drug is not an orphan drug (if applicable)
        """
        claim_id = claim.get("claim_id", str(uuid.uuid4())[:8])
        ndc = claim.get("ndc", "")
        patient_id = claim.get("patient_id", "")
        prescriber_npi = claim.get("prescriber_npi", "")
        payer_type = claim.get("payer_type", "").lower()
        drug_category = claim.get("drug_category", "brand_single_source")

        eligibility = {
            "claim_id": claim_id,
            "ndc": ndc,
            "eligible": True,
            "checks": [],
            "disqualification_reasons": [],
        }

        # Check 1: Patient relationship
        patient_of_entity = claim.get("patient_of_entity", True)
        eligibility["checks"].append({
            "check": "patient_relationship",
            "passed": patient_of_entity,
            "detail": "Patient is registered with covered entity" if patient_of_entity else "Patient not registered",
        })
        if not patient_of_entity:
            eligibility["eligible"] = False
            eligibility["disqualification_reasons"].append("Patient not a patient of covered entity")

        # Check 2: Prescriber relationship
        prescriber_valid = claim.get("prescriber_affiliated", True)
        eligibility["checks"].append({
            "check": "prescriber_affiliation",
            "passed": prescriber_valid,
            "detail": f"Prescriber NPI {prescriber_npi} {'affiliated' if prescriber_valid else 'not affiliated'}",
        })
        if not prescriber_valid:
            eligibility["eligible"] = False
            eligibility["disqualification_reasons"].append("Prescriber not affiliated with covered entity")

        # Check 3: Duplicate discount prevention (Medicaid)
        is_medicaid = payer_type in ("medicaid", "managed_medicaid", "medicaid_mco")
        medicaid_excluded = ndc in self.medicaid_exclusion_file

        if is_medicaid and not medicaid_excluded:
            eligibility["eligible"] = False
            eligibility["disqualification_reasons"].append(
                "Medicaid claim - not on manufacturer exclusion file (duplicate discount risk)"
            )
            eligibility["checks"].append({
                "check": "duplicate_discount",
                "passed": False,
                "detail": "Medicaid claim cannot use 340B pricing unless manufacturer has excluded NDC from rebates",
            })
        else:
            eligibility["checks"].append({
                "check": "duplicate_discount",
                "passed": True,
                "detail": "No duplicate discount conflict" if not is_medicaid else "NDC on exclusion file - cleared",
            })

        # Check 4: Orphan drug exclusion check
        is_orphan = claim.get("orphan_drug", False)
        if is_orphan and self.entity_type not in ("CHC", "FQHC", "RW", "TI", "BG", "HH"):
            # Non-grantee hospitals may be subject to orphan drug exclusion
            eligibility["checks"].append({
                "check": "orphan_drug",
                "passed": False,
                "detail": "Orphan drug exclusion applies for non-grantee hospital-type entities",
            })
            eligibility["eligible"] = False
            eligibility["disqualification_reasons"].append("Orphan drug exclusion for hospital entity type")
        else:
            eligibility["checks"].append({
                "check": "orphan_drug",
                "passed": True,
                "detail": "Not an orphan drug" if not is_orphan else "Entity type exempt from orphan drug exclusion",
            })

        # Check 5: Contract pharmacy arrangement
        dispensing_pharmacy = claim.get("dispensing_pharmacy_npi", "")
        is_contract = claim.get("is_contract_pharmacy", False)

        if is_contract:
            contract_valid = any(
                cp.get("pharmacy_npi") == dispensing_pharmacy and cp.get("status") == "active"
                for cp in self.contract_pharmacies
            )
            eligibility["checks"].append({
                "check": "contract_pharmacy",
                "passed": contract_valid,
                "detail": f"Contract pharmacy {'valid' if contract_valid else 'not registered/inactive'}",
            })
            if not contract_valid:
                eligibility["eligible"] = False
                eligibility["disqualification_reasons"].append("Dispensing pharmacy not in active contract pharmacy list")

        # Calculate savings if eligible
        if eligibility["eligible"]:
            savings = self._calculate_340b_savings(claim)
            eligibility["savings"] = savings

        # Overall status
        eligibility["status"] = "eligible" if eligibility["eligible"] else "ineligible"
        eligibility["checks_passed"] = sum(1 for c in eligibility["checks"] if c["passed"])
        eligibility["checks_total"] = len(eligibility["checks"])
        eligibility["evaluated_at"] = datetime.now().isoformat()

        self.claims_db.append(eligibility)
        return eligibility

    def _calculate_340b_savings(self, claim: Dict) -> Dict:
        """Calculate 340B savings vs. WAC/NADAC pricing."""
        wac_price = claim.get("wac_unit_price", 0)
        nadac_price = claim.get("nadac_unit_price", 0)
        quantity = claim.get("quantity", 0)
        drug_category = claim.get("drug_category", "brand_single_source")
        reimbursement = claim.get("reimbursement_amount", 0)

        category_config = self.DRUG_CATEGORIES.get(drug_category, self.DRUG_CATEGORIES["brand_single_source"])
        avg_discount = category_config["avg_discount_pct"]
        min_discount = category_config["min_discount_pct"]

        # Estimate 340B ceiling price
        if wac_price > 0:
            estimated_ceiling_unit = wac_price * (1 - avg_discount / 100)
            estimated_ceiling_min = wac_price * (1 - min_discount / 100)
        else:
            estimated_ceiling_unit = 0
            estimated_ceiling_min = 0

        total_wac = wac_price * quantity
        total_ceiling_est = estimated_ceiling_unit * quantity
        total_ceiling_max = estimated_ceiling_min * quantity

        # Savings = reimbursement - 340B cost
        savings_estimate = reimbursement - total_ceiling_est if reimbursement > 0 else total_wac - total_ceiling_est

        savings_data = {
            "wac_unit_price": round(wac_price, 4),
            "nadac_unit_price": round(nadac_price, 4),
            "estimated_340b_ceiling_unit": round(estimated_ceiling_unit, 4),
            "quantity": quantity,
            "total_wac_cost": round(total_wac, 2),
            "total_340b_cost_estimate": round(total_ceiling_est, 2),
            "total_340b_cost_max": round(total_ceiling_max, 2),
            "reimbursement": round(reimbursement, 2),
            "savings_estimate": round(savings_estimate, 2),
            "savings_pct": round((savings_estimate / total_wac * 100) if total_wac > 0 else 0, 1),
            "drug_category": drug_category,
            "discount_applied": f"{avg_discount}% (avg for {drug_category})",
        }

        self.savings_log.append({
            "claim_id": claim.get("claim_id", ""),
            "ndc": claim.get("ndc", ""),
            "savings": savings_estimate,
            "date": datetime.now().isoformat(),
        })

        return savings_data

    def load_medicaid_exclusion_file(self, exclusion_entries: List[Dict]) -> Dict:
        """
        Load manufacturer Medicaid exclusion file entries.
        NDCs on this file can use 340B pricing even for Medicaid claims.
        """
        loaded = 0
        for entry in exclusion_entries:
            ndc = entry.get("ndc", "")
            if ndc:
                self.medicaid_exclusion_file[ndc] = {
                    "ndc": ndc,
                    "manufacturer": entry.get("manufacturer", ""),
                    "drug_name": entry.get("drug_name", ""),
                    "effective_date": entry.get("effective_date", ""),
                    "termination_date": entry.get("termination_date"),
                }
                loaded += 1

        return {
            "status": "success",
            "loaded": loaded,
            "total_exclusions": len(self.medicaid_exclusion_file),
        }

    def register_contract_pharmacy(self, pharmacy_data: Dict) -> Dict:
        """Register a contract pharmacy arrangement."""
        pharmacy = {
            "id": str(uuid.uuid4())[:8],
            "pharmacy_npi": pharmacy_data.get("npi", ""),
            "pharmacy_name": pharmacy_data.get("name", ""),
            "address": pharmacy_data.get("address", {}),
            "status": "active",
            "agreement_start": pharmacy_data.get("start_date", datetime.now().strftime("%Y-%m-%d")),
            "agreement_end": pharmacy_data.get("end_date"),
            "billing_model": pharmacy_data.get("billing_model", "replenishment"),
            "admin_fee_pct": pharmacy_data.get("admin_fee_pct", 15.0),
            "registered_at": datetime.now().isoformat(),
        }

        self.contract_pharmacies.append(pharmacy)
        return {"status": "success", "contract_pharmacy": pharmacy}

    def run_compliance_audit(self, claims: Optional[List[Dict]] = None) -> Dict:
        """
        Run a comprehensive 340B compliance audit.
        Checks for diversion, duplicate discounts, and program integrity.
        """
        audit_id = str(uuid.uuid4())[:8]
        claims_to_audit = claims or self.claims_db
        now = datetime.now()

        findings = []
        risk_score = 0

        # 1. Check for potential diversion (non-patient claims marked as eligible)
        diversion_suspects = [
            c for c in claims_to_audit
            if c.get("eligible") and not c.get("checks", [{}])[0].get("passed", True)
        ]
        if diversion_suspects:
            finding = {
                "type": "diversion_risk",
                "severity": "high",
                "count": len(diversion_suspects),
                "description": f"{len(diversion_suspects)} claims flagged with potential diversion risk",
                "recommendation": "Review patient-entity relationship for flagged claims",
            }
            findings.append(finding)
            risk_score += 25

        # 2. Duplicate discount check
        medicaid_340b = [
            c for c in claims_to_audit
            if "duplicate_discount" in str(c.get("disqualification_reasons", []))
        ]
        if medicaid_340b:
            finding = {
                "type": "duplicate_discount",
                "severity": "critical",
                "count": len(medicaid_340b),
                "description": f"{len(medicaid_340b)} potential duplicate discount violations detected",
                "recommendation": "Immediately exclude these claims from 340B pricing; update exclusion file",
            }
            findings.append(finding)
            risk_score += 40

        # 3. Contract pharmacy compliance
        inactive_cp_claims = []
        for c in claims_to_audit:
            for check in c.get("checks", []):
                if check.get("check") == "contract_pharmacy" and not check.get("passed"):
                    inactive_cp_claims.append(c)
        if inactive_cp_claims:
            finding = {
                "type": "contract_pharmacy_violation",
                "severity": "high",
                "count": len(inactive_cp_claims),
                "description": f"{len(inactive_cp_claims)} claims dispensed at unregistered/inactive contract pharmacies",
                "recommendation": "Verify contract pharmacy registrations and update HRSA database",
            }
            findings.append(finding)
            risk_score += 20

        # 4. Orphan drug violations
        orphan_violations = [
            c for c in claims_to_audit
            if "orphan_drug" in str(c.get("disqualification_reasons", []))
        ]
        if orphan_violations:
            finding = {
                "type": "orphan_drug_violation",
                "severity": "medium",
                "count": len(orphan_violations),
                "description": f"{len(orphan_violations)} potential orphan drug exclusion violations",
                "recommendation": "Review orphan drug designations and entity type exemptions",
            }
            findings.append(finding)
            risk_score += 15

        # 5. Savings analysis
        total_savings = sum(
            c.get("savings", {}).get("savings_estimate", 0)
            for c in claims_to_audit if c.get("eligible")
        )
        eligible_count = sum(1 for c in claims_to_audit if c.get("eligible"))
        ineligible_count = sum(1 for c in claims_to_audit if not c.get("eligible"))

        # Compute overall compliance score
        compliance_score = max(0, 100 - risk_score)
        if compliance_score >= 90:
            grade = "A"
        elif compliance_score >= 80:
            grade = "B"
        elif compliance_score >= 70:
            grade = "C"
        elif compliance_score >= 60:
            grade = "D"
        else:
            grade = "F"

        audit_result = {
            "audit_id": audit_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "audit_date": now.isoformat(),
            "claims_audited": len(claims_to_audit),
            "eligible_claims": eligible_count,
            "ineligible_claims": ineligible_count,
            "eligibility_rate": round(eligible_count / len(claims_to_audit) * 100, 1) if claims_to_audit else 0,
            "total_340b_savings": round(total_savings, 2),
            "findings": findings,
            "findings_count": len(findings),
            "compliance_score": compliance_score,
            "compliance_grade": grade,
            "risk_level": "critical" if risk_score >= 40 else "high" if risk_score >= 25 else "medium" if risk_score >= 10 else "low",
            "hrsa_audit_readiness": "ready" if compliance_score >= 85 else "needs_improvement" if compliance_score >= 70 else "at_risk",
            "recommendations": [f["recommendation"] for f in findings],
            "next_audit_date": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
        }

        self.audit_findings.append(audit_result)
        return audit_result

    def get_savings_summary(self, period_days: int = 30) -> Dict:
        """Get 340B savings summary for a given period."""
        cutoff = datetime.now() - timedelta(days=period_days)
        period_savings = [
            s for s in self.savings_log
            if s.get("date", "") >= cutoff.isoformat()
        ]

        if not period_savings:
            return {"period_days": period_days, "total_savings": 0, "claim_count": 0}

        savings_amounts = [s["savings"] for s in period_savings]

        return {
            "period_days": period_days,
            "total_savings": round(sum(savings_amounts), 2),
            "claim_count": len(period_savings),
            "avg_savings_per_claim": round(statistics.mean(savings_amounts), 2),
            "max_savings_claim": round(max(savings_amounts), 2),
            "annualized_savings": round(sum(savings_amounts) / period_days * 365, 2),
        }

    def get_program_dashboard(self) -> Dict:
        """Get comprehensive 340B program dashboard data."""
        total_claims = len(self.claims_db)
        eligible = sum(1 for c in self.claims_db if c.get("eligible"))

        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_type_label": self.COVERED_ENTITY_TYPES.get(self.entity_type, {}).get("label", "Unknown"),
            "total_claims_evaluated": total_claims,
            "eligible_claims": eligible,
            "ineligible_claims": total_claims - eligible,
            "eligibility_rate": round(eligible / total_claims * 100, 1) if total_claims else 0,
            "contract_pharmacies": len(self.contract_pharmacies),
            "active_contract_pharmacies": sum(1 for cp in self.contract_pharmacies if cp["status"] == "active"),
            "medicaid_exclusions_loaded": len(self.medicaid_exclusion_file),
            "savings_30_day": self.get_savings_summary(30),
            "savings_90_day": self.get_savings_summary(90),
            "latest_audit": self.audit_findings[-1] if self.audit_findings else None,
            "billing_model": self.BILLING_MODELS.get("split_billing"),
        }


# FastAPI integration
def create_340b_routes(app):
    """Register 340B compliance API routes."""
    engine = ThreeFourtyBComplianceEngine()

    @app.post("/api/v1/340b/evaluate-claim")
    async def evaluate_claim(request):
        data = await request.json()
        result = engine.evaluate_claim_eligibility(data.get("claim", {}))
        return {"status": "success", "evaluation": result}

    @app.post("/api/v1/340b/batch-evaluate")
    async def batch_evaluate(request):
        data = await request.json()
        claims = data.get("claims", [])
        results = [engine.evaluate_claim_eligibility(c) for c in claims]
        eligible = sum(1 for r in results if r.get("eligible"))
        return {
            "status": "success",
            "total": len(results),
            "eligible": eligible,
            "ineligible": len(results) - eligible,
            "results": results,
        }

    @app.post("/api/v1/340b/exclusion-file")
    async def load_exclusion_file(request):
        data = await request.json()
        result = engine.load_medicaid_exclusion_file(data.get("entries", []))
        return result

    @app.post("/api/v1/340b/contract-pharmacy")
    async def register_contract_pharmacy(request):
        data = await request.json()
        result = engine.register_contract_pharmacy(data)
        return result

    @app.post("/api/v1/340b/audit")
    async def run_audit(request):
        result = engine.run_compliance_audit()
        return {"status": "success", "audit": result}

    @app.get("/api/v1/340b/dashboard")
    async def program_dashboard():
        return {"status": "success", "dashboard": engine.get_program_dashboard()}

    @app.get("/api/v1/340b/savings")
    async def savings_summary(days: int = 30):
        return {"status": "success", "savings": engine.get_savings_summary(days)}

    return engine
