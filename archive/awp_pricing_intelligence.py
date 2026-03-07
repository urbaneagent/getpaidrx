"""
AWP Pricing Intelligence Engine for GetPaidRx
Tracks Average Wholesale Price changes and optimizes acquisition strategies
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics


@dataclass
class AWPDataPoint:
    """Single AWP price point"""
    ndc: str
    drug_name: str
    manufacturer: str
    package_size: str
    awp_per_unit: float
    effective_date: str
    source: str  # First DataBank, Medispan, etc


@dataclass
class AcquisitionCost:
    """Actual acquisition cost"""
    ndc: str
    drug_name: str
    wholesaler: str
    cost_per_unit: float
    purchase_date: str
    quantity: int


class AWPPricingIntelligence:
    """
    AWP pricing intelligence for:
    - AWP change tracking and alerts
    - Acquisition cost optimization
    - Wholesaler comparison
    - Brand-generic arbitrage detection
    """
    
    def __init__(self):
        self.awp_history: Dict[str, List[AWPDataPoint]] = {}
        self.acquisition_costs: List[AcquisitionCost] = []
        self.wholesalers: Dict[str, Dict] = {}
    
    def add_awp_price(self, price_point: AWPDataPoint):
        """Record an AWP price point"""
        if price_point.ndc not in self.awp_history:
            self.awp_history[price_point.ndc] = []
        
        self.awp_history[price_point.ndc].append(price_point)
        
        # Sort by effective date
        self.awp_history[price_point.ndc].sort(
            key=lambda x: x.effective_date,
            reverse=True
        )
    
    def add_acquisition_cost(self, cost: AcquisitionCost):
        """Record an actual acquisition cost"""
        self.acquisition_costs.append(cost)
    
    def detect_awp_changes(self, days: int = 30, threshold_pct: float = 5.0) -> Dict[str, Any]:
        """
        Detect significant AWP changes
        
        Args:
            days: Lookback period in days
            threshold_pct: Minimum % change to flag
        
        Returns:
            AWP changes report
        """
        cutoff = datetime.now() - timedelta(days=days)
        changes = []
        
        for ndc, history in self.awp_history.items():
            if len(history) < 2:
                continue
            
            # Compare most recent to previous
            current = history[0]
            previous = history[1]
            
            # Check if change is within analysis window
            if datetime.fromisoformat(current.effective_date) < cutoff:
                continue
            
            change_amount = current.awp_per_unit - previous.awp_per_unit
            change_pct = (change_amount / previous.awp_per_unit) * 100
            
            if abs(change_pct) >= threshold_pct:
                # Determine impact
                if change_pct > 0:
                    impact = "increase"
                    severity = "high" if change_pct > 15 else "medium"
                else:
                    impact = "decrease"
                    severity = "opportunity"  # Price decreases are opportunities
                
                changes.append({
                    "ndc": ndc,
                    "drug_name": current.drug_name,
                    "manufacturer": current.manufacturer,
                    "previous_awp": round(previous.awp_per_unit, 2),
                    "current_awp": round(current.awp_per_unit, 2),
                    "change_amount": round(change_amount, 2),
                    "change_pct": round(change_pct, 2),
                    "impact": impact,
                    "severity": severity,
                    "effective_date": current.effective_date
                })
        
        # Sort by absolute change %
        changes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        
        return {
            "analysis_period_days": days,
            "total_changes_detected": len(changes),
            "increases": len([c for c in changes if c["impact"] == "increase"]),
            "decreases": len([c for c in changes if c["impact"] == "decrease"]),
            "changes": changes,
            "generated_at": datetime.now().isoformat()
        }
    
    def analyze_awp_to_aac_spread(self) -> Dict[str, Any]:
        """
        Analyze spread between AWP and Actual Acquisition Cost (AAC)
        
        Returns:
            AWP-to-AAC analysis with optimization opportunities
        """
        spread_analysis = []
        
        for cost in self.acquisition_costs:
            # Find corresponding AWP
            awp_history = self.awp_history.get(cost.ndc)
            if not awp_history:
                continue
            
            # Get AWP at time of purchase
            purchase_date = datetime.fromisoformat(cost.purchase_date)
            awp_at_purchase = None
            
            for awp in awp_history:
                if datetime.fromisoformat(awp.effective_date) <= purchase_date:
                    awp_at_purchase = awp.awp_per_unit
                    break
            
            if not awp_at_purchase:
                continue
            
            # Calculate spread
            spread = cost.cost_per_unit - awp_at_purchase
            spread_pct = (spread / awp_at_purchase) * 100
            
            # Standard pharmacy spread benchmark: AWP -18% to -20%
            target_spread_pct = -19.0
            variance_from_target = spread_pct - target_spread_pct
            
            # Flag if not achieving target spread
            if variance_from_target > 5:  # More than 5% off target
                status = "poor_spread"
                opportunity = abs(variance_from_target) * awp_at_purchase / 100
            elif variance_from_target < -5:
                status = "exceptional_spread"
                opportunity = 0
            else:
                status = "target_spread"
                opportunity = 0
            
            spread_analysis.append({
                "ndc": cost.ndc,
                "drug_name": cost.drug_name,
                "wholesaler": cost.wholesaler,
                "awp": round(awp_at_purchase, 2),
                "aac": round(cost.cost_per_unit, 2),
                "spread_pct": round(spread_pct, 2),
                "target_spread_pct": target_spread_pct,
                "variance_from_target": round(variance_from_target, 2),
                "status": status,
                "potential_savings_per_unit": round(opportunity, 2),
                "purchase_quantity": cost.quantity,
                "total_opportunity": round(opportunity * cost.quantity, 2)
            })
        
        # Sort by total opportunity
        spread_analysis.sort(key=lambda x: x["total_opportunity"], reverse=True)
        
        total_savings_opportunity = sum(s["total_opportunity"] for s in spread_analysis)
        
        return {
            "total_purchases_analyzed": len(spread_analysis),
            "total_savings_opportunity": round(total_savings_opportunity, 2),
            "poor_spread_count": len([s for s in spread_analysis if s["status"] == "poor_spread"]),
            "spread_analysis": spread_analysis[:50],  # Top 50
            "generated_at": datetime.now().isoformat()
        }
    
    def compare_wholesalers(self) -> Dict[str, Any]:
        """
        Compare wholesaler pricing performance
        
        Returns:
            Wholesaler rankings and recommendations
        """
        wholesaler_stats = {}
        
        for cost in self.acquisition_costs:
            if cost.wholesaler not in wholesaler_stats:
                wholesaler_stats[cost.wholesaler] = {
                    "purchases": [],
                    "total_spend": 0,
                    "total_units": 0
                }
            
            wholesaler_stats[cost.wholesaler]["purchases"].append(cost)
            wholesaler_stats[cost.wholesaler]["total_spend"] += cost.cost_per_unit * cost.quantity
            wholesaler_stats[cost.wholesaler]["total_units"] += cost.quantity
        
        # Calculate metrics per wholesaler
        wholesaler_rankings = []
        
        for wholesaler, stats in wholesaler_stats.items():
            # Calculate average spread
            spreads = []
            for cost in stats["purchases"]:
                awp_history = self.awp_history.get(cost.ndc)
                if awp_history:
                    awp = awp_history[0].awp_per_unit
                    spread_pct = ((cost.cost_per_unit - awp) / awp) * 100
                    spreads.append(spread_pct)
            
            avg_spread = statistics.mean(spreads) if spreads else 0
            
            # Target is -19%, calculate score
            # Closer to -19% (or better) = higher score
            score = max(0, 100 + (avg_spread + 19) * 5)  # Scale around target
            
            wholesaler_rankings.append({
                "wholesaler": wholesaler,
                "total_purchases": len(stats["purchases"]),
                "total_spend": round(stats["total_spend"], 2),
                "total_units": stats["total_units"],
                "avg_spread_pct": round(avg_spread, 2),
                "target_spread_pct": -19.0,
                "performance_score": round(min(100, score), 2),
                "grade": self._score_to_grade(score)
            })
        
        wholesaler_rankings.sort(key=lambda x: x["performance_score"], reverse=True)
        
        return {
            "total_wholesalers": len(wholesaler_rankings),
            "rankings": wholesaler_rankings,
            "recommendation": self._generate_wholesaler_recommendation(wholesaler_rankings),
            "generated_at": datetime.now().isoformat()
        }
    
    def detect_arbitrage_opportunities(self) -> Dict[str, Any]:
        """
        Detect brand-generic arbitrage opportunities
        
        Returns:
            Arbitrage opportunities where generic substitution is profitable
        """
        opportunities = []
        
        # Group drugs by therapeutic equivalent
        # In real implementation, would use FDA Orange Book data
        
        # For now, detect based on naming patterns (simplified)
        brand_generic_pairs = {}
        
        for ndc, history in self.awp_history.items():
            if not history:
                continue
            
            drug = history[0]
            
            # Simplified detection: if drug name contains common brand names
            # Real implementation would use proper brand-generic mapping
            if "generic" in drug.drug_name.lower() or "tab" in drug.drug_name.lower():
                # Check if there's a corresponding brand
                base_name = drug.drug_name.split()[0]  # First word
                
                if base_name not in brand_generic_pairs:
                    brand_generic_pairs[base_name] = {"brand": None, "generics": []}
                
                brand_generic_pairs[base_name]["generics"].append(drug)
        
        # Calculate arbitrage potential
        for base_name, pair in brand_generic_pairs.items():
            if not pair["generics"]:
                continue
            
            # Find lowest cost generic
            cheapest_generic = min(pair["generics"], key=lambda x: x.awp_per_unit)
            
            # If there's significant savings vs other options
            for generic in pair["generics"]:
                if generic.ndc == cheapest_generic.ndc:
                    continue
                
                savings_per_unit = generic.awp_per_unit - cheapest_generic.awp_per_unit
                savings_pct = (savings_per_unit / generic.awp_per_unit) * 100
                
                if savings_pct > 10:  # >10% savings opportunity
                    opportunities.append({
                        "drug_class": base_name,
                        "current_ndc": generic.ndc,
                        "current_product": generic.drug_name,
                        "current_awp": round(generic.awp_per_unit, 2),
                        "recommended_ndc": cheapest_generic.ndc,
                        "recommended_product": cheapest_generic.drug_name,
                        "recommended_awp": round(cheapest_generic.awp_per_unit, 2),
                        "savings_per_unit": round(savings_per_unit, 2),
                        "savings_pct": round(savings_pct, 2)
                    })
        
        opportunities.sort(key=lambda x: x["savings_pct"], reverse=True)
        
        return {
            "total_opportunities": len(opportunities),
            "opportunities": opportunities[:30],  # Top 30
            "generated_at": datetime.now().isoformat()
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert performance score to letter grade"""
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
    
    def _generate_wholesaler_recommendation(self, rankings: List[Dict]) -> str:
        """Generate recommendation based on wholesaler analysis"""
        if not rankings:
            return "Insufficient data for recommendations"
        
        best = rankings[0]
        
        if best["performance_score"] >= 85:
            return f"{best['wholesaler']} is performing well. Continue current relationship."
        elif best["performance_score"] >= 70:
            return f"{best['wholesaler']} is adequate but negotiate for better terms."
        else:
            return f"All wholesalers underperforming. Consider RFP for new wholesaler contracts."


# Example usage:
# intelligence = AWPPricingIntelligence()
# intelligence.add_awp_price(AWPDataPoint(...))
# intelligence.add_acquisition_cost(AcquisitionCost(...))
# changes = intelligence.detect_awp_changes(days=30)
# spread = intelligence.analyze_awp_to_aac_spread()
# comparison = intelligence.compare_wholesalers()
