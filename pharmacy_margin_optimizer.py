"""
GetPaidRx - Pharmacy Margin Optimizer

Real-time margin optimization engine that identifies the highest-impact
actions a pharmacy can take to improve profitability. Combines drug-level
margin analysis, contract negotiation triggers, generic substitution
opportunities, dispensing fee optimization, and inventory turn recommendations.

Features:
  - Drug-level margin waterfall analysis
  - Margin improvement opportunity scoring (0-100)
  - Generic substitution savings calculator
  - Dispensing fee benchmarking against industry averages
  - Inventory turn rate optimization with dead stock identification
  - Payer contract renegotiation triggers
  - Margin forecast modeling (30/60/90 day projections)
  - Action prioritization with ROI ranking
  - Dashboard-ready KPI generation
  - FastAPI route integration
"""

import uuid
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# Industry Benchmarks (2026)
# ============================================================

INDUSTRY_BENCHMARKS = {
    "avg_gross_margin_pct": 22.5,  # Average independent pharmacy gross margin
    "avg_dispensing_fee": 10.50,  # Average dispensing fee
    "avg_inventory_turns": 12.0,  # Annual turns
    "avg_generic_fill_rate": 0.90,  # 90% generic dispensing rate
    "avg_days_sales_inventory": 28,  # DSI
    "avg_script_count_per_day": 180,  # Average for independent
    "avg_revenue_per_rx": 42.50,  # Average revenue per prescription
    "avg_cost_per_rx": 33.00,  # Average COGS per prescription
    "avg_labor_cost_per_rx": 5.20,  # Average labor cost
    "target_net_margin_pct": 3.5,  # Target net profit margin
}


@dataclass
class MarginOpportunity:
    """A single margin improvement opportunity."""
    opportunity_id: str = ""
    category: str = ""  # generic_switch/contract/inventory/dispensing/volume
    title: str = ""
    description: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    monthly_impact: float = 0.0
    annual_impact: float = 0.0
    difficulty: str = "MEDIUM"  # EASY/MEDIUM/HARD
    time_to_implement: str = ""
    roi_score: float = 0.0  # 0-100
    priority_rank: int = 0


class PharmacyMarginOptimizer:
    """
    Analyzes pharmacy operations and identifies the highest-ROI
    margin improvement opportunities.
    """
    
    def __init__(self):
        self.pharmacy_data: Dict = {}
        self.claim_data: List[Dict] = []
        self.opportunities: List[MarginOpportunity] = []
    
    def load_pharmacy_profile(self, profile: Dict) -> None:
        """Load pharmacy operational profile."""
        defaults = {
            "pharmacy_name": "Independent Pharmacy",
            "avg_daily_scripts": 150,
            "current_gross_margin_pct": 20.5,
            "current_dispensing_fee_avg": 8.50,
            "generic_fill_rate": 0.85,
            "inventory_value": 350000,
            "annual_revenue": 5500000,
            "annual_cogs": 4375000,
            "monthly_rent": 6500,
            "monthly_labor": 45000,
            "monthly_supplies": 3500,
            "payer_mix": {
                "commercial": 0.35,
                "medicare_part_d": 0.30,
                "medicaid": 0.20,
                "cash": 0.10,
                "340b": 0.05,
            },
            "top_drugs_by_revenue": [
                {"name": "Ozempic 1mg", "monthly_revenue": 45000, "margin_pct": 4.2, "is_brand": True},
                {"name": "Eliquis 5mg", "monthly_revenue": 38000, "margin_pct": 3.8, "is_brand": True},
                {"name": "Atorvastatin 20mg", "monthly_revenue": 12000, "margin_pct": 45.0, "is_brand": False},
                {"name": "Lisinopril 10mg", "monthly_revenue": 8500, "margin_pct": 52.0, "is_brand": False},
                {"name": "Metformin 500mg", "monthly_revenue": 7200, "margin_pct": 48.0, "is_brand": False},
                {"name": "Humira Pen", "monthly_revenue": 42000, "margin_pct": 2.1, "is_brand": True},
                {"name": "Trulicity 1.5mg", "monthly_revenue": 28000, "margin_pct": 5.5, "is_brand": True},
                {"name": "Gabapentin 300mg", "monthly_revenue": 6800, "margin_pct": 42.0, "is_brand": False},
                {"name": "Omeprazole 20mg", "monthly_revenue": 5500, "margin_pct": 55.0, "is_brand": False},
                {"name": "Sertraline 50mg", "monthly_revenue": 4800, "margin_pct": 50.0, "is_brand": False},
            ],
            "inventory_turns_annual": 10.5,
            "days_sales_inventory": 34,
            "dead_stock_pct": 8.5,
        }
        self.pharmacy_data = {**defaults, **profile}
    
    def analyze_opportunities(self) -> Dict:
        """Run comprehensive margin analysis and identify opportunities."""
        if not self.pharmacy_data:
            self.load_pharmacy_profile({})
        
        self.opportunities = []
        
        self._check_generic_opportunities()
        self._check_dispensing_fee_opportunities()
        self._check_inventory_opportunities()
        self._check_contract_opportunities()
        self._check_volume_opportunities()
        self._check_specialty_opportunities()
        
        # Score and rank
        self._score_opportunities()
        self.opportunities.sort(key=lambda o: o.roi_score, reverse=True)
        for i, opp in enumerate(self.opportunities):
            opp.priority_rank = i + 1
        
        total_monthly = sum(o.monthly_impact for o in self.opportunities)
        total_annual = sum(o.annual_impact for o in self.opportunities)
        
        return {
            "pharmacy_name": self.pharmacy_data.get("pharmacy_name"),
            "analysis_date": datetime.utcnow().isoformat() + "Z",
            "current_state": {
                "gross_margin_pct": self.pharmacy_data["current_gross_margin_pct"],
                "industry_avg_margin_pct": INDUSTRY_BENCHMARKS["avg_gross_margin_pct"],
                "gap_vs_industry": round(INDUSTRY_BENCHMARKS["avg_gross_margin_pct"] - self.pharmacy_data["current_gross_margin_pct"], 1),
                "generic_fill_rate": self.pharmacy_data["generic_fill_rate"],
                "inventory_turns": self.pharmacy_data["inventory_turns_annual"],
                "daily_scripts": self.pharmacy_data["avg_daily_scripts"],
            },
            "total_opportunities": len(self.opportunities),
            "total_monthly_improvement": round(total_monthly, 2),
            "total_annual_improvement": round(total_annual, 2),
            "potential_margin_improvement_pct": round(
                (total_annual / self.pharmacy_data["annual_revenue"]) * 100, 2
            ),
            "opportunities": [self._opp_to_dict(o) for o in self.opportunities],
            "quick_wins": [self._opp_to_dict(o) for o in self.opportunities if o.difficulty == "EASY"][:3],
            "high_impact": [self._opp_to_dict(o) for o in self.opportunities if o.annual_impact > 10000][:3],
            "category_summary": self._summarize_by_category(),
        }
    
    def _check_generic_opportunities(self):
        """Identify generic substitution margin opportunities."""
        current_rate = self.pharmacy_data["generic_fill_rate"]
        target_rate = min(current_rate + 0.05, 0.95)
        
        if current_rate < INDUSTRY_BENCHMARKS["avg_generic_fill_rate"]:
            annual_rev = self.pharmacy_data["annual_revenue"]
            brand_rev = annual_rev * (1 - current_rate)
            switchable_pct = (target_rate - current_rate) / (1 - current_rate)
            # Generic margin ~45% vs brand ~5%
            savings = brand_rev * switchable_pct * 0.40  # margin pickup
            
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="generic_switch",
                title="Increase Generic Fill Rate",
                description=f"Current GFR: {current_rate*100:.0f}%. Increasing to {target_rate*100:.0f}% through prescriber outreach and DAW code management captures significantly higher margins on generic dispensing.",
                current_value=current_rate,
                target_value=target_rate,
                monthly_impact=round(savings / 12, 2),
                annual_impact=round(savings, 2),
                difficulty="MEDIUM",
                time_to_implement="2-4 weeks",
            ))
        
        # Check specific brand-to-generic switches
        brand_drugs = [d for d in self.pharmacy_data.get("top_drugs_by_revenue", []) if d.get("is_brand") and d.get("margin_pct", 0) < 10]
        for drug in brand_drugs[:3]:
            potential_savings = drug["monthly_revenue"] * 0.08  # Est. 8% margin improvement
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="generic_switch",
                title=f"Generic Alternative for {drug['name']}",
                description=f"Current margin: {drug['margin_pct']}%. Identify authorized generic or therapeutic alternative with higher margin.",
                current_value=drug["margin_pct"],
                target_value=drug["margin_pct"] + 8,
                monthly_impact=round(potential_savings, 2),
                annual_impact=round(potential_savings * 12, 2),
                difficulty="MEDIUM",
                time_to_implement="1-2 weeks",
            ))
    
    def _check_dispensing_fee_opportunities(self):
        """Check dispensing fee optimization."""
        current_fee = self.pharmacy_data["current_dispensing_fee_avg"]
        industry_avg = INDUSTRY_BENCHMARKS["avg_dispensing_fee"]
        
        if current_fee < industry_avg:
            daily_scripts = self.pharmacy_data["avg_daily_scripts"]
            fee_gap = industry_avg - current_fee
            monthly_impact = fee_gap * daily_scripts * 30
            
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="dispensing",
                title="Negotiate Higher Dispensing Fees",
                description=f"Current avg fee: ${current_fee:.2f} vs industry avg: ${industry_avg:.2f}. Negotiate fee increases in upcoming contract renewals.",
                current_value=current_fee,
                target_value=industry_avg,
                monthly_impact=round(monthly_impact, 2),
                annual_impact=round(monthly_impact * 12, 2),
                difficulty="HARD",
                time_to_implement="Contract renewal cycle",
            ))
    
    def _check_inventory_opportunities(self):
        """Identify inventory optimization opportunities."""
        current_turns = self.pharmacy_data["inventory_turns_annual"]
        target_turns = INDUSTRY_BENCHMARKS["avg_inventory_turns"]
        dead_stock_pct = self.pharmacy_data.get("dead_stock_pct", 0)
        inv_value = self.pharmacy_data["inventory_value"]
        
        if current_turns < target_turns:
            # Freed capital from better turns
            current_avg_inv = inv_value
            target_avg_inv = self.pharmacy_data["annual_cogs"] / target_turns
            freed_capital = current_avg_inv - target_avg_inv
            carrying_cost_savings = freed_capital * 0.15  # 15% carrying cost
            
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="inventory",
                title="Improve Inventory Turnover",
                description=f"Current turns: {current_turns}x vs target: {target_turns}x. Tighter purchasing, just-in-time ordering, and dead stock reduction frees ${freed_capital:,.0f} in working capital.",
                current_value=current_turns,
                target_value=target_turns,
                monthly_impact=round(carrying_cost_savings / 12, 2),
                annual_impact=round(carrying_cost_savings, 2),
                difficulty="MEDIUM",
                time_to_implement="4-8 weeks",
            ))
        
        if dead_stock_pct > 5:
            dead_stock_value = inv_value * (dead_stock_pct / 100)
            recovery = dead_stock_value * 0.40  # 40% recovery through returns/reverse distribution
            
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="inventory",
                title="Reduce Dead Stock",
                description=f"Dead stock: {dead_stock_pct}% (${dead_stock_value:,.0f}). Use reverse distribution for expired drugs and return-to-vendor for slow movers.",
                current_value=dead_stock_pct,
                target_value=3.0,
                monthly_impact=round(recovery / 6, 2),  # Over 6 months
                annual_impact=round(recovery, 2),
                difficulty="EASY",
                time_to_implement="1-2 weeks",
            ))
    
    def _check_contract_opportunities(self):
        """Identify payer contract renegotiation triggers."""
        payer_mix = self.pharmacy_data.get("payer_mix", {})
        annual_rev = self.pharmacy_data["annual_revenue"]
        
        # Check if any payer is >30% of revenue (concentration risk)
        for payer, share in payer_mix.items():
            if share >= 0.30 and payer != "cash":
                payer_rev = annual_rev * share
                negotiation_target = payer_rev * 0.02  # 2% improvement target
                
                self.opportunities.append(MarginOpportunity(
                    opportunity_id=str(uuid.uuid4())[:8],
                    category="contract",
                    title=f"Renegotiate {payer.replace('_', ' ').title()} Contract",
                    description=f"{payer.replace('_', ' ').title()} represents {share*100:.0f}% of revenue (${payer_rev:,.0f}/yr). Even 2% improvement = ${negotiation_target:,.0f}/yr. Use NADAC benchmarks as leverage.",
                    current_value=share * 100,
                    target_value=share * 100,
                    monthly_impact=round(negotiation_target / 12, 2),
                    annual_impact=round(negotiation_target, 2),
                    difficulty="HARD",
                    time_to_implement="1-3 months",
                ))
    
    def _check_volume_opportunities(self):
        """Check prescription volume growth opportunities."""
        daily_scripts = self.pharmacy_data["avg_daily_scripts"]
        avg_margin_per_rx = (self.pharmacy_data["annual_revenue"] - self.pharmacy_data["annual_cogs"]) / (daily_scripts * 365)
        
        if daily_scripts < INDUSTRY_BENCHMARKS["avg_script_count_per_day"]:
            target_increase = min(20, INDUSTRY_BENCHMARKS["avg_script_count_per_day"] - daily_scripts)
            volume_impact = target_increase * avg_margin_per_rx * 30
            
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="volume",
                title="Grow Prescription Volume",
                description=f"Current: {daily_scripts}/day vs industry avg: {INDUSTRY_BENCHMARKS['avg_script_count_per_day']}/day. Adding {target_increase} scripts/day through prescriber outreach, adherence programs, and immunization services.",
                current_value=daily_scripts,
                target_value=daily_scripts + target_increase,
                monthly_impact=round(volume_impact, 2),
                annual_impact=round(volume_impact * 12, 2),
                difficulty="MEDIUM",
                time_to_implement="2-6 months",
            ))
    
    def _check_specialty_opportunities(self):
        """Check specialty pharmacy service opportunities."""
        # MTM revenue
        daily_scripts = self.pharmacy_data["avg_daily_scripts"]
        medicare_share = self.pharmacy_data.get("payer_mix", {}).get("medicare_part_d", 0)
        eligible_patients = daily_scripts * 30 * medicare_share * 0.15  # 15% of Medicare patients qualify
        mtm_revenue = eligible_patients * 75  # $75 avg CMR reimbursement
        
        if mtm_revenue > 500:
            self.opportunities.append(MarginOpportunity(
                opportunity_id=str(uuid.uuid4())[:8],
                category="services",
                title="Expand MTM/CMR Services",
                description=f"Estimated {int(eligible_patients)} Medicare patients qualify for MTM. At $75/CMR avg, this adds ${mtm_revenue:,.0f}/month in pure-margin clinical services revenue.",
                current_value=0,
                target_value=mtm_revenue,
                monthly_impact=round(mtm_revenue, 2),
                annual_impact=round(mtm_revenue * 12, 2),
                difficulty="EASY",
                time_to_implement="1-2 weeks",
            ))
        
        # Immunization revenue
        immunization_monthly = daily_scripts * 0.05 * 25  # 5% conversion, $25 avg admin fee
        self.opportunities.append(MarginOpportunity(
            opportunity_id=str(uuid.uuid4())[:8],
            category="services",
            title="Immunization Program Expansion",
            description=f"Estimated {int(daily_scripts * 0.05)} immunizations/day at $25 avg admin fee. Includes flu, COVID, shingles, pneumonia, RSV.",
            current_value=0,
            target_value=immunization_monthly,
            monthly_impact=round(immunization_monthly, 2),
            annual_impact=round(immunization_monthly * 12, 2),
            difficulty="EASY",
            time_to_implement="1 week (if already credentialed)",
        ))
    
    def _score_opportunities(self):
        """Score each opportunity for ROI-based prioritization."""
        if not self.opportunities:
            return
        
        max_annual = max(o.annual_impact for o in self.opportunities) or 1
        difficulty_scores = {"EASY": 30, "MEDIUM": 20, "HARD": 10}
        
        for opp in self.opportunities:
            impact_score = (opp.annual_impact / max_annual) * 60
            ease_score = difficulty_scores.get(opp.difficulty, 15)
            opp.roi_score = round(min(100, impact_score + ease_score), 1)
    
    def _opp_to_dict(self, opp: MarginOpportunity) -> Dict:
        return {
            "opportunity_id": opp.opportunity_id,
            "priority_rank": opp.priority_rank,
            "category": opp.category,
            "title": opp.title,
            "description": opp.description,
            "current_value": opp.current_value,
            "target_value": opp.target_value,
            "monthly_impact": opp.monthly_impact,
            "annual_impact": opp.annual_impact,
            "difficulty": opp.difficulty,
            "time_to_implement": opp.time_to_implement,
            "roi_score": opp.roi_score,
        }
    
    def _summarize_by_category(self) -> Dict:
        """Summarize opportunities by category."""
        cats = defaultdict(lambda: {"count": 0, "total_annual": 0})
        for opp in self.opportunities:
            cats[opp.category]["count"] += 1
            cats[opp.category]["total_annual"] += opp.annual_impact
        
        return {k: {"count": v["count"], "total_annual_impact": round(v["total_annual"], 2)}
                for k, v in sorted(cats.items(), key=lambda x: x[1]["total_annual"], reverse=True)}
    
    def get_margin_forecast(self, months: int = 6) -> Dict:
        """Project margin improvements over time."""
        if not self.opportunities:
            self.analyze_opportunities()
        
        current_margin = self.pharmacy_data.get("current_gross_margin_pct", 20.5)
        annual_rev = self.pharmacy_data.get("annual_revenue", 5500000)
        
        easy = [o for o in self.opportunities if o.difficulty == "EASY"]
        medium = [o for o in self.opportunities if o.difficulty == "MEDIUM"]
        hard = [o for o in self.opportunities if o.difficulty == "HARD"]
        
        forecast = []
        cumulative_improvement = 0
        
        for month in range(1, months + 1):
            # Easy wins: fully realized by month 2
            if month >= 2:
                cumulative_improvement += sum(o.monthly_impact for o in easy) / 2
            
            # Medium: ramp from month 2-4
            if 2 <= month <= 4:
                cumulative_improvement += sum(o.monthly_impact for o in medium) / 3
            elif month > 4:
                cumulative_improvement += sum(o.monthly_impact for o in medium) / 6
            
            # Hard: ramp from month 4+
            if month >= 4:
                cumulative_improvement += sum(o.monthly_impact for o in hard) / 6
            
            new_margin = current_margin + (cumulative_improvement / (annual_rev / 12)) * 100
            
            forecast.append({
                "month": month,
                "projected_margin_pct": round(min(new_margin, 30), 2),
                "cumulative_monthly_improvement": round(cumulative_improvement, 2),
                "margin_gain_pct": round(new_margin - current_margin, 2),
            })
        
        return {
            "starting_margin_pct": current_margin,
            "forecast_months": months,
            "forecast": forecast,
            "target_margin_pct": INDUSTRY_BENCHMARKS["avg_gross_margin_pct"],
        }


def create_margin_optimizer_routes(app):
    """Register margin optimizer routes."""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/margin", tags=["Margin Optimization"])
    optimizer = PharmacyMarginOptimizer()
    optimizer.load_pharmacy_profile({})
    
    @router.get("/analyze")
    async def analyze_margins():
        """Get comprehensive margin analysis with opportunities."""
        return optimizer.analyze_opportunities()
    
    @router.get("/forecast")
    async def margin_forecast(months: int = 6):
        """Get margin improvement forecast."""
        return optimizer.get_margin_forecast(months)
    
    @router.get("/quick-wins")
    async def quick_wins():
        """Get top 3 easy-to-implement margin improvements."""
        analysis = optimizer.analyze_opportunities()
        return {"quick_wins": analysis["quick_wins"]}
    
    app.include_router(router)
    return router
