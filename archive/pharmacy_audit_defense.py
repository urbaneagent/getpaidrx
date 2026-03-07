"""
Pharmacy Audit Defense System
================================
Proactive PBM audit preparation and defense toolkit for independent pharmacies.
Identifies audit risk patterns, prepares documentation packages, and generates
appeal letters for recoupment challenges.

Features:
- Audit risk scoring based on dispensing patterns
- Pre-audit self-assessment with automated checks
- Documentation package generator for common audit types
- Appeal letter template engine for recoupment disputes
- DAW code compliance validator
- Quantity override pattern analysis
- Refill-too-soon detection and justification
- Controlled substance dispensing pattern monitor
- Compound prescription audit preparation
- Historical audit outcome tracker
"""

import json
import statistics
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import uuid


class AuditType:
    DESK = "desk_audit"
    ONSITE = "onsite_audit"
    TARGETED = "targeted_audit"
    RANDOM = "random_audit"
    COMPLIANCE = "compliance_audit"
    CONTROLLED = "controlled_substance_audit"
    COMPOUND = "compound_audit"


class PharmacyAuditDefense:
    """
    Proactive pharmacy audit defense and preparation system.
    """

    # Common PBM audit trigger thresholds
    AUDIT_TRIGGERS = {
        "high_daw_rate": {
            "description": "Excessive DAW-1 (brand requested by patient) dispensing",
            "threshold_pct": 15.0,
            "severity": "high",
            "action": "Review DAW-1 documentation for valid patient requests",
        },
        "quantity_override_rate": {
            "description": "Frequent quantity overrides above PBM-approved amounts",
            "threshold_pct": 10.0,
            "severity": "medium",
            "action": "Ensure prescriber authorization documentation exists for all overrides",
        },
        "early_refill_rate": {
            "description": "High rate of refills dispensed before expected fill date",
            "threshold_pct": 8.0,
            "severity": "high",
            "action": "Document vacation overrides, dose changes, and lost/stolen scripts",
        },
        "brand_dispense_rate": {
            "description": "Low generic substitution rate",
            "threshold_pct": 20.0,  # % brand when generic available
            "severity": "medium",
            "action": "Review substitution barriers (NTI drugs, patient preference, formulary)",
        },
        "compound_claim_rate": {
            "description": "Elevated compound prescription dispensing",
            "threshold_pct": 5.0,
            "severity": "high",
            "action": "Prepare compound formulation records and prescriber documentation",
        },
        "controlled_volume": {
            "description": "High volume of Schedule II-IV controlled substances",
            "threshold_pct": 25.0,
            "severity": "critical",
            "action": "Review PDMP checks, patient agreements, prescriber DEA verification",
        },
        "high_cost_claims": {
            "description": "Concentration of high-cost specialty/biologic claims",
            "threshold_pct": 3.0,
            "severity": "medium",
            "action": "Verify specialty accreditation, prior auth, and patient eligibility",
        },
        "single_prescriber_concentration": {
            "description": "Large portion of claims from single prescriber",
            "threshold_pct": 40.0,
            "severity": "medium",
            "action": "Document legitimate prescriber relationship (clinic proximity, specialty)",
        },
    }

    # Documentation requirements by audit type
    DOCUMENTATION_REQUIREMENTS = {
        AuditType.DESK: [
            "prescription_hardcopies",
            "signature_logs",
            "daw_documentation",
            "quantity_override_auth",
            "dispensing_records",
        ],
        AuditType.ONSITE: [
            "all_desk_audit_docs",
            "inventory_records",
            "purchase_invoices",
            "staff_licenses",
            "policy_procedures_manual",
            "quality_assurance_records",
            "temperature_logs",
            "cii_perpetual_inventory",
        ],
        AuditType.CONTROLLED: [
            "dea_registration",
            "cii_perpetual_inventory",
            "pdmp_check_records",
            "patient_id_verification",
            "prescriber_dea_verification",
            "corresponding_responsibility_docs",
            "red_flag_resolution_logs",
        ],
        AuditType.COMPOUND: [
            "master_formulation_records",
            "compounding_logs",
            "ingredient_purchase_records",
            "beyond_use_dating_calcs",
            "potency_testing_results",
            "patient_specific_prescriptions",
            "component_ndc_verification",
        ],
    }

    # Appeal letter categories
    APPEAL_CATEGORIES = {
        "recoupment": {
            "title": "Recoupment Dispute",
            "basis": [
                "Prescription was properly filled per prescriber instructions",
                "Documentation supports claim accuracy",
                "PBM applied incorrect audit standards",
            ],
        },
        "quantity_dispute": {
            "title": "Quantity Override Justification",
            "basis": [
                "Prescriber authorized specific quantity",
                "Clinical necessity documented",
                "Quantity consistent with FDA-approved dosing",
            ],
        },
        "daw_dispute": {
            "title": "DAW Code Justification",
            "basis": [
                "Patient requested brand product (documented)",
                "Prescriber specified brand medically necessary",
                "No AB-rated generic available at time of dispensing",
            ],
        },
        "early_refill": {
            "title": "Early Refill Justification",
            "basis": [
                "Patient traveling / vacation supply",
                "Dosage change by prescriber",
                "Insurance change requiring new fill",
                "Lost or stolen medication (police report available)",
            ],
        },
        "uc_pricing": {
            "title": "Usual & Customary Price Dispute",
            "basis": [
                "U&C price was accurate at time of dispensing",
                "Price reflects acquisition cost plus dispensing fee",
                "Competitive market pricing analysis supports U&C",
            ],
        },
    }

    def __init__(self):
        self.claims_history: List[Dict] = []
        self.audit_history: List[Dict] = []
        self.risk_assessments: List[Dict] = []
        self.appeal_log: List[Dict] = []

    def compute_audit_risk_score(self, dispensing_data: Dict) -> Dict:
        """
        Compute pharmacy audit risk score based on dispensing patterns.
        Returns risk scores by trigger category and overall risk level.
        """
        assessment_id = str(uuid.uuid4())[:8]
        total_claims = dispensing_data.get("total_claims", 0)
        if total_claims == 0:
            return {"assessment_id": assessment_id, "status": "error", "message": "No claims data provided"}

        trigger_results = {}
        total_risk = 0
        critical_count = 0

        for trigger_name, trigger_config in self.AUDIT_TRIGGERS.items():
            threshold = trigger_config["threshold_pct"]
            severity = trigger_config["severity"]

            # Calculate actual rate from dispensing data
            actual_value = dispensing_data.get(trigger_name, 0)

            # Compare to threshold
            if actual_value > threshold:
                risk_factor = min(100, (actual_value / threshold) * 50)
                exceeded = True
            else:
                risk_factor = (actual_value / threshold) * 25 if threshold > 0 else 0
                exceeded = False

            # Severity multiplier
            sev_multiplier = {"critical": 2.0, "high": 1.5, "medium": 1.0}.get(severity, 1.0)
            weighted_risk = risk_factor * sev_multiplier

            if severity == "critical" and exceeded:
                critical_count += 1

            trigger_results[trigger_name] = {
                "description": trigger_config["description"],
                "threshold_pct": threshold,
                "actual_pct": round(actual_value, 1),
                "exceeded": exceeded,
                "risk_score": round(weighted_risk, 1),
                "severity": severity,
                "recommended_action": trigger_config["action"],
            }

            total_risk += weighted_risk

        # Normalize composite
        max_possible = len(self.AUDIT_TRIGGERS) * 100
        composite = min(100, (total_risk / max_possible) * 100) if max_possible > 0 else 0

        # Determine risk level
        if composite >= 75 or critical_count >= 2:
            risk_level = "critical"
            recommendation = "Immediate self-audit required. Engage pharmacy compliance consultant."
        elif composite >= 50:
            risk_level = "high"
            recommendation = "Prepare documentation for likely audit. Review all triggered areas."
        elif composite >= 25:
            risk_level = "medium"
            recommendation = "Monitor flagged areas. Proactive documentation recommended."
        else:
            risk_level = "low"
            recommendation = "Continue normal operations. Maintain documentation standards."

        # Top risk areas
        sorted_triggers = sorted(
            trigger_results.items(), key=lambda x: x[1]["risk_score"], reverse=True
        )
        top_risks = [
            {"trigger": k, **v}
            for k, v in sorted_triggers[:3]
            if v["exceeded"]
        ]

        assessment = {
            "assessment_id": assessment_id,
            "assessed_at": datetime.now().isoformat(),
            "total_claims": total_claims,
            "trigger_analysis": trigger_results,
            "composite_risk_score": round(composite, 1),
            "risk_level": risk_level,
            "critical_triggers": critical_count,
            "exceeded_triggers": sum(1 for t in trigger_results.values() if t["exceeded"]),
            "total_triggers_checked": len(trigger_results),
            "top_risk_areas": top_risks,
            "recommendation": recommendation,
        }

        self.risk_assessments.append(assessment)
        return assessment

    def run_self_audit(self, claims: List[Dict], audit_type: str = AuditType.DESK) -> Dict:
        """
        Run a proactive self-audit on a set of claims.
        Identifies issues before PBM auditors find them.
        """
        audit_id = str(uuid.uuid4())[:8]
        findings = []
        claims_reviewed = 0
        issues_found = 0

        for claim in claims:
            claims_reviewed += 1
            claim_issues = []

            # Check 1: DAW code documentation
            daw_code = claim.get("daw_code", 0)
            if daw_code in (1, 2, 3, 4, 5, 6, 7, 8, 9):
                has_documentation = claim.get("daw_documentation", False)
                if not has_documentation:
                    claim_issues.append({
                        "type": "missing_daw_documentation",
                        "severity": "high",
                        "detail": f"DAW-{daw_code} claim lacks supporting documentation",
                        "remedy": "Obtain signed patient/prescriber DAW request form",
                    })

            # Check 2: Quantity vs. prescribed
            dispensed_qty = claim.get("quantity_dispensed", 0)
            prescribed_qty = claim.get("quantity_prescribed", 0)
            if dispensed_qty > 0 and prescribed_qty > 0 and dispensed_qty != prescribed_qty:
                has_auth = claim.get("quantity_override_auth", False)
                if not has_auth and dispensed_qty > prescribed_qty:
                    claim_issues.append({
                        "type": "quantity_override_no_auth",
                        "severity": "high",
                        "detail": f"Dispensed {dispensed_qty} vs. prescribed {prescribed_qty} without override authorization",
                        "remedy": "Obtain prescriber authorization for quantity change",
                    })

            # Check 3: Refill timing
            last_fill_date = claim.get("last_fill_date")
            fill_date = claim.get("fill_date")
            days_supply = claim.get("days_supply", 30)
            if last_fill_date and fill_date and days_supply:
                try:
                    last_dt = datetime.fromisoformat(last_fill_date)
                    fill_dt = datetime.fromisoformat(fill_date)
                    days_since_last = (fill_dt - last_dt).days
                    expected_refill_day = days_supply * 0.75  # 75% = typical early refill threshold

                    if days_since_last < expected_refill_day:
                        has_justification = claim.get("early_refill_justification")
                        if not has_justification:
                            claim_issues.append({
                                "type": "early_refill_no_justification",
                                "severity": "medium",
                                "detail": f"Refilled {days_since_last} days after last fill ({days_supply}-day supply). No justification on file.",
                                "remedy": "Document reason: vacation, dose change, lost medication",
                            })
                except (ValueError, TypeError):
                    pass

            # Check 4: Prescriber validation
            if not claim.get("prescriber_npi"):
                claim_issues.append({
                    "type": "missing_prescriber_npi",
                    "severity": "high",
                    "detail": "Claim missing prescriber NPI",
                    "remedy": "Add valid prescriber NPI to claim record",
                })

            # Check 5: Sig/directions completeness
            if not claim.get("sig") or len(claim.get("sig", "")) < 5:
                claim_issues.append({
                    "type": "incomplete_sig",
                    "severity": "medium",
                    "detail": "Prescription sig/directions missing or incomplete",
                    "remedy": "Verify and complete prescription directions",
                })

            # Check 6: Controlled substance documentation
            schedule = claim.get("dea_schedule", 0)
            if schedule in (2, 3, 4, 5):
                if not claim.get("pdmp_checked"):
                    claim_issues.append({
                        "type": "pdmp_not_checked",
                        "severity": "critical" if schedule == 2 else "high",
                        "detail": f"Schedule {schedule} - No PDMP check documented",
                        "remedy": "Document PDMP check per state requirements",
                    })
                if schedule == 2 and not claim.get("patient_id_verified"):
                    claim_issues.append({
                        "type": "patient_id_not_verified",
                        "severity": "high",
                        "detail": "Schedule II - Patient ID not verified/documented",
                        "remedy": "Document patient identification verification",
                    })

            # Check 7: Usual & Customary pricing
            uc_price = claim.get("uc_price", 0)
            submitted_price = claim.get("submitted_price", 0)
            if uc_price > 0 and submitted_price > 0 and submitted_price > uc_price * 1.5:
                claim_issues.append({
                    "type": "uc_price_discrepancy",
                    "severity": "medium",
                    "detail": f"Submitted ${submitted_price:.2f} vs. U&C ${uc_price:.2f} (>{50}% over U&C)",
                    "remedy": "Verify U&C pricing is current and defensible",
                })

            if claim_issues:
                issues_found += len(claim_issues)
                findings.append({
                    "claim_id": claim.get("claim_id", "unknown"),
                    "rx_number": claim.get("rx_number", ""),
                    "ndc": claim.get("ndc", ""),
                    "issues": claim_issues,
                    "issue_count": len(claim_issues),
                })

        # Compute audit readiness
        issue_rate = issues_found / claims_reviewed if claims_reviewed > 0 else 0
        if issue_rate <= 0.02:
            readiness = "excellent"
            grade = "A"
        elif issue_rate <= 0.05:
            readiness = "good"
            grade = "B"
        elif issue_rate <= 0.10:
            readiness = "needs_improvement"
            grade = "C"
        elif issue_rate <= 0.20:
            readiness = "at_risk"
            grade = "D"
        else:
            readiness = "critical"
            grade = "F"

        # Required documentation checklist
        doc_requirements = self.DOCUMENTATION_REQUIREMENTS.get(audit_type, [])

        audit_result = {
            "audit_id": audit_id,
            "audit_type": audit_type,
            "run_at": datetime.now().isoformat(),
            "claims_reviewed": claims_reviewed,
            "issues_found": issues_found,
            "claims_with_issues": len(findings),
            "issue_rate": round(issue_rate * 100, 2),
            "readiness_level": readiness,
            "readiness_grade": grade,
            "findings": findings,
            "findings_by_type": self._aggregate_findings_by_type(findings),
            "documentation_checklist": [
                {"item": doc, "status": "pending"} for doc in doc_requirements
            ],
            "remediation_summary": self._generate_remediation_summary(findings),
        }

        self.audit_history.append(audit_result)
        return audit_result

    def generate_appeal_letter(
        self,
        appeal_category: str,
        claim_details: Dict,
        pharmacy_info: Dict,
        additional_justification: Optional[str] = None,
    ) -> Dict:
        """Generate a structured appeal letter for a PBM recoupment dispute."""
        category_config = self.APPEAL_CATEGORIES.get(appeal_category)
        if not category_config:
            return {"status": "error", "message": f"Unknown appeal category: {appeal_category}"}

        appeal_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        # Build the appeal letter structure
        letter = {
            "appeal_id": appeal_id,
            "generated_at": now.isoformat(),
            "category": appeal_category,
            "title": category_config["title"],
            "header": {
                "pharmacy_name": pharmacy_info.get("name", ""),
                "pharmacy_npi": pharmacy_info.get("npi", ""),
                "pharmacy_ncpdp": pharmacy_info.get("ncpdp", ""),
                "pharmacy_address": pharmacy_info.get("address", ""),
                "date": now.strftime("%B %d, %Y"),
                "pbm_name": claim_details.get("pbm_name", ""),
                "pbm_audit_department": claim_details.get("audit_department", "Pharmacy Audit Department"),
                "audit_reference": claim_details.get("audit_reference", ""),
            },
            "subject": (
                f"Appeal of Recoupment - Audit Reference: {claim_details.get('audit_reference', 'N/A')} | "
                f"Rx #: {claim_details.get('rx_number', 'N/A')} | "
                f"Claim ID: {claim_details.get('claim_id', 'N/A')}"
            ),
            "body_sections": [
                {
                    "heading": "Introduction",
                    "content": (
                        f"This letter serves as a formal appeal regarding the recoupment notice dated "
                        f"{claim_details.get('recoupment_date', '[DATE]')} for the amount of "
                        f"${claim_details.get('recoupment_amount', 0):.2f}. We respectfully dispute this "
                        f"recoupment based on the following documented evidence."
                    ),
                },
                {
                    "heading": "Claim Details",
                    "content": (
                        f"Prescription Number: {claim_details.get('rx_number', 'N/A')}\n"
                        f"Date of Service: {claim_details.get('date_of_service', 'N/A')}\n"
                        f"NDC: {claim_details.get('ndc', 'N/A')}\n"
                        f"Drug Name: {claim_details.get('drug_name', 'N/A')}\n"
                        f"Quantity Dispensed: {claim_details.get('quantity', 'N/A')}\n"
                        f"Days Supply: {claim_details.get('days_supply', 'N/A')}\n"
                        f"Patient: {claim_details.get('patient_name', '[PATIENT NAME]')}"
                    ),
                },
                {
                    "heading": "Basis for Appeal",
                    "content": "\n".join(
                        f"• {basis}" for basis in category_config["basis"]
                    ),
                },
                {
                    "heading": "Supporting Evidence",
                    "content": (
                        f"Enclosed please find the following supporting documentation:\n"
                        f"1. Original prescription hardcopy\n"
                        f"2. Dispensing log record\n"
                        f"3. Signature log entry\n"
                        f"{'4. ' + additional_justification if additional_justification else ''}"
                    ),
                },
                {
                    "heading": "Conclusion",
                    "content": (
                        f"Based on the evidence provided, we respectfully request that the recoupment of "
                        f"${claim_details.get('recoupment_amount', 0):.2f} be reversed in full. "
                        f"This prescription was dispensed in compliance with all applicable state and federal "
                        f"laws, and the documentation supports the accuracy of the original claim submission.\n\n"
                        f"We request a response within 30 calendar days per the terms of our provider agreement. "
                        f"Please contact us at the information above if additional documentation is needed."
                    ),
                },
            ],
            "attachments_checklist": [
                "Original prescription hardcopy (front and back)",
                "Pharmacy dispensing log record",
                "Patient signature log",
                "Prescriber documentation (if applicable)",
                "PDMP report (if controlled substance)",
                "Prior authorization approval (if applicable)",
            ],
            "compliance_notes": [
                "Submit via certified mail with return receipt requested",
                "Retain copies of all submitted documents",
                "Note appeal deadline per PBM contract",
                "Consider concurrent state pharmacy board filing if audit is unreasonable",
            ],
        }

        self.appeal_log.append({
            "appeal_id": appeal_id,
            "category": appeal_category,
            "claim_id": claim_details.get("claim_id"),
            "amount": claim_details.get("recoupment_amount", 0),
            "generated_at": now.isoformat(),
            "status": "generated",
        })

        return {"status": "success", "appeal_letter": letter}

    def _aggregate_findings_by_type(self, findings: List[Dict]) -> Dict:
        """Aggregate audit findings by issue type."""
        aggregated = defaultdict(lambda: {"count": 0, "severity_counts": defaultdict(int)})

        for finding in findings:
            for issue in finding.get("issues", []):
                issue_type = issue.get("type", "unknown")
                severity = issue.get("severity", "medium")
                aggregated[issue_type]["count"] += 1
                aggregated[issue_type]["severity_counts"][severity] += 1
                aggregated[issue_type]["description"] = issue.get("detail", "")
                aggregated[issue_type]["remedy"] = issue.get("remedy", "")

        return dict(aggregated)

    def _generate_remediation_summary(self, findings: List[Dict]) -> List[Dict]:
        """Generate prioritized remediation action items."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_issues = []

        for finding in findings:
            for issue in finding.get("issues", []):
                all_issues.append(issue)

        # Deduplicate by type and sort by severity
        seen_types = set()
        unique_remediations = []

        for issue in sorted(all_issues, key=lambda x: severity_order.get(x.get("severity", "medium"), 99)):
            if issue["type"] not in seen_types:
                seen_types.add(issue["type"])
                count = sum(1 for i in all_issues if i["type"] == issue["type"])
                unique_remediations.append({
                    "issue_type": issue["type"],
                    "severity": issue["severity"],
                    "affected_claims": count,
                    "remediation": issue.get("remedy", "Review and correct"),
                    "priority": len(unique_remediations) + 1,
                })

        return unique_remediations

    def get_audit_defense_dashboard(self) -> Dict:
        """Get comprehensive audit defense dashboard."""
        return {
            "risk_assessments": len(self.risk_assessments),
            "latest_risk": self.risk_assessments[-1] if self.risk_assessments else None,
            "audits_completed": len(self.audit_history),
            "latest_audit": self.audit_history[-1] if self.audit_history else None,
            "appeals_generated": len(self.appeal_log),
            "appeals_by_status": defaultdict(int, {
                a["status"]: 1 for a in self.appeal_log
            }),
            "total_recoupment_disputed": sum(a.get("amount", 0) for a in self.appeal_log),
        }


# FastAPI integration
def create_audit_defense_routes(app):
    """Register pharmacy audit defense API routes."""
    engine = PharmacyAuditDefense()

    @app.post("/api/v1/audit/risk-score")
    async def audit_risk_score(request):
        data = await request.json()
        result = engine.compute_audit_risk_score(data.get("dispensing_data", {}))
        return {"status": "success", "assessment": result}

    @app.post("/api/v1/audit/self-audit")
    async def self_audit(request):
        data = await request.json()
        result = engine.run_self_audit(
            data.get("claims", []),
            data.get("audit_type", AuditType.DESK),
        )
        return {"status": "success", "audit": result}

    @app.post("/api/v1/audit/appeal-letter")
    async def generate_appeal(request):
        data = await request.json()
        result = engine.generate_appeal_letter(
            data.get("category", "recoupment"),
            data.get("claim_details", {}),
            data.get("pharmacy_info", {}),
            data.get("additional_justification"),
        )
        return result

    @app.get("/api/v1/audit/dashboard")
    async def audit_dashboard():
        return {"status": "success", "dashboard": engine.get_audit_defense_dashboard()}

    return engine
