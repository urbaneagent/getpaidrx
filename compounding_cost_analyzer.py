"""
GetPaidRx - Pharmacy Compounding Cost Analyzer
Calculates ingredient costs, labor, overhead, and margin analysis
for compounded medications with reimbursement comparison against
commercial alternatives and payer-specific pricing.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import math


class CompoundType(Enum):
    STERILE = "sterile"
    NON_STERILE = "non_sterile"
    HAZARDOUS = "hazardous"
    RADIOPHARMACEUTICAL = "radiopharmaceutical"


class PricingBasis(Enum):
    AWP = "awp"
    WAC = "wac"
    NADAC = "nadac"
    COST_PLUS = "cost_plus"
    FEE_SCHEDULE = "fee_schedule"


class BUDType(Enum):
    """Beyond Use Date categories per USP 795/797."""
    USP_795_NONAQUEOUS = "usp_795_nonaqueous"  # 180 days
    USP_795_AQUEOUS = "usp_795_aqueous"  # 14 days
    USP_797_CAT1 = "usp_797_cat1"  # 12 hours (BUD <= 12h)
    USP_797_CAT2 = "usp_797_cat2"  # 1-4 days
    USP_797_CAT3 = "usp_797_cat3"  # Custom stability testing


@dataclass
class Ingredient:
    """Individual compounding ingredient."""
    ndc: str
    name: str
    strength: str
    unit_of_measure: str  # g, mg, mL, etc.
    cost_per_unit: float
    quantity_on_hand: float = 0
    supplier: str = ""
    lot_number: str = ""
    expiration_date: str = ""
    is_hazardous: bool = False
    is_controlled: bool = False
    schedule: Optional[str] = None  # DEA schedule


@dataclass
class FormulaIngredient:
    """Ingredient with quantity as used in a formula."""
    ingredient: Ingredient
    quantity_needed: float
    overage_pct: float = 10.0  # Standard overage percentage
    actual_quantity: float = 0.0  # With overage applied


@dataclass
class LaborRate:
    """Labor cost component."""
    role: str  # pharmacist, technician
    hourly_rate: float
    minutes_required: float
    verification_minutes: float = 0


@dataclass
class CompoundFormula:
    """Complete compounding formula definition."""
    formula_id: str
    name: str
    compound_type: CompoundType
    dosage_form: str  # capsule, cream, solution, injection
    route: str  # oral, topical, IV, IM
    strength: str
    bud_type: BUDType
    ingredients: List[FormulaIngredient] = field(default_factory=list)
    labor: List[LaborRate] = field(default_factory=list)
    equipment_costs: Dict[str, float] = field(default_factory=dict)
    packaging_cost: float = 0.0
    quality_testing_cost: float = 0.0
    batch_size: int = 1
    units_per_batch: int = 1
    commercial_alternative_ndc: Optional[str] = None
    commercial_alternative_cost: Optional[float] = None


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a compounded preparation."""
    formula_id: str
    ingredient_cost: float = 0.0
    ingredient_details: List[Dict] = field(default_factory=list)
    labor_cost: float = 0.0
    labor_details: List[Dict] = field(default_factory=list)
    equipment_cost: float = 0.0
    packaging_cost: float = 0.0
    quality_testing_cost: float = 0.0
    overhead_cost: float = 0.0
    total_cost: float = 0.0
    cost_per_unit: float = 0.0
    units_produced: int = 0
    margin_analysis: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PayerReimbursement:
    """Payer-specific reimbursement for compounds."""
    payer_id: str
    payer_name: str
    pricing_basis: PricingBasis
    base_rate: float
    dispensing_fee: float
    compound_modifier: float = 1.0  # Multiplier for compound claims
    ingredient_markup_pct: float = 0.0
    max_reimbursement: Optional[float] = None
    requires_prior_auth: bool = False
    compound_code: Optional[str] = None  # HCPCS or billing code


class IngredientCostCalculator:
    """Calculates ingredient costs with overage and waste tracking."""

    def __init__(self, ingredients_db: Optional[Dict[str, Ingredient]] = None):
        self.ingredients_db = ingredients_db or {}
        self.waste_log: List[Dict] = []

    def calculate_ingredient_cost(
        self, formula_ingredient: FormulaIngredient
    ) -> Dict[str, float]:
        """Calculate cost for a single ingredient including overage."""
        base_qty = formula_ingredient.quantity_needed
        overage = base_qty * (formula_ingredient.overage_pct / 100)
        actual_qty = base_qty + overage
        formula_ingredient.actual_quantity = actual_qty

        cost = actual_qty * formula_ingredient.ingredient.cost_per_unit
        waste_cost = overage * formula_ingredient.ingredient.cost_per_unit

        return {
            "ingredient": formula_ingredient.ingredient.name,
            "base_quantity": round(base_qty, 4),
            "overage_quantity": round(overage, 4),
            "actual_quantity": round(actual_qty, 4),
            "unit": formula_ingredient.ingredient.unit_of_measure,
            "cost_per_unit": formula_ingredient.ingredient.cost_per_unit,
            "base_cost": round(base_qty * formula_ingredient.ingredient.cost_per_unit, 2),
            "overage_cost": round(waste_cost, 2),
            "total_cost": round(cost, 2),
        }

    def calculate_batch_ingredients(
        self, formula: CompoundFormula
    ) -> Tuple[float, List[Dict]]:
        """Calculate total ingredient cost for a batch."""
        total = 0.0
        details = []

        for fi in formula.ingredients:
            # Scale to batch size
            scaled = FormulaIngredient(
                ingredient=fi.ingredient,
                quantity_needed=fi.quantity_needed * formula.batch_size,
                overage_pct=fi.overage_pct,
            )
            result = self.calculate_ingredient_cost(scaled)
            total += result["total_cost"]
            details.append(result)

            # Track waste
            self.waste_log.append({
                "formula_id": formula.formula_id,
                "ingredient": fi.ingredient.name,
                "waste_amount": result["overage_quantity"],
                "waste_cost": result["overage_cost"],
                "timestamp": datetime.now().isoformat(),
            })

        return total, details


class LaborCostCalculator:
    """Calculates labor costs for compounding operations."""

    COMPLEXITY_MULTIPLIERS = {
        CompoundType.NON_STERILE: 1.0,
        CompoundType.STERILE: 1.5,
        CompoundType.HAZARDOUS: 2.0,
        CompoundType.RADIOPHARMACEUTICAL: 2.5,
    }

    def calculate_labor_cost(
        self, formula: CompoundFormula
    ) -> Tuple[float, List[Dict]]:
        """Calculate labor cost including complexity adjustments."""
        multiplier = self.COMPLEXITY_MULTIPLIERS.get(formula.compound_type, 1.0)
        total = 0.0
        details = []

        for labor in formula.labor:
            adjusted_minutes = labor.minutes_required * multiplier
            total_minutes = adjusted_minutes + labor.verification_minutes
            cost = (total_minutes / 60) * labor.hourly_rate

            details.append({
                "role": labor.role,
                "hourly_rate": labor.hourly_rate,
                "base_minutes": labor.minutes_required,
                "complexity_multiplier": multiplier,
                "adjusted_minutes": round(adjusted_minutes, 1),
                "verification_minutes": labor.verification_minutes,
                "total_minutes": round(total_minutes, 1),
                "cost": round(cost, 2),
            })
            total += cost

        return round(total, 2), details


class OverheadCalculator:
    """Calculates overhead allocation for compounding."""

    DEFAULT_RATES = {
        "facility": 15.00,  # per compound
        "utilities": 5.00,
        "insurance": 8.00,
        "depreciation": 12.00,
        "regulatory_compliance": 10.00,
    }

    STERILE_SURCHARGE = {
        "cleanroom_maintenance": 25.00,
        "environmental_monitoring": 15.00,
        "media_fill_allocation": 10.00,
    }

    def calculate_overhead(
        self, formula: CompoundFormula, custom_rates: Optional[Dict] = None
    ) -> float:
        """Calculate overhead allocation."""
        rates = custom_rates or self.DEFAULT_RATES
        total = sum(rates.values())

        if formula.compound_type in (CompoundType.STERILE, CompoundType.HAZARDOUS):
            total += sum(self.STERILE_SURCHARGE.values())

        if formula.compound_type == CompoundType.HAZARDOUS:
            total += 20.00  # Hazardous waste disposal allocation

        return round(total * formula.batch_size, 2)


class ReimbursementAnalyzer:
    """Analyzes payer reimbursement against compounding costs."""

    def __init__(self):
        self.payer_contracts: Dict[str, PayerReimbursement] = {}

    def add_payer_contract(self, contract: PayerReimbursement):
        self.payer_contracts[contract.payer_id] = contract

    def calculate_reimbursement(
        self, payer_id: str, ingredient_cost: float, units: int = 1
    ) -> Dict[str, Any]:
        """Calculate expected reimbursement from a payer."""
        contract = self.payer_contracts.get(payer_id)
        if not contract:
            return {"error": f"No contract for payer {payer_id}"}

        if contract.pricing_basis == PricingBasis.COST_PLUS:
            base = ingredient_cost * (1 + contract.ingredient_markup_pct / 100)
            reimbursement = base * contract.compound_modifier + contract.dispensing_fee
        elif contract.pricing_basis == PricingBasis.FEE_SCHEDULE:
            reimbursement = contract.base_rate * units + contract.dispensing_fee
        else:
            # AWP/WAC/NADAC based
            reimbursement = contract.base_rate * units * contract.compound_modifier + contract.dispensing_fee

        if contract.max_reimbursement:
            reimbursement = min(reimbursement, contract.max_reimbursement)

        return {
            "payer_id": payer_id,
            "payer_name": contract.payer_name,
            "pricing_basis": contract.pricing_basis.value,
            "reimbursement": round(reimbursement, 2),
            "dispensing_fee": contract.dispensing_fee,
            "requires_prior_auth": contract.requires_prior_auth,
            "compound_code": contract.compound_code,
        }

    def analyze_margin_by_payer(
        self, total_cost: float, ingredient_cost: float, units: int = 1
    ) -> List[Dict[str, Any]]:
        """Analyze margins across all payer contracts."""
        results = []
        for payer_id in self.payer_contracts:
            reimb = self.calculate_reimbursement(payer_id, ingredient_cost, units)
            if "error" in reimb:
                continue

            margin = reimb["reimbursement"] - total_cost
            margin_pct = (margin / max(total_cost, 0.01)) * 100

            results.append({
                **reimb,
                "total_cost": round(total_cost, 2),
                "margin": round(margin, 2),
                "margin_pct": round(margin_pct, 1),
                "profitable": margin > 0,
            })

        results.sort(key=lambda x: x.get("margin", 0), reverse=True)
        return results


class CompoundingCostAnalyzer:
    """Main orchestrator for compounding cost analysis."""

    def __init__(self):
        self.ingredient_calc = IngredientCostCalculator()
        self.labor_calc = LaborCostCalculator()
        self.overhead_calc = OverheadCalculator()
        self.reimbursement = ReimbursementAnalyzer()
        self.cost_history: List[CostBreakdown] = []

    def analyze_formula(self, formula: CompoundFormula) -> CostBreakdown:
        """Perform complete cost analysis for a formula."""
        breakdown = CostBreakdown(
            formula_id=formula.formula_id,
            units_produced=formula.units_per_batch * formula.batch_size,
        )

        # Ingredient costs
        breakdown.ingredient_cost, breakdown.ingredient_details = (
            self.ingredient_calc.calculate_batch_ingredients(formula)
        )

        # Labor costs
        breakdown.labor_cost, breakdown.labor_details = (
            self.labor_calc.calculate_labor_cost(formula)
        )

        # Equipment costs
        breakdown.equipment_cost = sum(formula.equipment_costs.values())

        # Packaging
        breakdown.packaging_cost = formula.packaging_cost * formula.batch_size

        # Quality testing
        breakdown.quality_testing_cost = formula.quality_testing_cost

        # Overhead
        breakdown.overhead_cost = self.overhead_calc.calculate_overhead(formula)

        # Totals
        breakdown.total_cost = round(
            breakdown.ingredient_cost +
            breakdown.labor_cost +
            breakdown.equipment_cost +
            breakdown.packaging_cost +
            breakdown.quality_testing_cost +
            breakdown.overhead_cost,
            2,
        )

        breakdown.cost_per_unit = round(
            breakdown.total_cost / max(breakdown.units_produced, 1), 2
        )

        # Margin analysis across payers
        payer_margins = self.reimbursement.analyze_margin_by_payer(
            breakdown.total_cost, breakdown.ingredient_cost, breakdown.units_produced
        )
        breakdown.margin_analysis = {
            "by_payer": payer_margins,
            "avg_margin": round(
                sum(p.get("margin", 0) for p in payer_margins) / max(len(payer_margins), 1), 2
            ),
            "profitable_payers": sum(1 for p in payer_margins if p.get("profitable")),
            "total_payers": len(payer_margins),
        }

        # Commercial alternative comparison
        if formula.commercial_alternative_cost:
            savings = formula.commercial_alternative_cost - breakdown.cost_per_unit
            breakdown.margin_analysis["vs_commercial"] = {
                "commercial_cost": formula.commercial_alternative_cost,
                "compound_cost": breakdown.cost_per_unit,
                "savings_per_unit": round(savings, 2),
                "savings_pct": round(savings / formula.commercial_alternative_cost * 100, 1) if formula.commercial_alternative_cost > 0 else 0,
                "compound_cheaper": savings > 0,
            }

        self.cost_history.append(breakdown)
        return breakdown

    def generate_cost_report(self, breakdown: CostBreakdown, formula: CompoundFormula) -> str:
        """Generate formatted cost analysis report."""
        lines = [
            f"{'='*60}",
            f"  COMPOUNDING COST ANALYSIS",
            f"  Formula: {formula.name}",
            f"  Type: {formula.compound_type.value} | Form: {formula.dosage_form}",
            f"  Batch: {formula.batch_size} | Units: {breakdown.units_produced}",
            f"{'='*60}",
            f"",
            f"  💊 INGREDIENT COSTS: ${breakdown.ingredient_cost:,.2f}",
            f"  {'─'*45}",
        ]

        for detail in breakdown.ingredient_details:
            lines.append(
                f"  {detail['ingredient'][:25]:25s} "
                f"{detail['actual_quantity']:>8.2f} {detail['unit']:4s} "
                f"${detail['total_cost']:>8.2f}"
            )

        lines.extend([
            f"",
            f"  👷 LABOR COSTS: ${breakdown.labor_cost:,.2f}",
            f"  {'─'*45}",
        ])

        for detail in breakdown.labor_details:
            lines.append(
                f"  {detail['role']:25s} {detail['total_minutes']:>6.1f} min  "
                f"${detail['cost']:>8.2f}"
            )

        lines.extend([
            f"",
            f"  🏭 OTHER COSTS",
            f"  {'─'*45}",
            f"  Equipment:       ${breakdown.equipment_cost:>10,.2f}",
            f"  Packaging:       ${breakdown.packaging_cost:>10,.2f}",
            f"  Quality Testing: ${breakdown.quality_testing_cost:>10,.2f}",
            f"  Overhead:        ${breakdown.overhead_cost:>10,.2f}",
            f"",
            f"  {'='*45}",
            f"  TOTAL BATCH COST:  ${breakdown.total_cost:>10,.2f}",
            f"  COST PER UNIT:     ${breakdown.cost_per_unit:>10,.2f}",
            f"  {'='*45}",
        ])

        if breakdown.margin_analysis.get("by_payer"):
            lines.extend([f"", f"  💰 PAYER MARGIN ANALYSIS", f"  {'─'*45}"])
            for pm in breakdown.margin_analysis["by_payer"]:
                profit_icon = "✅" if pm.get("profitable") else "❌"
                lines.append(
                    f"  {profit_icon} {pm['payer_name']:20s} "
                    f"Reimb: ${pm['reimbursement']:>8.2f}  "
                    f"Margin: ${pm['margin']:>8.2f} ({pm['margin_pct']:>5.1f}%)"
                )

        vs = breakdown.margin_analysis.get("vs_commercial")
        if vs:
            lines.extend([
                f"",
                f"  🏪 VS COMMERCIAL ALTERNATIVE",
                f"  {'─'*45}",
                f"  Commercial: ${vs['commercial_cost']:,.2f}/unit",
                f"  Compound:   ${vs['compound_cost']:,.2f}/unit",
                f"  Savings:    ${vs['savings_per_unit']:,.2f} ({vs['savings_pct']:.1f}%)",
                f"  {'✅ Compounding is cheaper' if vs['compound_cheaper'] else '❌ Commercial is cheaper'}",
            ])

        return "\n".join(lines)


if __name__ == "__main__":
    analyzer = CompoundingCostAnalyzer()

    # Add payer contracts
    analyzer.reimbursement.add_payer_contract(PayerReimbursement(
        payer_id="anthem", payer_name="Anthem BCBS",
        pricing_basis=PricingBasis.COST_PLUS,
        base_rate=0, dispensing_fee=15.00,
        ingredient_markup_pct=40, compound_modifier=1.2,
    ))
    analyzer.reimbursement.add_payer_contract(PayerReimbursement(
        payer_id="aetna", payer_name="Aetna",
        pricing_basis=PricingBasis.FEE_SCHEDULE,
        base_rate=8.50, dispensing_fee=12.00,
        compound_modifier=1.0,
    ))
    analyzer.reimbursement.add_payer_contract(PayerReimbursement(
        payer_id="medicaid", payer_name="KY Medicaid",
        pricing_basis=PricingBasis.NADAC,
        base_rate=5.25, dispensing_fee=10.80,
        compound_modifier=0.9,
    ))

    # Define a formula
    formula = CompoundFormula(
        formula_id="RX-COMP-001",
        name="Progesterone 200mg Vaginal Suppositories",
        compound_type=CompoundType.NON_STERILE,
        dosage_form="suppository",
        route="vaginal",
        strength="200mg",
        bud_type=BUDType.USP_795_NONAQUEOUS,
        batch_size=1,
        units_per_batch=30,
        packaging_cost=2.50,
        quality_testing_cost=0,
        commercial_alternative_cost=45.00,
        ingredients=[
            FormulaIngredient(
                Ingredient("00000-0001-01", "Progesterone USP Micronized", "100%",
                           "g", 0.85, supplier="Medisca"),
                quantity_needed=6.0, overage_pct=10,
            ),
            FormulaIngredient(
                Ingredient("00000-0002-01", "Polyethylene Glycol 1450", "NF",
                           "g", 0.12, supplier="PCCA"),
                quantity_needed=25.0, overage_pct=5,
            ),
            FormulaIngredient(
                Ingredient("00000-0003-01", "Polyethylene Glycol 8000", "NF",
                           "g", 0.15, supplier="PCCA"),
                quantity_needed=15.0, overage_pct=5,
            ),
        ],
        labor=[
            LaborRate("pharmacist", 65.00, 15, verification_minutes=10),
            LaborRate("technician", 22.00, 30, verification_minutes=5),
        ],
        equipment_costs={"suppository_molds": 1.50, "hot_plate": 0.50},
    )

    breakdown = analyzer.analyze_formula(formula)
    print(analyzer.generate_cost_report(breakdown, formula))
