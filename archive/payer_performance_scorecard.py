"""
Payer Performance Scorecard - Comprehensive Payer Analysis & Benchmarking
Tracks reimbursement rates, denial patterns, and payment timeliness by payer
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict
import statistics

@dataclass
class PayerMetrics:
    payer_id: str
    payer_name: str
    total_claims: int
    approved_claims: int
    denied_claims: int
    pending_claims: int
    total_billed: float
    total_paid: float
    average_reimbursement_rate: float
    median_payment_days: int
    denial_rate: float
    underpayment_amount: float
    dir_fees_total: float

class PayerPerformanceScorecard:
    def __init__(self):
        self.payer_data: Dict[str, List[Dict]] = defaultdict(list)
        self.payer_info: Dict[str, Dict] = {}
        self.benchmarks = self._load_industry_benchmarks()
        self.scoring_weights = {
            "reimbursement_rate": 0.30,
            "denial_rate": 0.25,
            "payment_speed": 0.20,
            "underpayment_frequency": 0.15,
            "dir_fee_fairness": 0.10
        }
    
    def _load_industry_benchmarks(self) -> Dict:
        """Load industry benchmark data"""
        return {
            "reimbursement_rate": {
                "excellent": 95.0,
                "good": 90.0,
                "fair": 85.0,
                "poor": 80.0
            },
            "denial_rate": {
                "excellent": 5.0,
                "good": 10.0,
                "fair": 15.0,
                "poor": 20.0
            },
            "payment_days": {
                "excellent": 14,
                "good": 21,
                "fair": 30,
                "poor": 45
            },
            "dir_fee_percentage": {
                "excellent": 1.0,
                "good": 2.5,
                "fair": 4.0,
                "poor": 6.0
            }
        }
    
    def register_payer(self, payer_id: str, payer_name: str, metadata: Dict = None):
        """Register a payer in the system"""
        self.payer_info[payer_id] = {
            "payer_id": payer_id,
            "payer_name": payer_name,
            "registered_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
    
    def record_claim(self, payer_id: str, claim_data: Dict):
        """Record a claim for payer analysis"""
        claim_data["recorded_at"] = datetime.now().isoformat()
        self.payer_data[payer_id].append(claim_data)
    
    def calculate_payer_metrics(self, payer_id: str, days: int = 90) -> PayerMetrics:
        """Calculate comprehensive metrics for a payer"""
        cutoff = datetime.now() - timedelta(days=days)
        
        # Filter recent claims
        all_claims = self.payer_data.get(payer_id, [])
        recent_claims = [c for c in all_claims
                        if datetime.fromisoformat(c.get("date", datetime.now().isoformat())) >= cutoff]
        
        if not recent_claims:
            return None
        
        # Basic counts
        total_claims = len(recent_claims)
        approved = sum(1 for c in recent_claims if c.get("status") == "approved")
        denied = sum(1 for c in recent_claims if c.get("status") == "denied")
        pending = sum(1 for c in recent_claims if c.get("status") == "pending")
        
        # Financial metrics
        total_billed = sum(c.get("billed_amount", 0) for c in recent_claims)
        total_paid = sum(c.get("paid_amount", 0) for c in recent_claims if c.get("status") == "approved")
        
        avg_reimbursement = (total_paid / total_billed * 100) if total_billed > 0 else 0
        
        # Payment timing
        payment_days = [c.get("payment_days", 0) for c in recent_claims 
                       if c.get("status") == "approved" and c.get("payment_days")]
        median_days = statistics.median(payment_days) if payment_days else 0
        
        # Denial rate
        denial_rate = (denied / total_claims * 100) if total_claims > 0 else 0
        
        # Underpayment calculation
        underpayment = sum(
            max(0, c.get("expected_amount", 0) - c.get("paid_amount", 0))
            for c in recent_claims if c.get("status") == "approved"
        )
        
        # DIR fees
        dir_fees = sum(c.get("dir_fee", 0) for c in recent_claims)
        
        payer_name = self.payer_info.get(payer_id, {}).get("payer_name", payer_id)
        
        return PayerMetrics(
            payer_id=payer_id,
            payer_name=payer_name,
            total_claims=total_claims,
            approved_claims=approved,
            denied_claims=denied,
            pending_claims=pending,
            total_billed=total_billed,
            total_paid=total_paid,
            average_reimbursement_rate=avg_reimbursement,
            median_payment_days=int(median_days),
            denial_rate=denial_rate,
            underpayment_amount=underpayment,
            dir_fees_total=dir_fees
        )
    
    def generate_scorecard(self, payer_id: str, days: int = 90) -> Dict:
        """Generate comprehensive performance scorecard"""
        metrics = self.calculate_payer_metrics(payer_id, days)
        
        if not metrics:
            return {"error": "Insufficient data", "payer_id": payer_id}
        
        # Score each dimension
        scores = {
            "reimbursement_rate": self._score_reimbursement_rate(metrics.average_reimbursement_rate),
            "denial_rate": self._score_denial_rate(metrics.denial_rate),
            "payment_speed": self._score_payment_speed(metrics.median_payment_days),
            "underpayment": self._score_underpayment(metrics.underpayment_amount, metrics.total_billed),
            "dir_fees": self._score_dir_fees(metrics.dir_fees_total, metrics.total_paid)
        }
        
        # Calculate weighted overall score
        overall_score = sum(
            scores[dimension]["score"] * self.scoring_weights[dimension]
            for dimension in scores.keys()
        )
        
        # Determine grade
        grade = self._calculate_grade(overall_score)
        
        # Generate insights
        insights = self._generate_insights(metrics, scores)
        
        # Compare to industry benchmarks
        benchmark_comparison = self._compare_to_benchmarks(metrics)
        
        return {
            "payer_id": payer_id,
            "payer_name": metrics.payer_name,
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "overall_score": round(overall_score, 1),
            "grade": grade,
            "metrics": {
                "total_claims": metrics.total_claims,
                "approved_claims": metrics.approved_claims,
                "denied_claims": metrics.denied_claims,
                "approval_rate": round((metrics.approved_claims / metrics.total_claims * 100), 1),
                "total_billed": round(metrics.total_billed, 2),
                "total_paid": round(metrics.total_paid, 2),
                "reimbursement_rate": round(metrics.average_reimbursement_rate, 2),
                "median_payment_days": metrics.median_payment_days,
                "denial_rate": round(metrics.denial_rate, 2),
                "underpayment_amount": round(metrics.underpayment_amount, 2),
                "dir_fees_total": round(metrics.dir_fees_total, 2)
            },
            "dimension_scores": scores,
            "insights": insights,
            "benchmark_comparison": benchmark_comparison,
            "recommendations": self._generate_recommendations(metrics, scores)
        }
    
    def _score_reimbursement_rate(self, rate: float) -> Dict:
        """Score reimbursement rate"""
        benchmarks = self.benchmarks["reimbursement_rate"]
        
        if rate >= benchmarks["excellent"]:
            score = 100
            rating = "excellent"
        elif rate >= benchmarks["good"]:
            score = 85
            rating = "good"
        elif rate >= benchmarks["fair"]:
            score = 70
            rating = "fair"
        elif rate >= benchmarks["poor"]:
            score = 50
            rating = "poor"
        else:
            score = max(0, rate)
            rating = "very_poor"
        
        return {
            "score": score,
            "rating": rating,
            "value": round(rate, 2),
            "benchmark": benchmarks["good"]
        }
    
    def _score_denial_rate(self, rate: float) -> Dict:
        """Score denial rate (lower is better)"""
        benchmarks = self.benchmarks["denial_rate"]
        
        if rate <= benchmarks["excellent"]:
            score = 100
            rating = "excellent"
        elif rate <= benchmarks["good"]:
            score = 85
            rating = "good"
        elif rate <= benchmarks["fair"]:
            score = 70
            rating = "fair"
        elif rate <= benchmarks["poor"]:
            score = 50
            rating = "poor"
        else:
            score = max(0, 50 - (rate - benchmarks["poor"]))
            rating = "very_poor"
        
        return {
            "score": score,
            "rating": rating,
            "value": round(rate, 2),
            "benchmark": benchmarks["good"]
        }
    
    def _score_payment_speed(self, days: int) -> Dict:
        """Score payment speed (lower is better)"""
        benchmarks = self.benchmarks["payment_days"]
        
        if days <= benchmarks["excellent"]:
            score = 100
            rating = "excellent"
        elif days <= benchmarks["good"]:
            score = 85
            rating = "good"
        elif days <= benchmarks["fair"]:
            score = 70
            rating = "fair"
        elif days <= benchmarks["poor"]:
            score = 50
            rating = "poor"
        else:
            score = max(0, 50 - (days - benchmarks["poor"]))
            rating = "very_poor"
        
        return {
            "score": score,
            "rating": rating,
            "value": days,
            "benchmark": benchmarks["good"]
        }
    
    def _score_underpayment(self, underpayment: float, total_billed: float) -> Dict:
        """Score underpayment frequency"""
        if total_billed == 0:
            return {"score": 100, "rating": "excellent", "value": 0, "benchmark": 0}
        
        underpayment_pct = (underpayment / total_billed) * 100
        
        # Lower underpayment is better
        if underpayment_pct <= 1:
            score = 100
            rating = "excellent"
        elif underpayment_pct <= 3:
            score = 85
            rating = "good"
        elif underpayment_pct <= 5:
            score = 70
            rating = "fair"
        elif underpayment_pct <= 8:
            score = 50
            rating = "poor"
        else:
            score = max(0, 50 - (underpayment_pct - 8) * 5)
            rating = "very_poor"
        
        return {
            "score": score,
            "rating": rating,
            "value": round(underpayment_pct, 2),
            "benchmark": 2.0
        }
    
    def _score_dir_fees(self, dir_fees: float, total_paid: float) -> Dict:
        """Score DIR fees fairness"""
        if total_paid == 0:
            return {"score": 100, "rating": "excellent", "value": 0, "benchmark": 0}
        
        dir_fee_pct = (dir_fees / total_paid) * 100
        benchmarks = self.benchmarks["dir_fee_percentage"]
        
        if dir_fee_pct <= benchmarks["excellent"]:
            score = 100
            rating = "excellent"
        elif dir_fee_pct <= benchmarks["good"]:
            score = 85
            rating = "good"
        elif dir_fee_pct <= benchmarks["fair"]:
            score = 70
            rating = "fair"
        elif dir_fee_pct <= benchmarks["poor"]:
            score = 50
            rating = "poor"
        else:
            score = max(0, 50 - (dir_fee_pct - benchmarks["poor"]) * 5)
            rating = "very_poor"
        
        return {
            "score": score,
            "rating": rating,
            "value": round(dir_fee_pct, 2),
            "benchmark": benchmarks["good"]
        }
    
    def _calculate_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_insights(self, metrics: PayerMetrics, scores: Dict) -> List[str]:
        """Generate actionable insights"""
        insights = []
        
        # Reimbursement insights
        if scores["reimbursement_rate"]["rating"] in ["poor", "very_poor"]:
            insights.append(f"Reimbursement rate ({metrics.average_reimbursement_rate:.1f}%) is below industry standards")
        
        # Denial insights
        if scores["denial_rate"]["rating"] in ["poor", "very_poor"]:
            insights.append(f"High denial rate ({metrics.denial_rate:.1f}%) indicates potential issues with claims submission or payer policies")
        
        # Payment speed insights
        if scores["payment_speed"]["rating"] in ["poor", "very_poor"]:
            insights.append(f"Slow payment processing ({metrics.median_payment_days} days) impacts cash flow")
        
        # Underpayment insights
        if metrics.underpayment_amount > 1000:
            insights.append(f"Significant underpayment detected (${metrics.underpayment_amount:.2f} total)")
        
        # DIR fee insights
        dir_fee_pct = (metrics.dir_fees_total / metrics.total_paid * 100) if metrics.total_paid > 0 else 0
        if dir_fee_pct > 3:
            insights.append(f"High DIR fees ({dir_fee_pct:.1f}% of reimbursement) reducing actual payment")
        
        if not insights:
            insights.append("Payer performance is within acceptable ranges")
        
        return insights
    
    def _compare_to_benchmarks(self, metrics: PayerMetrics) -> Dict:
        """Compare metrics to industry benchmarks"""
        return {
            "reimbursement_rate": {
                "value": round(metrics.average_reimbursement_rate, 2),
                "benchmark": self.benchmarks["reimbursement_rate"]["good"],
                "vs_benchmark": round(metrics.average_reimbursement_rate - self.benchmarks["reimbursement_rate"]["good"], 2)
            },
            "denial_rate": {
                "value": round(metrics.denial_rate, 2),
                "benchmark": self.benchmarks["denial_rate"]["good"],
                "vs_benchmark": round(metrics.denial_rate - self.benchmarks["denial_rate"]["good"], 2)
            },
            "payment_days": {
                "value": metrics.median_payment_days,
                "benchmark": self.benchmarks["payment_days"]["good"],
                "vs_benchmark": metrics.median_payment_days - self.benchmarks["payment_days"]["good"]
            }
        }
    
    def _generate_recommendations(self, metrics: PayerMetrics, scores: Dict) -> List[Dict]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if scores["denial_rate"]["rating"] in ["poor", "very_poor"]:
            recommendations.append({
                "priority": "high",
                "category": "denials",
                "action": "Review denial reasons and implement corrective measures",
                "expected_impact": "Reduce denial rate by 5-10 percentage points"
            })
        
        if scores["payment_speed"]["rating"] in ["poor", "very_poor"]:
            recommendations.append({
                "priority": "medium",
                "category": "cash_flow",
                "action": "Contact payer to discuss payment processing delays",
                "expected_impact": "Improve cash flow timing"
            })
        
        if metrics.underpayment_amount > 5000:
            recommendations.append({
                "priority": "high",
                "category": "revenue_recovery",
                "action": "Submit appeals for underpaid claims",
                "expected_impact": f"Potential recovery of ${metrics.underpayment_amount:.2f}"
            })
        
        if scores["dir_fees"]["rating"] in ["poor", "very_poor"]:
            recommendations.append({
                "priority": "medium",
                "category": "contract_negotiation",
                "action": "Renegotiate DIR fee terms with payer",
                "expected_impact": "Reduce effective DIR fees by 1-2%"
            })
        
        return recommendations
    
    def compare_payers(self, days: int = 90) -> List[Dict]:
        """Compare all payers"""
        comparisons = []
        
        for payer_id in self.payer_data.keys():
            scorecard = self.generate_scorecard(payer_id, days)
            if "error" not in scorecard:
                comparisons.append({
                    "payer_id": payer_id,
                    "payer_name": scorecard["payer_name"],
                    "overall_score": scorecard["overall_score"],
                    "grade": scorecard["grade"],
                    "total_paid": scorecard["metrics"]["total_paid"],
                    "reimbursement_rate": scorecard["metrics"]["reimbursement_rate"],
                    "denial_rate": scorecard["metrics"]["denial_rate"]
                })
        
        # Sort by overall score
        comparisons.sort(key=lambda x: x["overall_score"], reverse=True)
        
        return comparisons

# Example usage
if __name__ == "__main__":
    scorecard = PayerPerformanceScorecard()
    
    # Register payers
    scorecard.register_payer("PAY001", "Blue Cross Blue Shield")
    scorecard.register_payer("PAY002", "UnitedHealthcare")
    
    # Record sample claims
    for i in range(100):
        scorecard.record_claim("PAY001", {
            "claim_id": f"CLM{i}",
            "date": (datetime.now() - timedelta(days=i % 30)).isoformat(),
            "status": "approved" if i % 10 != 0 else "denied",
            "billed_amount": 100.0,
            "paid_amount": 92.0 if i % 10 != 0 else 0,
            "expected_amount": 95.0,
            "payment_days": 18 + (i % 10),
            "dir_fee": 2.5
        })
    
    report = scorecard.generate_scorecard("PAY001")
    print(json.dumps(report, indent=2))
