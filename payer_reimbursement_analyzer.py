"""
Payer Reimbursement Analyzer for GetPaidRx
Analyzes reimbursement patterns across payers to identify underpayment trends
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics


@dataclass
class ReimbursementClaim:
    """Single claim reimbursement record"""
    claim_id: str
    payer: str
    drug_ndc: str
    drug_name: str
    quantity: float
    days_supply: int
    submitted_amount: float
    paid_amount: float
    contracted_rate: Optional[float]
    adjudication_date: str
    reject_code: Optional[str] = None


class PayerReimbursementAnalyzer:
    """
    Comprehensive payer reimbursement analysis to detect:
    - Systematic underpayment patterns
    - Payer-specific trends
    - Drug-level reimbursement adequacy
    - Time-based payment degradation
    """
    
    def __init__(self):
        self.claims: List[ReimbursementClaim] = []
        self.payer_profiles: Dict[str, Dict] = {}
    
    def add_claim(self, claim: ReimbursementClaim):
        """Add a claim to analysis dataset"""
        self.claims.append(claim)
    
    def analyze_payer_performance(self, days: int = 90) -> Dict[str, Any]:
        """
        Analyze overall payer performance
        
        Args:
            days: Analysis window in days
        
        Returns:
            Payer performance metrics
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_claims = [
            c for c in self.claims
            if datetime.fromisoformat(c.adjudication_date) > cutoff
        ]
        
        if not recent_claims:
            return {"message": "No claims in analysis period"}
        
        # Group by payer
        payer_data = {}
        
        for claim in recent_claims:
            if claim.payer not in payer_data:
                payer_data[claim.payer] = {
                    "claims": [],
                    "total_submitted": 0,
                    "total_paid": 0,
                    "underpaid_claims": 0,
                    "rejected_claims": 0
                }
            
            payer_data[claim.payer]["claims"].append(claim)
            payer_data[claim.payer]["total_submitted"] += claim.submitted_amount
            payer_data[claim.payer]["total_paid"] += claim.paid_amount
            
            # Check for underpayment (>5% variance)
            if claim.paid_amount < claim.submitted_amount * 0.95:
                payer_data[claim.payer]["underpaid_claims"] += 1
            
            if claim.reject_code:
                payer_data[claim.payer]["rejected_claims"] += 1
        
        # Calculate payer rankings
        payer_rankings = []
        
        for payer, data in payer_data.items():
            total_claims = len(data["claims"])
            reimbursement_rate = (data["total_paid"] / data["total_submitted"]) * 100
            underpayment_rate = (data["underpaid_claims"] / total_claims) * 100
            rejection_rate = (data["rejected_claims"] / total_claims) * 100
            
            # Calculate performance score (0-100)
            # Higher reimbursement rate + lower underpayment/rejection = higher score
            performance_score = (
                (reimbursement_rate * 0.5) +
                ((100 - underpayment_rate) * 0.3) +
                ((100 - rejection_rate) * 0.2)
            )
            
            # Assign grade
            if performance_score >= 90:
                grade = "A"
            elif performance_score >= 80:
                grade = "B"
            elif performance_score >= 70:
                grade = "C"
            elif performance_score >= 60:
                grade = "D"
            else:
                grade = "F"
            
            payer_rankings.append({
                "payer": payer,
                "total_claims": total_claims,
                "total_submitted": round(data["total_submitted"], 2),
                "total_paid": round(data["total_paid"], 2),
                "reimbursement_rate_pct": round(reimbursement_rate, 2),
                "underpayment_rate_pct": round(underpayment_rate, 2),
                "rejection_rate_pct": round(rejection_rate, 2),
                "performance_score": round(performance_score, 2),
                "grade": grade,
                "estimated_lost_revenue": round(data["total_submitted"] - data["total_paid"], 2)
            })
        
        # Sort by performance score
        payer_rankings.sort(key=lambda x: x["performance_score"], reverse=True)
        
        return {
            "analysis_period_days": days,
            "total_payers": len(payer_rankings),
            "total_claims": len(recent_claims),
            "payer_rankings": payer_rankings,
            "generated_at": datetime.now().isoformat()
        }
    
    def detect_underpayment_patterns(self) -> Dict[str, Any]:
        """
        Detect systematic underpayment patterns
        
        Returns:
            Patterns and anomalies in underpayment
        """
        if not self.claims:
            return {"message": "No claims to analyze"}
        
        patterns = []
        
        # Pattern 1: Specific drug always underpaid
        drug_underpayment = {}
        for claim in self.claims:
            key = f"{claim.drug_name} ({claim.drug_ndc})"
            if key not in drug_underpayment:
                drug_underpayment[key] = {"underpaid": 0, "total": 0, "variance": []}
            
            drug_underpayment[key]["total"] += 1
            variance = claim.paid_amount - claim.submitted_amount
            drug_underpayment[key]["variance"].append(variance)
            
            if variance < -5:  # More than $5 underpaid
                drug_underpayment[key]["underpaid"] += 1
        
        # Find drugs with >50% underpayment rate
        for drug, data in drug_underpayment.items():
            if data["total"] >= 5:  # Minimum sample size
                underpayment_rate = (data["underpaid"] / data["total"]) * 100
                if underpayment_rate > 50:
                    avg_variance = statistics.mean(data["variance"])
                    patterns.append({
                        "type": "drug_systematic_underpayment",
                        "drug": drug,
                        "underpayment_rate_pct": round(underpayment_rate, 2),
                        "avg_underpayment_amount": round(abs(avg_variance), 2),
                        "total_claims": data["total"],
                        "severity": "high" if underpayment_rate > 75 else "medium"
                    })
        
        # Pattern 2: Payer underpays specific class
        payer_drug_combos = {}
        for claim in self.claims:
            key = f"{claim.payer}|{claim.drug_name}"
            if key not in payer_drug_combos:
                payer_drug_combos[key] = {"underpaid": 0, "total": 0}
            
            payer_drug_combos[key]["total"] += 1
            if claim.paid_amount < claim.submitted_amount * 0.95:
                payer_drug_combos[key]["underpaid"] += 1
        
        for combo, data in payer_drug_combos.items():
            if data["total"] >= 3:
                underpayment_rate = (data["underpaid"] / data["total"]) * 100
                if underpayment_rate > 66:
                    payer, drug = combo.split("|")
                    patterns.append({
                        "type": "payer_drug_specific",
                        "payer": payer,
                        "drug": drug,
                        "underpayment_rate_pct": round(underpayment_rate, 2),
                        "total_claims": data["total"],
                        "severity": "high"
                    })
        
        # Pattern 3: Trending worse over time
        # Sort claims by date
        sorted_claims = sorted(self.claims, key=lambda c: c.adjudication_date)
        
        if len(sorted_claims) >= 30:
            # Compare first 30% to last 30%
            early_chunk = sorted_claims[:len(sorted_claims)//3]
            late_chunk = sorted_claims[-len(sorted_claims)//3:]
            
            early_rate = sum(c.paid_amount / c.submitted_amount for c in early_chunk if c.submitted_amount > 0) / len(early_chunk)
            late_rate = sum(c.paid_amount / c.submitted_amount for c in late_chunk if c.submitted_amount > 0) / len(late_chunk)
            
            degradation_pct = ((early_rate - late_rate) / early_rate) * 100
            
            if degradation_pct > 5:
                patterns.append({
                    "type": "temporal_degradation",
                    "early_reimbursement_rate_pct": round(early_rate * 100, 2),
                    "recent_reimbursement_rate_pct": round(late_rate * 100, 2),
                    "degradation_pct": round(degradation_pct, 2),
                    "severity": "high" if degradation_pct > 10 else "medium"
                })
        
        return {
            "total_patterns_detected": len(patterns),
            "patterns": patterns,
            "generated_at": datetime.now().isoformat()
        }
    
    def generate_appeal_targets(self, min_recovery: float = 100) -> Dict[str, Any]:
        """
        Identify best targets for appeal/recovery
        
        Args:
            min_recovery: Minimum recovery amount to flag
        
        Returns:
            Prioritized appeal targets
        """
        appeal_targets = []
        
        for claim in self.claims:
            underpayment = claim.submitted_amount - claim.paid_amount
            
            if underpayment >= min_recovery:
                # Calculate appeal priority score
                # Higher underpayment + recent date = higher priority
                days_old = (datetime.now() - datetime.fromisoformat(claim.adjudication_date)).days
                recency_score = max(0, 100 - days_old)  # Newer = higher score
                amount_score = min(100, underpayment)   # Up to $100
                
                priority_score = (recency_score * 0.4) + (amount_score * 0.6)
                
                appeal_targets.append({
                    "claim_id": claim.claim_id,
                    "payer": claim.payer,
                    "drug_name": claim.drug_name,
                    "adjudication_date": claim.adjudication_date,
                    "days_old": days_old,
                    "submitted": round(claim.submitted_amount, 2),
                    "paid": round(claim.paid_amount, 2),
                    "underpayment": round(underpayment, 2),
                    "priority_score": round(priority_score, 2),
                    "appeal_deadline": (datetime.fromisoformat(claim.adjudication_date) + timedelta(days=365)).isoformat()
                })
        
        # Sort by priority score
        appeal_targets.sort(key=lambda x: x["priority_score"], reverse=True)
        
        total_recovery_potential = sum(t["underpayment"] for t in appeal_targets)
        
        return {
            "total_appeal_opportunities": len(appeal_targets),
            "total_recovery_potential": round(total_recovery_potential, 2),
            "top_targets": appeal_targets[:50],  # Top 50 targets
            "generated_at": datetime.now().isoformat()
        }
    
    def benchmark_against_contracted_rates(self) -> Dict[str, Any]:
        """
        Compare actual reimbursement vs contracted rates
        
        Returns:
            Contract compliance analysis
        """
        contract_variances = []
        
        for claim in self.claims:
            if claim.contracted_rate:
                expected_payment = claim.contracted_rate * claim.quantity
                actual_payment = claim.paid_amount
                variance = actual_payment - expected_payment
                variance_pct = (variance / expected_payment) * 100 if expected_payment > 0 else 0
                
                # Flag significant variances (>5%)
                if abs(variance_pct) > 5:
                    contract_variances.append({
                        "claim_id": claim.claim_id,
                        "payer": claim.payer,
                        "drug_name": claim.drug_name,
                        "expected_payment": round(expected_payment, 2),
                        "actual_payment": round(actual_payment, 2),
                        "variance": round(variance, 2),
                        "variance_pct": round(variance_pct, 2),
                        "compliance_issue": "underpaid" if variance < 0 else "overpaid"
                    })
        
        contract_variances.sort(key=lambda x: abs(x["variance"]), reverse=True)
        
        total_variance = sum(v["variance"] for v in contract_variances)
        
        return {
            "total_variances": len(contract_variances),
            "total_variance_amount": round(total_variance, 2),
            "underpaid_claims": len([v for v in contract_variances if v["variance"] < 0]),
            "overpaid_claims": len([v for v in contract_variances if v["variance"] > 0]),
            "top_variances": contract_variances[:30],
            "generated_at": datetime.now().isoformat()
        }


# Example usage:
# analyzer = PayerReimbursementAnalyzer()
# analyzer.add_claim(ReimbursementClaim(...))
# performance = analyzer.analyze_payer_performance(days=90)
# patterns = analyzer.detect_underpayment_patterns()
# appeals = analyzer.generate_appeal_targets(min_recovery=50)
