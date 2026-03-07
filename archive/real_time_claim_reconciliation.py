"""
Real-Time Claim Reconciliation Engine
Automated reconciliation between submitted and adjudicated claims
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class ReconciliationStatus(Enum):
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    PENDING = "pending"

class DiscrepancyType(Enum):
    AMOUNT_MISMATCH = "amount_mismatch"
    DATE_MISMATCH = "date_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    NDC_MISMATCH = "ndc_mismatch"
    PATIENT_MISMATCH = "patient_mismatch"
    MISSING_REMITTANCE = "missing_remittance"
    UNDERPAYMENT = "underpayment"

@dataclass
class ClaimRecord:
    claim_id: str
    rx_number: str
    ndc: str
    patient_id: str
    submission_date: datetime
    submitted_amount: float
    quantity: int
    days_supply: int
    metadata: Dict = field(default_factory=dict)

@dataclass
class RemittanceRecord:
    remittance_id: str
    claim_id: str
    rx_number: str
    ndc: str
    patient_id: str
    payment_date: datetime
    paid_amount: float
    ingredient_cost: float
    dispensing_fee: float
    patient_pay: float
    plan_pay: float
    adjustment_codes: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

@dataclass
class ReconciliationResult:
    claim_record: ClaimRecord
    remittance_record: Optional[RemittanceRecord]
    status: ReconciliationStatus
    discrepancies: List[Dict]
    amount_difference: float
    confidence_score: float
    reconciled_at: datetime

class RealTimeClaimReconciliation:
    def __init__(self):
        self.submitted_claims: Dict[str, ClaimRecord] = {}
        self.remittances: Dict[str, RemittanceRecord] = {}
        self.reconciliation_results: List[ReconciliationResult] = []
        self.matching_rules = self._initialize_matching_rules()
        self.tolerance_thresholds = {
            "amount_tolerance_cents": 5,
            "date_tolerance_days": 2,
            "quantity_tolerance_percent": 2.0
        }
    
    def _initialize_matching_rules(self) -> Dict:
        """Initialize claim matching rules with priorities"""
        return {
            "primary": {
                "fields": ["claim_id", "rx_number"],
                "weight": 1.0,
                "required": True
            },
            "secondary": {
                "fields": ["ndc", "patient_id", "submission_date"],
                "weight": 0.8,
                "required": False
            },
            "fuzzy": {
                "fields": ["submitted_amount", "quantity"],
                "weight": 0.6,
                "tolerance": True
            }
        }
    
    def register_claim(self, claim_data: Dict) -> str:
        """Register a submitted claim"""
        claim = ClaimRecord(
            claim_id=claim_data["claim_id"],
            rx_number=claim_data["rx_number"],
            ndc=claim_data["ndc"],
            patient_id=claim_data["patient_id"],
            submission_date=datetime.fromisoformat(claim_data["submission_date"]),
            submitted_amount=float(claim_data["submitted_amount"]),
            quantity=int(claim_data["quantity"]),
            days_supply=int(claim_data.get("days_supply", 30)),
            metadata=claim_data.get("metadata", {})
        )
        
        self.submitted_claims[claim.claim_id] = claim
        return claim.claim_id
    
    def register_remittance(self, remittance_data: Dict) -> str:
        """Register a remittance/payment record"""
        remittance = RemittanceRecord(
            remittance_id=remittance_data["remittance_id"],
            claim_id=remittance_data.get("claim_id", ""),
            rx_number=remittance_data["rx_number"],
            ndc=remittance_data["ndc"],
            patient_id=remittance_data["patient_id"],
            payment_date=datetime.fromisoformat(remittance_data["payment_date"]),
            paid_amount=float(remittance_data["paid_amount"]),
            ingredient_cost=float(remittance_data.get("ingredient_cost", 0)),
            dispensing_fee=float(remittance_data.get("dispensing_fee", 0)),
            patient_pay=float(remittance_data.get("patient_pay", 0)),
            plan_pay=float(remittance_data.get("plan_pay", 0)),
            adjustment_codes=remittance_data.get("adjustment_codes", []),
            metadata=remittance_data.get("metadata", {})
        )
        
        self.remittances[remittance.remittance_id] = remittance
        
        # Attempt automatic reconciliation
        self._attempt_reconciliation(remittance)
        
        return remittance.remittance_id
    
    def _attempt_reconciliation(self, remittance: RemittanceRecord):
        """Attempt to reconcile a remittance with submitted claims"""
        # Try to find matching claim
        matched_claim = self._find_matching_claim(remittance)
        
        if matched_claim:
            # Perform detailed reconciliation
            result = self._reconcile_claim_pair(matched_claim, remittance)
            self.reconciliation_results.append(result)
            
            # Remove matched claim from pending
            if result.status == ReconciliationStatus.MATCHED:
                self.submitted_claims.pop(matched_claim.claim_id, None)
        else:
            # No match found - flag as missing claim
            result = ReconciliationResult(
                claim_record=None,
                remittance_record=remittance,
                status=ReconciliationStatus.MISSING,
                discrepancies=[{
                    "type": DiscrepancyType.MISSING_REMITTANCE.value,
                    "description": "Remittance received but no matching claim found",
                    "severity": "high"
                }],
                amount_difference=0.0,
                confidence_score=0.0,
                reconciled_at=datetime.now()
            )
            self.reconciliation_results.append(result)
    
    def _find_matching_claim(self, remittance: RemittanceRecord) -> Optional[ClaimRecord]:
        """Find claim matching the remittance"""
        best_match = None
        best_score = 0.0
        
        for claim in self.submitted_claims.values():
            score = self._calculate_match_score(claim, remittance)
            
            if score > best_score and score >= 0.8:  # 80% confidence threshold
                best_score = score
                best_match = claim
        
        return best_match
    
    def _calculate_match_score(self, claim: ClaimRecord, remittance: RemittanceRecord) -> float:
        """Calculate matching confidence score"""
        score = 0.0
        max_score = 0.0
        
        # Primary matching (claim_id, rx_number)
        rule = self.matching_rules["primary"]
        max_score += rule["weight"]
        
        if claim.claim_id == remittance.claim_id or claim.rx_number == remittance.rx_number:
            score += rule["weight"]
        
        # Secondary matching (NDC, patient, date proximity)
        rule = self.matching_rules["secondary"]
        max_score += rule["weight"]
        
        secondary_matches = 0
        if claim.ndc == remittance.ndc:
            secondary_matches += 1
        if claim.patient_id == remittance.patient_id:
            secondary_matches += 1
        
        date_diff = abs((claim.submission_date - remittance.payment_date).days)
        if date_diff <= self.tolerance_thresholds["date_tolerance_days"]:
            secondary_matches += 1
        
        score += (secondary_matches / 3) * rule["weight"]
        
        # Fuzzy matching (amounts, quantities)
        rule = self.matching_rules["fuzzy"]
        max_score += rule["weight"]
        
        amount_diff = abs(claim.submitted_amount - remittance.paid_amount)
        if amount_diff <= (self.tolerance_thresholds["amount_tolerance_cents"] / 100):
            score += rule["weight"] * 0.5
        
        quantity_diff = abs(claim.quantity - remittance.metadata.get("quantity", claim.quantity))
        if quantity_diff == 0:
            score += rule["weight"] * 0.5
        
        return score / max_score if max_score > 0 else 0.0
    
    def _reconcile_claim_pair(self, claim: ClaimRecord, remittance: RemittanceRecord) -> ReconciliationResult:
        """Perform detailed reconciliation of matched claim/remittance"""
        discrepancies = []
        
        # Check amount discrepancy
        amount_diff = claim.submitted_amount - remittance.paid_amount
        if abs(amount_diff) > (self.tolerance_thresholds["amount_tolerance_cents"] / 100):
            discrepancy_pct = (amount_diff / claim.submitted_amount) * 100
            discrepancies.append({
                "type": DiscrepancyType.AMOUNT_MISMATCH.value,
                "description": f"Amount difference: ${amount_diff:.2f} ({discrepancy_pct:.1f}%)",
                "severity": "high" if abs(discrepancy_pct) > 10 else "medium",
                "expected": claim.submitted_amount,
                "actual": remittance.paid_amount,
                "difference": amount_diff
            })
            
            # Check if it's underpayment
            if amount_diff > 0:
                discrepancies.append({
                    "type": DiscrepancyType.UNDERPAYMENT.value,
                    "description": f"Underpaid by ${amount_diff:.2f}",
                    "severity": "high",
                    "recovery_potential": amount_diff
                })
        
        # Check date discrepancy
        date_diff = abs((claim.submission_date - remittance.payment_date).days)
        if date_diff > self.tolerance_thresholds["date_tolerance_days"]:
            discrepancies.append({
                "type": DiscrepancyType.DATE_MISMATCH.value,
                "description": f"Date difference: {date_diff} days",
                "severity": "low",
                "submission_date": claim.submission_date.isoformat(),
                "payment_date": remittance.payment_date.isoformat()
            })
        
        # Check quantity discrepancy
        remit_quantity = remittance.metadata.get("quantity", claim.quantity)
        if claim.quantity != remit_quantity:
            discrepancies.append({
                "type": DiscrepancyType.QUANTITY_MISMATCH.value,
                "description": f"Quantity mismatch: submitted {claim.quantity}, paid for {remit_quantity}",
                "severity": "medium",
                "expected": claim.quantity,
                "actual": remit_quantity
            })
        
        # Check NDC match
        if claim.ndc != remittance.ndc:
            discrepancies.append({
                "type": DiscrepancyType.NDC_MISMATCH.value,
                "description": "NDC codes do not match",
                "severity": "high",
                "expected": claim.ndc,
                "actual": remittance.ndc
            })
        
        # Check patient match
        if claim.patient_id != remittance.patient_id:
            discrepancies.append({
                "type": DiscrepancyType.PATIENT_MISMATCH.value,
                "description": "Patient IDs do not match",
                "severity": "critical",
                "expected": claim.patient_id,
                "actual": remittance.patient_id
            })
        
        # Determine overall status
        if not discrepancies:
            status = ReconciliationStatus.MATCHED
        elif any(d["severity"] == "critical" for d in discrepancies):
            status = ReconciliationStatus.DISCREPANCY
        else:
            status = ReconciliationStatus.MATCHED if len(discrepancies) <= 1 else ReconciliationStatus.DISCREPANCY
        
        # Calculate confidence score
        confidence = 1.0 - (len(discrepancies) * 0.15)
        confidence = max(0.0, min(1.0, confidence))
        
        return ReconciliationResult(
            claim_record=claim,
            remittance_record=remittance,
            status=status,
            discrepancies=discrepancies,
            amount_difference=amount_diff,
            confidence_score=confidence,
            reconciled_at=datetime.now()
        )
    
    def get_reconciliation_summary(self, days: int = 30) -> Dict:
        """Get reconciliation summary for specified period"""
        cutoff = datetime.now() - timedelta(days=days)
        recent_results = [r for r in self.reconciliation_results 
                         if r.reconciled_at >= cutoff]
        
        if not recent_results:
            return {"status": "no_data", "period_days": days}
        
        total = len(recent_results)
        matched = sum(1 for r in recent_results if r.status == ReconciliationStatus.MATCHED)
        discrepancies = sum(1 for r in recent_results if r.status == ReconciliationStatus.DISCREPANCY)
        missing = sum(1 for r in recent_results if r.status == ReconciliationStatus.MISSING)
        
        total_amount_diff = sum(abs(r.amount_difference) for r in recent_results)
        underpayments = [r for r in recent_results if r.amount_difference > 0]
        total_underpaid = sum(r.amount_difference for r in underpayments)
        
        return {
            "period_days": days,
            "total_reconciliations": total,
            "matched": matched,
            "matched_percentage": (matched / total) * 100,
            "discrepancies": discrepancies,
            "missing_claims": missing,
            "total_amount_variance": total_amount_diff,
            "total_underpayments": total_underpaid,
            "underpayment_count": len(underpayments),
            "average_confidence": sum(r.confidence_score for r in recent_results) / total,
            "pending_claims": len(self.submitted_claims),
            "discrepancy_breakdown": self._get_discrepancy_breakdown(recent_results)
        }
    
    def _get_discrepancy_breakdown(self, results: List[ReconciliationResult]) -> Dict:
        """Break down discrepancies by type"""
        breakdown = {}
        
        for result in results:
            for disc in result.discrepancies:
                disc_type = disc["type"]
                if disc_type not in breakdown:
                    breakdown[disc_type] = {
                        "count": 0,
                        "total_impact": 0.0,
                        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0}
                    }
                
                breakdown[disc_type]["count"] += 1
                breakdown[disc_type]["severity_counts"][disc["severity"]] += 1
                
                if "recovery_potential" in disc:
                    breakdown[disc_type]["total_impact"] += disc["recovery_potential"]
        
        return breakdown
    
    def get_unreconciled_claims(self, older_than_days: int = 7) -> List[Dict]:
        """Get claims that haven't been reconciled"""
        cutoff = datetime.now() - timedelta(days=older_than_days)
        
        unreconciled = []
        for claim in self.submitted_claims.values():
            if claim.submission_date < cutoff:
                age_days = (datetime.now() - claim.submission_date).days
                unreconciled.append({
                    "claim_id": claim.claim_id,
                    "rx_number": claim.rx_number,
                    "submission_date": claim.submission_date.isoformat(),
                    "age_days": age_days,
                    "submitted_amount": claim.submitted_amount,
                    "priority": "high" if age_days > 30 else "medium" if age_days > 14 else "normal"
                })
        
        return sorted(unreconciled, key=lambda x: x["age_days"], reverse=True)
    
    def export_discrepancies(self, severity_filter: Optional[str] = None) -> List[Dict]:
        """Export discrepancies for review"""
        export = []
        
        for result in self.reconciliation_results:
            if result.status != ReconciliationStatus.DISCREPANCY:
                continue
            
            for disc in result.discrepancies:
                if severity_filter and disc["severity"] != severity_filter:
                    continue
                
                export.append({
                    "claim_id": result.claim_record.claim_id if result.claim_record else "N/A",
                    "rx_number": result.claim_record.rx_number if result.claim_record else "N/A",
                    "discrepancy_type": disc["type"],
                    "description": disc["description"],
                    "severity": disc["severity"],
                    "amount_difference": result.amount_difference,
                    "reconciled_at": result.reconciled_at.isoformat(),
                    "details": disc
                })
        
        return export

# Example usage
if __name__ == "__main__":
    reconciler = RealTimeClaimReconciliation()
    
    # Register a claim
    claim_id = reconciler.register_claim({
        "claim_id": "CLM001",
        "rx_number": "RX12345",
        "ndc": "12345-678-90",
        "patient_id": "PT001",
        "submission_date": "2024-03-01T10:00:00",
        "submitted_amount": 125.50,
        "quantity": 30
    })
    
    # Register remittance
    remit_id = reconciler.register_remittance({
        "remittance_id": "REM001",
        "claim_id": "CLM001",
        "rx_number": "RX12345",
        "ndc": "12345-678-90",
        "patient_id": "PT001",
        "payment_date": "2024-03-02T14:00:00",
        "paid_amount": 118.00,
        "ingredient_cost": 100.00,
        "dispensing_fee": 18.00,
        "patient_pay": 10.00,
        "plan_pay": 108.00
    })
    
    summary = reconciler.get_reconciliation_summary()
    print(json.dumps(summary, indent=2))
