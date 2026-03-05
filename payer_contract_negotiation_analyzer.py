"""
Payer Contract Rate Negotiation Analyzer
============================================
Analyzes payer contract performance to identify negotiation leverage
points, benchmark against industry standards, model rate improvement
scenarios, and generate data-driven negotiation strategies.

Features:
- Contract performance scoring across all payers
- Effective rate analysis (actual vs contracted)
- Market rate benchmarking against regional/national averages
- Underpayment pattern quantification by drug class
- Contract term gap analysis
- Rate improvement scenario modeling (what-if)
- Payer ranking by profitability contribution
- Negotiation priority scoring
- Historical rate trend analysis
- Negotiation brief generator with data-backed arguments

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import uuid
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, Counter
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContractStatus(Enum):
    ACTIVE = "active"
    EXPIRING = "expiring"      # < 90 days to renewal
    EXPIRED = "expired"
    IN_NEGOTIATION = "in_negotiation"
    PENDING = "pending"


class RateType(Enum):
    AWP_DISCOUNT = "awp_discount"
    WAC_PLUS = "wac_plus"
    NADAC_PLUS = "nadac_plus"
    MAC = "mac"
    FUL = "federal_upper_limit"
    FLAT_FEE = "flat_fee"
    ASP_PLUS = "asp_plus"


@dataclass
class ContractTerms:
    """Terms of a payer contract."""
    contract_id: str
    payer_id: str
    payer_name: str
    start_date: str
    end_date: str
    rate_type: RateType
    brand_discount: float = 0.0    # e.g., AWP-16%
    generic_discount: float = 0.0   # e.g., AWP-72% or NADAC+8%
    specialty_discount: float = 0.0
    dispensing_fee_brand: float = 0.0
    dispensing_fee_generic: float = 0.0
    dispensing_fee_specialty: float = 0.0
    admin_fee_pct: float = 0.0
    dir_fee_pct: float = 0.0
    performance_bonuses: List[Dict[str, Any]] = field(default_factory=list)
    auto_renewal: bool = True
    renewal_notice_days: int = 90
    status: ContractStatus = ContractStatus.ACTIVE

    @property
    def days_until_expiry(self) -> int:
        try:
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            return (end - datetime.now()).days
        except ValueError:
            return -1

    @property
    def effective_generic_rate(self) -> float:
        return self.generic_discount - self.dir_fee_pct - self.admin_fee_pct


@dataclass
class ClaimMetrics:
    """Aggregated claim metrics for a payer."""
    payer_id: str
    total_claims: int = 0
    total_revenue: float = 0.0
    total_cost: float = 0.0
    brand_claims: int = 0
    generic_claims: int = 0
    specialty_claims: int = 0
    brand_revenue: float = 0.0
    generic_revenue: float = 0.0
    specialty_revenue: float = 0.0
    brand_cost: float = 0.0
    generic_cost: float = 0.0
    specialty_cost: float = 0.0
    underpaid_claims: int = 0
    underpaid_amount: float = 0.0
    rejected_claims: int = 0
    avg_dispensing_fee_received: float = 0.0
    dir_fees_paid: float = 0.0
    admin_fees_paid: float = 0.0

    @property
    def gross_margin(self) -> float:
        return self.total_revenue - self.total_cost

    @property
    def gross_margin_pct(self) -> float:
        if self.total_revenue > 0:
            return (self.gross_margin / self.total_revenue) * 100
        return 0.0

    @property
    def net_margin(self) -> float:
        return self.gross_margin - self.dir_fees_paid - self.admin_fees_paid

    @property
    def net_margin_pct(self) -> float:
        if self.total_revenue > 0:
            return (self.net_margin / self.total_revenue) * 100
        return 0.0

    @property
    def rejection_rate(self) -> float:
        total = self.total_claims + self.rejected_claims
        if total > 0:
            return (self.rejected_claims / total) * 100
        return 0.0

    @property
    def underpayment_rate(self) -> float:
        if self.total_claims > 0:
            return (self.underpaid_claims / self.total_claims) * 100
        return 0.0


@dataclass
class MarketBenchmark:
    """Regional/national benchmark rates."""
    category: str  # brand, generic, specialty
    rate_type: RateType
    benchmark_discount: float
    benchmark_dispensing_fee: float
    region: str = "national"
    percentile_25: float = 0.0
    percentile_50: float = 0.0
    percentile_75: float = 0.0
    source: str = ""
    as_of_date: str = ""


@dataclass
class NegotiationScenario:
    """A what-if scenario for rate changes."""
    scenario_name: str
    payer_id: str
    changes: Dict[str, float]  # field -> new value
    projected_annual_impact: float = 0.0
    projected_margin_change: float = 0.0
    feasibility_score: float = 0.0  # 0-100
    rationale: str = ""


class PayerContractNegotiationAnalyzer:
    """
    Analyzes payer contracts and claim data to generate data-driven
    negotiation strategies and identify revenue optimization opportunities.
    """

    def __init__(self):
        self.contracts: Dict[str, ContractTerms] = {}
        self.claim_metrics: Dict[str, ClaimMetrics] = {}
        self.benchmarks: List[MarketBenchmark] = []
        self.scenarios: List[NegotiationScenario] = []
        self._load_default_benchmarks()

    def _load_default_benchmarks(self):
        """Load industry benchmark data."""
        self.benchmarks = [
            MarketBenchmark("brand", RateType.AWP_DISCOUNT, 16.5, 1.75,
                          "national", 14.0, 16.5, 18.0, "NCPA Digest 2025", "2025-12-01"),
            MarketBenchmark("generic", RateType.AWP_DISCOUNT, 72.0, 2.00,
                          "national", 68.0, 72.0, 76.0, "NCPA Digest 2025", "2025-12-01"),
            MarketBenchmark("generic", RateType.NADAC_PLUS, 8.0, 2.50,
                          "national", 5.0, 8.0, 12.0, "NCPA Digest 2025", "2025-12-01"),
            MarketBenchmark("specialty", RateType.AWP_DISCOUNT, 18.0, 3.50,
                          "national", 15.0, 18.0, 22.0, "NCPA Digest 2025", "2025-12-01"),
            MarketBenchmark("brand", RateType.AWP_DISCOUNT, 17.0, 2.00,
                          "southeast", 15.0, 17.0, 19.0, "Regional Survey 2025", "2025-12-01"),
            MarketBenchmark("generic", RateType.NADAC_PLUS, 10.0, 2.75,
                          "southeast", 7.0, 10.0, 13.0, "Regional Survey 2025", "2025-12-01"),
        ]

    def register_contract(self, contract: ContractTerms) -> str:
        """Register a payer contract."""
        # Auto-detect status
        days = contract.days_until_expiry
        if days < 0:
            contract.status = ContractStatus.EXPIRED
        elif days < 90:
            contract.status = ContractStatus.EXPIRING
        self.contracts[contract.contract_id] = contract
        return contract.contract_id

    def load_claim_metrics(self, metrics: ClaimMetrics):
        """Load claim performance metrics for a payer."""
        self.claim_metrics[metrics.payer_id] = metrics

    def analyze_contract_performance(self, contract_id: str) -> Dict[str, Any]:
        """Analyze a single contract's performance."""
        contract = self.contracts.get(contract_id)
        if not contract:
            return {"error": f"Contract {contract_id} not found"}

        metrics = self.claim_metrics.get(contract.payer_id)
        if not metrics:
            return {"error": f"No claim metrics for payer {contract.payer_id}"}

        # Benchmark comparison
        benchmarks = self._get_relevant_benchmarks(contract)

        performance = {
            "contract_id": contract_id,
            "payer": contract.payer_name,
            "status": contract.status.value,
            "days_until_expiry": contract.days_until_expiry,
            "rate_type": contract.rate_type.value,
            "claim_volume": metrics.total_claims,
            "total_revenue": round(metrics.total_revenue, 2),
            "total_cost": round(metrics.total_cost, 2),
            "gross_margin": round(metrics.gross_margin, 2),
            "gross_margin_pct": round(metrics.gross_margin_pct, 2),
            "net_margin": round(metrics.net_margin, 2),
            "net_margin_pct": round(metrics.net_margin_pct, 2),
            "underpaid_claims": metrics.underpaid_claims,
            "underpaid_amount": round(metrics.underpaid_amount, 2),
            "underpayment_rate": round(metrics.underpayment_rate, 2),
            "dir_fees_impact": round(metrics.dir_fees_paid, 2),
            "effective_generic_rate": round(contract.effective_generic_rate, 2),
            "benchmark_comparison": benchmarks,
            "performance_score": self._calculate_performance_score(contract, metrics, benchmarks),
            "negotiation_priority": self._calculate_negotiation_priority(contract, metrics),
        }

        return performance

    def _get_relevant_benchmarks(self, contract: ContractTerms) -> Dict[str, Any]:
        """Compare contract rates against benchmarks."""
        comparisons = {}

        for bm in self.benchmarks:
            if bm.rate_type == contract.rate_type:
                if bm.category == "brand":
                    actual = contract.brand_discount
                elif bm.category == "generic":
                    actual = contract.generic_discount
                elif bm.category == "specialty":
                    actual = contract.specialty_discount
                else:
                    continue

                gap = actual - bm.benchmark_discount
                percentile = self._estimate_percentile(actual, bm)

                comparisons[f"{bm.category}_{bm.region}"] = {
                    "category": bm.category,
                    "region": bm.region,
                    "your_rate": actual,
                    "benchmark_median": bm.benchmark_discount,
                    "gap": round(gap, 2),
                    "percentile": percentile,
                    "assessment": "above_market" if gap > 1 else "at_market" if abs(gap) <= 1 else "below_market"
                }

        return comparisons

    def _estimate_percentile(self, value: float, bm: MarketBenchmark) -> int:
        """Estimate where value falls in distribution."""
        if value <= bm.percentile_25:
            return 25
        elif value <= bm.percentile_50:
            frac = (value - bm.percentile_25) / max(bm.percentile_50 - bm.percentile_25, 0.1)
            return 25 + int(frac * 25)
        elif value <= bm.percentile_75:
            frac = (value - bm.percentile_50) / max(bm.percentile_75 - bm.percentile_50, 0.1)
            return 50 + int(frac * 25)
        else:
            return min(95, 75 + int((value - bm.percentile_75) / max(bm.percentile_75 * 0.1, 0.1) * 10))

    def _calculate_performance_score(self, contract: ContractTerms, metrics: ClaimMetrics,
                                     benchmarks: Dict) -> float:
        """Calculate overall contract performance score (0-100)."""
        score = 50.0  # Start neutral

        # Margin contribution
        if metrics.net_margin_pct > 5:
            score += 15
        elif metrics.net_margin_pct > 2:
            score += 8
        elif metrics.net_margin_pct > 0:
            score += 3
        else:
            score -= 15

        # Underpayment rate
        if metrics.underpayment_rate < 2:
            score += 10
        elif metrics.underpayment_rate < 5:
            score += 5
        elif metrics.underpayment_rate > 10:
            score -= 10

        # Benchmark positioning
        for key, bm_data in benchmarks.items():
            if bm_data["assessment"] == "above_market":
                score += 5
            elif bm_data["assessment"] == "below_market":
                score -= 8

        # DIR fee impact
        dir_pct = metrics.dir_fees_paid / max(metrics.total_revenue, 1) * 100
        if dir_pct > 3:
            score -= 10
        elif dir_pct > 1:
            score -= 5

        # Volume bonus
        if metrics.total_claims > 10000:
            score += 5

        return round(max(0, min(100, score)), 1)

    def _calculate_negotiation_priority(self, contract: ContractTerms, metrics: ClaimMetrics) -> Dict[str, Any]:
        """Calculate negotiation priority score and factors."""
        urgency = 0
        factors = []

        # Contract expiring soon
        days = contract.days_until_expiry
        if days < 30:
            urgency += 30
            factors.append("URGENT: Contract expires in <30 days")
        elif days < 90:
            urgency += 20
            factors.append("Contract expires in <90 days")
        elif days < 180:
            urgency += 10
            factors.append("Contract renewal approaching")

        # Negative margin
        if metrics.net_margin < 0:
            urgency += 25
            factors.append(f"LOSING MONEY: Net margin ${metrics.net_margin:,.2f}")
        elif metrics.net_margin_pct < 2:
            urgency += 15
            factors.append(f"Low margin: {metrics.net_margin_pct:.1f}%")

        # High volume = high impact
        if metrics.total_claims > 5000:
            urgency += 15
            factors.append(f"High volume ({metrics.total_claims:,} claims) — large impact potential")
        elif metrics.total_claims > 1000:
            urgency += 8
            factors.append(f"Moderate volume ({metrics.total_claims:,} claims)")

        # Underpayment issues
        if metrics.underpaid_amount > 10000:
            urgency += 15
            factors.append(f"Significant underpayments: ${metrics.underpaid_amount:,.2f}")

        # DIR fees eating margin
        dir_pct = metrics.dir_fees_paid / max(metrics.total_revenue, 1) * 100
        if dir_pct > 3:
            urgency += 10
            factors.append(f"High DIR fees: {dir_pct:.1f}% of revenue")

        return {
            "priority_score": min(100, urgency),
            "priority_level": "critical" if urgency >= 60 else "high" if urgency >= 40 else "medium" if urgency >= 20 else "low",
            "factors": factors
        }

    def model_scenario(self, payer_id: str, scenario_name: str,
                      changes: Dict[str, float]) -> Dict[str, Any]:
        """Model a negotiation scenario (what-if analysis)."""
        contract = next((c for c in self.contracts.values() if c.payer_id == payer_id), None)
        metrics = self.claim_metrics.get(payer_id)

        if not contract or not metrics:
            return {"error": "Contract or metrics not found for payer"}

        # Calculate impact of changes
        annual_impact = 0.0

        if "generic_discount" in changes:
            rate_diff = changes["generic_discount"] - contract.generic_discount
            generic_revenue = metrics.generic_revenue
            impact = generic_revenue * (rate_diff / 100)
            annual_impact += impact

        if "brand_discount" in changes:
            rate_diff = changes["brand_discount"] - contract.brand_discount
            brand_revenue = metrics.brand_revenue
            impact = brand_revenue * (rate_diff / 100)
            annual_impact += impact

        if "dispensing_fee_generic" in changes:
            fee_diff = changes["dispensing_fee_generic"] - contract.dispensing_fee_generic
            impact = fee_diff * metrics.generic_claims
            annual_impact += impact

        if "dir_fee_pct" in changes:
            dir_diff = changes["dir_fee_pct"] - contract.dir_fee_pct
            impact = metrics.total_revenue * (dir_diff / 100)
            annual_impact -= impact  # Lower DIR = positive impact

        scenario = NegotiationScenario(
            scenario_name=scenario_name,
            payer_id=payer_id,
            changes=changes,
            projected_annual_impact=round(annual_impact, 2),
            projected_margin_change=round(annual_impact / max(metrics.total_revenue, 1) * 100, 2),
            feasibility_score=self._assess_feasibility(changes, contract),
            rationale=self._build_scenario_rationale(changes, contract, metrics)
        )
        self.scenarios.append(scenario)

        return {
            "scenario": scenario_name,
            "payer": contract.payer_name,
            "changes": changes,
            "projected_annual_impact": scenario.projected_annual_impact,
            "projected_margin_change_pct": scenario.projected_margin_change,
            "feasibility_score": scenario.feasibility_score,
            "rationale": scenario.rationale
        }

    def _assess_feasibility(self, changes: Dict[str, float], contract: ContractTerms) -> float:
        """Assess how feasible a negotiation scenario is."""
        score = 70.0  # Start moderately feasible

        for field_name, new_value in changes.items():
            if field_name == "generic_discount":
                increase = new_value - contract.generic_discount
                if increase > 5:
                    score -= 20
                elif increase > 2:
                    score -= 10
            elif field_name == "dispensing_fee_generic":
                increase = new_value - contract.dispensing_fee_generic
                if increase > 1.0:
                    score -= 15
                elif increase > 0.5:
                    score -= 5
            elif field_name == "dir_fee_pct":
                decrease = contract.dir_fee_pct - new_value
                if decrease > 2:
                    score -= 20
                elif decrease > 1:
                    score -= 10

        return max(10, min(95, score))

    def _build_scenario_rationale(self, changes: Dict[str, float], contract: ContractTerms,
                                  metrics: ClaimMetrics) -> str:
        """Build a data-backed rationale for negotiation."""
        parts = []
        for field_name, new_value in changes.items():
            if field_name == "generic_discount":
                parts.append(f"Generic discount improvement {contract.generic_discount}% → {new_value}%: "
                           f"justified by {metrics.generic_claims:,} generic claim volume")
            elif field_name == "dispensing_fee_generic":
                parts.append(f"Dispensing fee increase ${contract.dispensing_fee_generic} → ${new_value}: "
                           f"operational costs have risen, below market median")
            elif field_name == "dir_fee_pct":
                parts.append(f"DIR fee reduction {contract.dir_fee_pct}% → {new_value}%: "
                           f"current DIR erodes ${metrics.dir_fees_paid:,.2f} from margins")
        return "; ".join(parts) if parts else "General rate improvement"

    def generate_negotiation_brief(self, payer_id: str) -> Dict[str, Any]:
        """Generate a comprehensive negotiation brief for a payer."""
        contract = next((c for c in self.contracts.values() if c.payer_id == payer_id), None)
        metrics = self.claim_metrics.get(payer_id)

        if not contract or not metrics:
            return {"error": "Data not found"}

        priority = self._calculate_negotiation_priority(contract, metrics)
        benchmarks = self._get_relevant_benchmarks(contract)

        # Identify top improvement areas
        improvements = []
        for key, bm in benchmarks.items():
            if bm["assessment"] == "below_market":
                improvements.append({
                    "area": bm["category"],
                    "current": bm["your_rate"],
                    "market_median": bm["benchmark_median"],
                    "gap": bm["gap"],
                    "recommended_target": bm["benchmark_median"]
                })

        return {
            "payer": contract.payer_name,
            "contract_id": contract.contract_id,
            "contract_expiry": contract.end_date,
            "days_remaining": contract.days_until_expiry,
            "priority": priority,
            "current_performance": {
                "total_claims": metrics.total_claims,
                "annual_revenue": round(metrics.total_revenue, 2),
                "net_margin": round(metrics.net_margin, 2),
                "net_margin_pct": round(metrics.net_margin_pct, 2),
                "underpayment_amount": round(metrics.underpaid_amount, 2),
                "dir_fees": round(metrics.dir_fees_paid, 2)
            },
            "market_positioning": benchmarks,
            "improvement_areas": improvements,
            "negotiation_talking_points": self._generate_talking_points(contract, metrics, benchmarks),
            "scenarios": [
                {
                    "name": s.scenario_name,
                    "annual_impact": s.projected_annual_impact,
                    "feasibility": s.feasibility_score
                }
                for s in self.scenarios if s.payer_id == payer_id
            ]
        }

    def _generate_talking_points(self, contract: ContractTerms, metrics: ClaimMetrics,
                                 benchmarks: Dict) -> List[str]:
        """Generate negotiation talking points."""
        points = []

        points.append(f"We process {metrics.total_claims:,} claims annually for your plan, "
                      f"representing significant volume and patient access")

        if metrics.underpaid_amount > 0:
            points.append(f"We have documented ${metrics.underpaid_amount:,.2f} in underpayments "
                         f"requiring reconciliation")

        for key, bm in benchmarks.items():
            if bm["assessment"] == "below_market":
                points.append(f"Our {bm['category']} rate ({bm['your_rate']}%) is below "
                            f"the market median ({bm['benchmark_median']}%) — a {abs(bm['gap']):.1f}% gap")

        dir_pct = metrics.dir_fees_paid / max(metrics.total_revenue, 1) * 100
        if dir_pct > 2:
            points.append(f"DIR fees of ${metrics.dir_fees_paid:,.2f} ({dir_pct:.1f}% of revenue) "
                         f"are creating unsustainable margin pressure")

        if metrics.rejection_rate > 5:
            points.append(f"Rejection rate of {metrics.rejection_rate:.1f}% adds administrative burden — "
                         f"we'd like to discuss streamlined adjudication")

        return points

    def get_payer_rankings(self) -> List[Dict[str, Any]]:
        """Rank all payers by performance and negotiation priority."""
        rankings = []
        for contract in self.contracts.values():
            metrics = self.claim_metrics.get(contract.payer_id)
            if not metrics:
                continue
            priority = self._calculate_negotiation_priority(contract, metrics)
            perf_score = self._calculate_performance_score(contract, metrics,
                                                           self._get_relevant_benchmarks(contract))
            rankings.append({
                "payer": contract.payer_name,
                "payer_id": contract.payer_id,
                "performance_score": perf_score,
                "negotiation_priority": priority["priority_score"],
                "priority_level": priority["priority_level"],
                "net_margin_pct": round(metrics.net_margin_pct, 2),
                "claim_volume": metrics.total_claims,
                "annual_revenue": round(metrics.total_revenue, 2),
                "contract_expiry": contract.end_date
            })

        rankings.sort(key=lambda x: -x["negotiation_priority"])
        return rankings


if __name__ == "__main__":
    analyzer = PayerContractNegotiationAnalyzer()

    # Register contracts
    bcbs = ContractTerms(
        contract_id="CTR-001",
        payer_id="BCBS-KY",
        payer_name="Blue Cross Blue Shield of Kentucky",
        start_date="2025-01-01",
        end_date="2026-06-30",
        rate_type=RateType.AWP_DISCOUNT,
        brand_discount=15.0,
        generic_discount=68.0,
        specialty_discount=16.0,
        dispensing_fee_brand=1.50,
        dispensing_fee_generic=1.50,
        dispensing_fee_specialty=2.50,
        dir_fee_pct=2.5,
        admin_fee_pct=0.5
    )
    analyzer.register_contract(bcbs)

    # Load metrics
    bcbs_metrics = ClaimMetrics(
        payer_id="BCBS-KY",
        total_claims=8500,
        total_revenue=425000.0,
        total_cost=380000.0,
        generic_claims=6800,
        brand_claims=1500,
        specialty_claims=200,
        generic_revenue=280000.0,
        brand_revenue=120000.0,
        specialty_revenue=25000.0,
        generic_cost=255000.0,
        brand_cost=108000.0,
        specialty_cost=17000.0,
        underpaid_claims=340,
        underpaid_amount=15800.0,
        rejected_claims=425,
        dir_fees_paid=10625.0,
        admin_fees_paid=2125.0
    )
    analyzer.load_claim_metrics(bcbs_metrics)

    # Analyze performance
    perf = analyzer.analyze_contract_performance("CTR-001")
    print("=== Contract Performance ===")
    print(json.dumps(perf, indent=2))

    # Model scenario
    scenario = analyzer.model_scenario(
        "BCBS-KY", "Improve Generic Rate + Reduce DIR",
        {"generic_discount": 72.0, "dir_fee_pct": 1.5, "dispensing_fee_generic": 2.00}
    )
    print("\n=== Negotiation Scenario ===")
    print(json.dumps(scenario, indent=2))

    # Generate brief
    brief = analyzer.generate_negotiation_brief("BCBS-KY")
    print("\n=== Negotiation Brief (Talking Points) ===")
    for point in brief["negotiation_talking_points"]:
        print(f"  • {point}")
