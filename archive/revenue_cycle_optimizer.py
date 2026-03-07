"""
Revenue Cycle Optimization Engine for GetPaidRx
Optimizes the complete pharmacy revenue cycle from claim submission to collection
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import statistics


class ClaimStatus(Enum):
    """Claim lifecycle status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PAID = "paid"
    DENIED = "denied"
    APPEALED = "appealed"
    REVERSED = "reversed"


@dataclass
class RevenueClaim:
    """Claim for revenue cycle tracking"""
    claim_id: str
    rx_number: str
    submission_date: str
    status: ClaimStatus
    submitted_amount: float
    paid_amount: float
    payer: str
    days_to_payment: Optional[int] = None
    denial_reason: Optional[str] = None
    reversal_reason: Optional[str] = None


class RevenueCycleOptimizer:
    """
    Complete revenue cycle optimization:
    - Days Sales Outstanding (DSO) tracking
    - Denial rate analysis and prevention
    - Collection efficiency monitoring
    - Cash flow forecasting
    - Payer payment speed analysis
    """
    
    def __init__(self):
        self.claims: List[RevenueClaim] = []
    
    def add_claim(self, claim: RevenueClaim):
        """Add claim to revenue cycle tracking"""
        self.claims.append(claim)
    
    def calculate_dso(self, days: int = 90) -> Dict[str, Any]:
        """
        Calculate Days Sales Outstanding (DSO)
        
        Args:
            days: Analysis period in days
        
        Returns:
            DSO metrics and trends
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_claims = [
            c for c in self.claims
            if datetime.fromisoformat(c.submission_date) > cutoff
        ]
        
        paid_claims = [c for c in recent_claims if c.status == ClaimStatus.PAID and c.days_to_payment]
        
        if not paid_claims:
            return {"message": "No paid claims in period for DSO calculation"}
        
        # Calculate DSO metrics
        days_to_payment = [c.days_to_payment for c in paid_claims]
        avg_dso = statistics.mean(days_to_payment)
        median_dso = statistics.median(days_to_payment)
        
        # Industry benchmark: 25-35 days for pharmacy
        benchmark_dso = 30
        variance = avg_dso - benchmark_dso
        
        # Categorize performance
        if avg_dso <= 25:
            performance = "excellent"
        elif avg_dso <= 35:
            performance = "good"
        elif avg_dso <= 45:
            performance = "fair"
        else:
            performance = "poor"
        
        # Calculate tied-up capital
        total_revenue = sum(c.paid_amount for c in paid_claims)
        daily_revenue = total_revenue / days
        tied_up_capital = daily_revenue * avg_dso
        
        # Potential savings if we hit benchmark
        if variance > 0:
            potential_savings = daily_revenue * variance
        else:
            potential_savings = 0
        
        return {
            "analysis_period_days": days,
            "total_paid_claims": len(paid_claims),
            "dso_metrics": {
                "average_days": round(avg_dso, 1),
                "median_days": round(median_dso, 1),
                "min_days": min(days_to_payment),
                "max_days": max(days_to_payment),
                "benchmark_days": benchmark_dso,
                "variance_from_benchmark": round(variance, 1)
            },
            "performance": performance,
            "financial_impact": {
                "daily_revenue": round(daily_revenue, 2),
                "tied_up_capital": round(tied_up_capital, 2),
                "potential_savings": round(potential_savings, 2)
            },
            "generated_at": datetime.now().isoformat()
        }
    
    def analyze_denial_rates(self) -> Dict[str, Any]:
        """
        Comprehensive denial rate analysis
        
        Returns:
            Denial metrics, trends, and root causes
        """
        if not self.claims:
            return {"message": "No claims to analyze"}
        
        total_claims = len(self.claims)
        denied_claims = [c for c in self.claims if c.status == ClaimStatus.DENIED]
        denial_rate = (len(denied_claims) / total_claims) * 100
        
        # Industry benchmark: 5-10% denial rate
        benchmark_denial_rate = 7.5
        
        # Categorize denial reasons
        denial_reasons = {}
        for claim in denied_claims:
            reason = claim.denial_reason or "unknown"
            denial_reasons[reason] = denial_reasons.get(reason, 0) + 1
        
        # Top denial reasons
        top_reasons = sorted(
            denial_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Calculate financial impact
        denied_revenue = sum(c.submitted_amount for c in denied_claims)
        
        # Group by payer
        payer_denials = {}
        for claim in denied_claims:
            payer_denials[claim.payer] = payer_denials.get(claim.payer, 0) + 1
        
        return {
            "overall_metrics": {
                "total_claims": total_claims,
                "denied_claims": len(denied_claims),
                "denial_rate_pct": round(denial_rate, 2),
                "benchmark_rate_pct": benchmark_denial_rate,
                "performance": "good" if denial_rate <= benchmark_denial_rate else "needs_improvement"
            },
            "financial_impact": {
                "denied_revenue": round(denied_revenue, 2),
                "avg_denied_amount": round(denied_revenue / len(denied_claims), 2) if denied_claims else 0
            },
            "top_denial_reasons": [
                {
                    "reason": reason,
                    "count": count,
                    "percentage": round(count / len(denied_claims) * 100, 2)
                }
                for reason, count in top_reasons
            ],
            "payer_breakdown": [
                {
                    "payer": payer,
                    "denials": count,
                    "percentage": round(count / len(denied_claims) * 100, 2)
                }
                for payer, count in sorted(payer_denials.items(), key=lambda x: x[1], reverse=True)[:10]
            ],
            "recommendations": self._generate_denial_recommendations(top_reasons),
            "generated_at": datetime.now().isoformat()
        }
    
    def analyze_collection_efficiency(self, days: int = 90) -> Dict[str, Any]:
        """
        Calculate collection efficiency and effectiveness
        
        Args:
            days: Analysis period
        
        Returns:
            Collection metrics and trends
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_claims = [
            c for c in self.claims
            if datetime.fromisoformat(c.submission_date) > cutoff
        ]
        
        if not recent_claims:
            return {"message": "No claims in analysis period"}
        
        # Calculate collection rate
        total_submitted = sum(c.submitted_amount for c in recent_claims)
        total_collected = sum(c.paid_amount for c in recent_claims if c.status == ClaimStatus.PAID)
        
        collection_rate = (total_collected / total_submitted) * 100 if total_submitted > 0 else 0
        
        # Industry benchmark: 98%+ collection rate
        benchmark_rate = 98.0
        
        # Calculate write-offs
        denied_not_appealed = [
            c for c in recent_claims 
            if c.status == ClaimStatus.DENIED
        ]
        write_off_amount = sum(c.submitted_amount for c in denied_not_appealed)
        
        # Calculate reversals impact
        reversed_claims = [c for c in recent_claims if c.status == ClaimStatus.REVERSED]
        reversal_amount = sum(c.paid_amount for c in reversed_claims)
        
        return {
            "analysis_period_days": days,
            "collection_metrics": {
                "total_submitted": round(total_submitted, 2),
                "total_collected": round(total_collected, 2),
                "collection_rate_pct": round(collection_rate, 2),
                "benchmark_rate_pct": benchmark_rate,
                "variance_from_benchmark": round(collection_rate - benchmark_rate, 2)
            },
            "write_offs": {
                "total_claims": len(denied_not_appealed),
                "total_amount": round(write_off_amount, 2),
                "write_off_rate_pct": round(write_off_amount / total_submitted * 100, 2) if total_submitted > 0 else 0
            },
            "reversals": {
                "total_claims": len(reversed_claims),
                "total_amount": round(reversal_amount, 2),
                "reversal_rate_pct": round(len(reversed_claims) / len(recent_claims) * 100, 2)
            },
            "performance": "excellent" if collection_rate >= benchmark_rate else "needs_improvement",
            "generated_at": datetime.now().isoformat()
        }
    
    def analyze_payer_payment_speed(self) -> Dict[str, Any]:
        """
        Analyze payment speed by payer
        
        Returns:
            Payer payment speed rankings
        """
        payer_metrics = {}
        
        for claim in self.claims:
            if claim.status != ClaimStatus.PAID or not claim.days_to_payment:
                continue
            
            if claim.payer not in payer_metrics:
                payer_metrics[claim.payer] = {
                    "payment_days": [],
                    "total_paid": 0,
                    "claim_count": 0
                }
            
            payer_metrics[claim.payer]["payment_days"].append(claim.days_to_payment)
            payer_metrics[claim.payer]["total_paid"] += claim.paid_amount
            payer_metrics[claim.payer]["claim_count"] += 1
        
        # Calculate rankings
        payer_rankings = []
        
        for payer, metrics in payer_metrics.items():
            if metrics["claim_count"] < 5:  # Minimum sample size
                continue
            
            avg_days = statistics.mean(metrics["payment_days"])
            median_days = statistics.median(metrics["payment_days"])
            
            # Score: faster = better
            # Industry avg is ~30 days
            score = max(0, 100 - (avg_days - 30) * 2)
            
            payer_rankings.append({
                "payer": payer,
                "avg_days_to_payment": round(avg_days, 1),
                "median_days_to_payment": round(median_days, 1),
                "min_days": min(metrics["payment_days"]),
                "max_days": max(metrics["payment_days"]),
                "total_claims": metrics["claim_count"],
                "total_paid": round(metrics["total_paid"], 2),
                "speed_score": round(score, 1),
                "rating": "fast" if avg_days <= 20 else "average" if avg_days <= 40 else "slow"
            })
        
        payer_rankings.sort(key=lambda x: x["avg_days_to_payment"])
        
        return {
            "total_payers": len(payer_rankings),
            "rankings": payer_rankings,
            "fastest_payer": payer_rankings[0]["payer"] if payer_rankings else None,
            "slowest_payer": payer_rankings[-1]["payer"] if payer_rankings else None,
            "generated_at": datetime.now().isoformat()
        }
    
    def forecast_cash_flow(self, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Forecast cash flow based on pending claims
        
        Args:
            days_ahead: Forecast horizon in days
        
        Returns:
            Cash flow forecast
        """
        # Get pending claims
        pending_claims = [c for c in self.claims if c.status == ClaimStatus.SUBMITTED]
        
        if not pending_claims:
            return {"message": "No pending claims to forecast"}
        
        # Calculate average days to payment from historical data
        paid_claims = [c for c in self.claims if c.status == ClaimStatus.PAID and c.days_to_payment]
        
        if not paid_claims:
            avg_payment_days = 30  # Default assumption
        else:
            avg_payment_days = statistics.mean([c.days_to_payment for c in paid_claims])
        
        # Forecast expected cash inflow
        expected_inflow = 0
        for claim in pending_claims:
            days_pending = (datetime.now() - datetime.fromisoformat(claim.submission_date)).days
            expected_payment_date = datetime.fromisoformat(claim.submission_date) + timedelta(days=avg_payment_days)
            
            if expected_payment_date <= datetime.now() + timedelta(days=days_ahead):
                # Apply historical collection rate (default 98%)
                expected_inflow += claim.submitted_amount * 0.98
        
        return {
            "forecast_horizon_days": days_ahead,
            "pending_claims": len(pending_claims),
            "total_pending_amount": round(sum(c.submitted_amount for c in pending_claims), 2),
            "expected_inflow": round(expected_inflow, 2),
            "avg_days_to_payment": round(avg_payment_days, 1),
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_denial_recommendations(self, top_reasons: List[tuple]) -> List[str]:
        """Generate recommendations based on top denial reasons"""
        recommendations = []
        
        if not top_reasons:
            return ["Maintain current claim submission practices"]
        
        top_reason = top_reasons[0][0].lower()
        
        if "eligibility" in top_reason or "coverage" in top_reason:
            recommendations.append("Implement real-time eligibility verification at POS")
            recommendations.append("Update patient insurance information before each fill")
        
        if "prior auth" in top_reason or "authorization" in top_reason:
            recommendations.append("Establish prior authorization tracking system")
            recommendations.append("Proactively obtain authorizations for high-risk drugs")
        
        if "ndc" in top_reason or "drug" in top_reason:
            recommendations.append("Verify NDC codes against payer formularies before submission")
            recommendations.append("Update drug database regularly")
        
        if "duplicate" in top_reason:
            recommendations.append("Implement duplicate claim detection before submission")
            recommendations.append("Review claim submission workflow for redundancies")
        
        recommendations.append("Consider denial management automation software")
        recommendations.append(f"Focus on top denial reason: {top_reasons[0][0]}")
        
        return recommendations


# Example usage:
# optimizer = RevenueCycleOptimizer()
# optimizer.add_claim(RevenueClaim(...))
# dso = optimizer.calculate_dso(days=90)
# denials = optimizer.analyze_denial_rates()
# collection = optimizer.analyze_collection_efficiency()
# speed = optimizer.analyze_payer_payment_speed()
# forecast = optimizer.forecast_cash_flow(days_ahead=30)
