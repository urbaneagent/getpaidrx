"""
GetPaidRx - Pharmacy Margin Optimizer
Analyzes prescription fill data against multiple pricing benchmarks (NADAC, AWP, WAC, MAC)
to identify margin erosion, optimize fill routing, and maximize per-script profitability.

Features:
- Multi-benchmark price comparison (NADAC, AWP, WAC, MAC, 340B)
- Margin erosion detection with trending
- Fill-level profitability scoring
- Payer contract compliance verification
- Generic substitution opportunity finder
- Brand-to-generic switch ROI calculator
- Optimal fill routing recommendations
"""
import json
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class PricingBenchmark(Enum):
    NADAC = "NADAC"           # National Average Drug Acquisition Cost
    AWP = "AWP"               # Average Wholesale Price
    WAC = "WAC"               # Wholesale Acquisition Cost
    MAC = "MAC"               # Maximum Allowable Cost
    ASP = "ASP"               # Average Sales Price
    FEDERAL_UPPER_LIMIT = "FUL"
    ACTUAL_COST = "ACQ"       # Actual acquisition cost
    COST_340B = "340B"        # 340B ceiling price


class DrugType(Enum):
    BRAND = "brand"
    GENERIC = "generic"
    BIOSIMILAR = "biosimilar"
    SPECIALTY = "specialty"
    OTC = "otc"
    COMPOUND = "compound"


class MarginStatus(Enum):
    PROFITABLE = "profitable"       # margin > 5%
    MARGINAL = "marginal"          # margin 0-5%
    UNDERWATER = "underwater"       # margin < 0%
    SEVERELY_UNDERWATER = "severely_underwater"  # margin < -10%


@dataclass
class DrugPricing:
    """Pricing data for a specific drug product."""
    ndc: str
    drug_name: str
    drug_type: DrugType
    gpi: str = ""  # Generic Product Identifier
    strength: str = ""
    form: str = ""
    package_size: float = 1.0
    nadac_per_unit: float = 0.0
    awp_per_unit: float = 0.0
    wac_per_unit: float = 0.0
    mac_per_unit: Optional[float] = None
    acquisition_cost_per_unit: float = 0.0
    cost_340b_per_unit: Optional[float] = None
    last_updated: str = ""
    generic_alternatives: List[str] = field(default_factory=list)


@dataclass
class FillRecord:
    """A single prescription fill record."""
    fill_id: str
    ndc: str
    drug_name: str
    quantity: float
    days_supply: int
    fill_date: str
    patient_id: str
    payer_id: str
    payer_name: str
    plan_type: str = ""  # commercial, medicare_d, medicaid, cash, 340b
    dispensing_fee: float = 0.0
    ingredient_cost_billed: float = 0.0
    ingredient_cost_paid: float = 0.0
    patient_copay: float = 0.0
    total_reimbursement: float = 0.0
    acquisition_cost: float = 0.0
    is_generic: bool = False
    is_340b: bool = False
    prescriber_npi: str = ""
    pharmacy_npi: str = ""


@dataclass
class MarginAnalysis:
    """Margin analysis for a fill or group of fills."""
    fill_id: str
    drug_name: str
    ndc: str
    reimbursement: float
    acquisition_cost: float
    dispensing_fee: float
    gross_margin: float
    gross_margin_pct: float
    net_margin: float  # after estimated overhead
    margin_status: MarginStatus
    nadac_benchmark: float = 0.0
    nadac_spread: float = 0.0
    awp_discount_pct: float = 0.0
    improvement_potential: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class MarginCalculator:
    """Core margin calculation engine."""

    # Estimated per-fill overhead costs
    OVERHEAD_PER_FILL = 10.50  # pharmacist time, overhead, etc.
    MIN_ACCEPTABLE_MARGIN_PCT = 5.0
    TARGET_MARGIN_PCT = 15.0

    def __init__(self):
        self.pricing_db: Dict[str, DrugPricing] = {}
        self.payer_contracts: Dict[str, Dict] = {}

    def load_pricing(self, pricing_data: List[DrugPricing]):
        """Load drug pricing database."""
        for p in pricing_data:
            self.pricing_db[p.ndc] = p
        logger.info(f"Loaded pricing for {len(pricing_data)} NDCs")

    def load_payer_contract(self, payer_id: str, contract: Dict):
        """Load a payer contract with reimbursement terms."""
        self.payer_contracts[payer_id] = contract
        logger.info(f"Loaded contract for payer {payer_id}")

    def analyze_fill(self, fill: FillRecord) -> MarginAnalysis:
        """Analyze margin for a single fill."""
        gross_margin = fill.total_reimbursement - fill.acquisition_cost
        gross_margin_pct = (
            (gross_margin / fill.total_reimbursement * 100)
            if fill.total_reimbursement > 0 else 0
        )
        net_margin = gross_margin - self.OVERHEAD_PER_FILL

        # Determine margin status
        if gross_margin_pct >= self.MIN_ACCEPTABLE_MARGIN_PCT:
            status = MarginStatus.PROFITABLE
        elif gross_margin_pct >= 0:
            status = MarginStatus.MARGINAL
        elif gross_margin_pct >= -10:
            status = MarginStatus.UNDERWATER
        else:
            status = MarginStatus.SEVERELY_UNDERWATER

        # Benchmark comparisons
        nadac_benchmark = 0.0
        nadac_spread = 0.0
        awp_discount = 0.0

        pricing = self.pricing_db.get(fill.ndc)
        if pricing:
            nadac_benchmark = pricing.nadac_per_unit * fill.quantity
            nadac_spread = fill.total_reimbursement - nadac_benchmark
            if pricing.awp_per_unit > 0:
                awp_total = pricing.awp_per_unit * fill.quantity
                awp_discount = ((awp_total - fill.total_reimbursement) / awp_total * 100)

        # Calculate improvement potential
        improvement = 0.0
        recommendations = []

        if status in (MarginStatus.UNDERWATER, MarginStatus.SEVERELY_UNDERWATER):
            target_reimb = fill.acquisition_cost * (1 + self.TARGET_MARGIN_PCT / 100) + self.OVERHEAD_PER_FILL
            improvement = target_reimb - fill.total_reimbursement
            recommendations.append(
                f"Fill is ${abs(gross_margin):.2f} underwater. "
                f"Need ${improvement:.2f} more reimbursement to hit {self.TARGET_MARGIN_PCT}% target."
            )

        if pricing and pricing.generic_alternatives and not fill.is_generic:
            recommendations.append(
                f"Generic alternatives available: {', '.join(pricing.generic_alternatives[:3])}. "
                f"Switch could improve margin significantly."
            )

        if fill.dispensing_fee < 2.0:
            recommendations.append(
                f"Dispensing fee is only ${fill.dispensing_fee:.2f}. "
                f"Negotiate higher dispensing fee with {fill.payer_name}."
            )

        # Check payer contract compliance
        contract = self.payer_contracts.get(fill.payer_id, {})
        if contract:
            min_reimb_pct = contract.get("min_reimbursement_of_awp", 0)
            if pricing and pricing.awp_per_unit > 0 and min_reimb_pct > 0:
                expected = pricing.awp_per_unit * fill.quantity * (min_reimb_pct / 100)
                if fill.ingredient_cost_paid < expected * 0.95:
                    recommendations.append(
                        f"UNDERPAYMENT: Reimbursement below contract minimum. "
                        f"Expected ${expected:.2f}, got ${fill.ingredient_cost_paid:.2f}. "
                        f"File claim dispute with {fill.payer_name}."
                    )

        return MarginAnalysis(
            fill_id=fill.fill_id,
            drug_name=fill.drug_name,
            ndc=fill.ndc,
            reimbursement=fill.total_reimbursement,
            acquisition_cost=fill.acquisition_cost,
            dispensing_fee=fill.dispensing_fee,
            gross_margin=round(gross_margin, 2),
            gross_margin_pct=round(gross_margin_pct, 2),
            net_margin=round(net_margin, 2),
            margin_status=status,
            nadac_benchmark=round(nadac_benchmark, 2),
            nadac_spread=round(nadac_spread, 2),
            awp_discount_pct=round(awp_discount, 2),
            improvement_potential=round(improvement, 2),
            recommendations=recommendations
        )

    def batch_analyze(self, fills: List[FillRecord]) -> Dict[str, Any]:
        """Analyze margin for a batch of fills."""
        analyses = [self.analyze_fill(f) for f in fills]

        total_reimbursement = sum(a.reimbursement for a in analyses)
        total_cost = sum(a.acquisition_cost for a in analyses)
        total_gross_margin = sum(a.gross_margin for a in analyses)
        total_net_margin = sum(a.net_margin for a in analyses)

        status_counts = defaultdict(int)
        payer_margins: Dict[str, List[float]] = defaultdict(list)
        drug_margins: Dict[str, List[float]] = defaultdict(list)
        underwater_fills = []

        for i, analysis in enumerate(analyses):
            status_counts[analysis.margin_status.value] += 1
            payer_margins[fills[i].payer_name].append(analysis.gross_margin)
            drug_margins[analysis.drug_name].append(analysis.gross_margin)

            if analysis.margin_status in (MarginStatus.UNDERWATER, MarginStatus.SEVERELY_UNDERWATER):
                underwater_fills.append({
                    "fill_id": analysis.fill_id,
                    "drug": analysis.drug_name,
                    "loss": round(abs(analysis.gross_margin), 2),
                    "payer": fills[i].payer_name
                })

        # Top losers
        drug_totals = {
            drug: sum(margins)
            for drug, margins in drug_margins.items()
        }
        worst_drugs = sorted(drug_totals.items(), key=lambda x: x[1])[:10]

        payer_totals = {
            payer: sum(margins)
            for payer, margins in payer_margins.items()
        }
        worst_payers = sorted(payer_totals.items(), key=lambda x: x[1])[:5]

        return {
            "summary": {
                "total_fills": len(fills),
                "total_reimbursement": round(total_reimbursement, 2),
                "total_acquisition_cost": round(total_cost, 2),
                "total_gross_margin": round(total_gross_margin, 2),
                "total_net_margin": round(total_net_margin, 2),
                "overall_margin_pct": round(
                    (total_gross_margin / total_reimbursement * 100)
                    if total_reimbursement else 0, 2
                ),
                "avg_margin_per_fill": round(
                    total_gross_margin / len(fills) if fills else 0, 2
                )
            },
            "status_breakdown": dict(status_counts),
            "underwater_count": (
                status_counts.get("underwater", 0) +
                status_counts.get("severely_underwater", 0)
            ),
            "total_improvement_potential": round(
                sum(a.improvement_potential for a in analyses), 2
            ),
            "worst_performing_drugs": [
                {"drug": drug, "total_margin": round(margin, 2)}
                for drug, margin in worst_drugs
            ],
            "worst_performing_payers": [
                {"payer": payer, "total_margin": round(margin, 2)}
                for payer, margin in worst_payers
            ],
            "underwater_fills": sorted(
                underwater_fills, key=lambda x: x["loss"], reverse=True
            )[:20],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


class GenericSubstitutionFinder:
    """Identifies opportunities for generic substitution to improve margins."""

    def __init__(self, pricing_db: Dict[str, DrugPricing]):
        self.pricing_db = pricing_db
        self._gpi_groups: Dict[str, List[DrugPricing]] = defaultdict(list)
        self._build_gpi_index()

    def _build_gpi_index(self):
        """Build GPI-based grouping of equivalent drugs."""
        for ndc, pricing in self.pricing_db.items():
            if pricing.gpi:
                self._gpi_groups[pricing.gpi].append(pricing)

    def find_opportunities(
        self, fills: List[FillRecord], min_savings_per_fill: float = 5.0
    ) -> List[Dict]:
        """Find generic substitution opportunities across fills."""
        opportunities = []

        for fill in fills:
            if fill.is_generic:
                continue  # Already generic

            pricing = self.pricing_db.get(fill.ndc)
            if not pricing or not pricing.gpi:
                continue

            # Find cheaper alternatives in same GPI group
            alternatives = self._gpi_groups.get(pricing.gpi, [])
            for alt in alternatives:
                if alt.ndc == fill.ndc:
                    continue
                if alt.drug_type != DrugType.GENERIC:
                    continue

                savings_per_unit = pricing.acquisition_cost_per_unit - alt.acquisition_cost_per_unit
                total_savings = savings_per_unit * fill.quantity

                if total_savings >= min_savings_per_fill:
                    opportunities.append({
                        "fill_id": fill.fill_id,
                        "current_drug": fill.drug_name,
                        "current_ndc": fill.ndc,
                        "current_cost": round(fill.acquisition_cost, 2),
                        "alternative_drug": alt.drug_name,
                        "alternative_ndc": alt.ndc,
                        "alternative_cost": round(alt.acquisition_cost_per_unit * fill.quantity, 2),
                        "savings_per_fill": round(total_savings, 2),
                        "annualized_savings": round(total_savings * (365 / fill.days_supply), 2),
                        "payer": fill.payer_name,
                        "patient_id": fill.patient_id
                    })

        opportunities.sort(key=lambda x: x["savings_per_fill"], reverse=True)
        return opportunities


class FillRoutingOptimizer:
    """Optimizes which pharmacy fills prescriptions for maximum profitability."""

    def __init__(self):
        self.pharmacy_costs: Dict[str, Dict[str, float]] = {}  # pharmacy -> {ndc: cost}
        self.pharmacy_fees: Dict[str, float] = {}  # pharmacy -> avg dispensing fee

    def add_pharmacy(
        self,
        pharmacy_id: str,
        acquisition_costs: Dict[str, float],
        avg_dispensing_fee: float
    ):
        """Add a pharmacy with its cost structure."""
        self.pharmacy_costs[pharmacy_id] = acquisition_costs
        self.pharmacy_fees[pharmacy_id] = avg_dispensing_fee

    def optimize_routing(
        self,
        fills: List[FillRecord],
        reimbursement_rates: Dict[str, float]
    ) -> Dict[str, Any]:
        """Find optimal routing of fills across pharmacies."""
        if not self.pharmacy_costs:
            return {"error": "No pharmacy data loaded"}

        routing_plan = []
        total_current_margin = 0.0
        total_optimized_margin = 0.0

        for fill in fills:
            current_margin = fill.total_reimbursement - fill.acquisition_cost

            best_pharmacy = None
            best_margin = current_margin

            for pharm_id, costs in self.pharmacy_costs.items():
                if fill.ndc in costs:
                    alt_cost = costs[fill.ndc] * fill.quantity
                    alt_fee = self.pharmacy_fees.get(pharm_id, 0)
                    reimb = reimbursement_rates.get(fill.ndc, fill.total_reimbursement)
                    alt_margin = reimb - alt_cost

                    if alt_margin > best_margin:
                        best_margin = alt_margin
                        best_pharmacy = pharm_id

            total_current_margin += current_margin
            total_optimized_margin += best_margin

            if best_pharmacy:
                routing_plan.append({
                    "fill_id": fill.fill_id,
                    "drug": fill.drug_name,
                    "current_pharmacy": fill.pharmacy_npi,
                    "recommended_pharmacy": best_pharmacy,
                    "current_margin": round(current_margin, 2),
                    "optimized_margin": round(best_margin, 2),
                    "improvement": round(best_margin - current_margin, 2)
                })

        return {
            "total_fills": len(fills),
            "reroutable_fills": len(routing_plan),
            "current_total_margin": round(total_current_margin, 2),
            "optimized_total_margin": round(total_optimized_margin, 2),
            "total_improvement": round(total_optimized_margin - total_current_margin, 2),
            "routing_recommendations": routing_plan[:50],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
