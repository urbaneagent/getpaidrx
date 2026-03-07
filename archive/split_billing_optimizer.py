"""
GetPaidRx - Split Billing Optimizer
Analyzes prescription claims to identify split-billing opportunities
where filling partial quantities across billing cycles or using
different coverage tiers maximizes pharmacy reimbursement.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import math


class BillingStrategy(Enum):
    STANDARD = "standard"  # Fill full qty on one claim
    SPLIT_DAYS_SUPPLY = "split_days_supply"  # Two fills to optimize copay/reimb
    PARTIAL_FILL = "partial_fill"  # Fill less than prescribed qty
    SHORT_CYCLE = "short_cycle"  # 14-day fills instead of 30
    MULTI_SOURCE = "multi_source"  # Different manufacturers for diff payers
    COUPON_SPLIT = "coupon_split"  # Apply manufacturer coupon strategically


class CoveragePhase(Enum):
    DEDUCTIBLE = "deductible"
    INITIAL_COVERAGE = "initial_coverage"
    COVERAGE_GAP = "coverage_gap"  # Medicare donut hole
    CATASTROPHIC = "catastrophic"


@dataclass
class PatientInsurance:
    """Patient insurance coverage details."""
    patient_id: str
    primary_payer: str
    primary_pbm: str
    has_secondary: bool = False
    secondary_payer: Optional[str] = None
    secondary_pbm: Optional[str] = None
    coverage_phase: CoveragePhase = CoveragePhase.INITIAL_COVERAGE
    deductible_remaining: float = 0.0
    oop_remaining: float = 0.0
    is_medicare_d: bool = False
    has_manufacturer_coupon: bool = False
    coupon_max_benefit: float = 0.0
    coupon_uses_remaining: int = 0


@dataclass
class PrescriptionOrder:
    """Prescription details for billing analysis."""
    rx_number: str
    patient_id: str
    ndc: str
    drug_name: str
    quantity_prescribed: float
    days_supply: int
    refills_remaining: int
    is_brand: bool = False
    is_specialty: bool = False
    is_controlled: bool = False
    dea_schedule: Optional[str] = None
    prescriber_npi: str = ""
    diagnosis_codes: List[str] = field(default_factory=list)


@dataclass
class ReimbursementScenario:
    """Projected reimbursement for a billing scenario."""
    scenario_id: str
    strategy: BillingStrategy
    description: str
    fills: List[Dict[str, Any]] = field(default_factory=list)
    total_quantity: float = 0.0
    total_reimbursement: float = 0.0
    total_patient_cost: float = 0.0
    pharmacy_profit: float = 0.0
    acquisition_cost: float = 0.0
    net_margin: float = 0.0
    net_margin_pct: float = 0.0
    compliance_notes: List[str] = field(default_factory=list)
    regulatory_flags: List[str] = field(default_factory=list)
    patient_benefit: str = ""


@dataclass
class BillingOptimizationResult:
    """Complete optimization result with all scenarios."""
    rx_number: str
    drug_name: str
    patient_id: str
    current_scenario: ReimbursementScenario
    optimized_scenarios: List[ReimbursementScenario] = field(default_factory=list)
    recommended_strategy: Optional[BillingStrategy] = None
    potential_savings: float = 0.0
    patient_savings: float = 0.0
    compliance_risk: str = "low"


class PayerRateEngine:
    """Simulates payer reimbursement calculations."""

    def __init__(self):
        self.payer_rates: Dict[str, Dict] = {}

    def add_payer_rate(
        self, payer: str, ndc: str, ingredient_rate: float,
        dispensing_fee: float, brand_discount: float = 0,
        copay_brand: float = 0, copay_generic: float = 0,
        days_supply_limit: int = 90,
    ):
        key = f"{payer}|{ndc}"
        self.payer_rates[key] = {
            "ingredient_rate": ingredient_rate,
            "dispensing_fee": dispensing_fee,
            "brand_discount": brand_discount,
            "copay_brand": copay_brand,
            "copay_generic": copay_generic,
            "days_supply_limit": days_supply_limit,
        }

    def calculate_reimbursement(
        self, payer: str, ndc: str, quantity: float, days_supply: int,
        is_brand: bool = False, coverage_phase: CoveragePhase = CoveragePhase.INITIAL_COVERAGE,
    ) -> Dict[str, float]:
        key = f"{payer}|{ndc}"
        rate = self.payer_rates.get(key)
        if not rate:
            # Default rates
            rate = {
                "ingredient_rate": 0.10 if not is_brand else 2.50,
                "dispensing_fee": 2.00,
                "brand_discount": 15.0,
                "copay_brand": 35.0,
                "copay_generic": 10.0,
                "days_supply_limit": 90,
            }

        ingredient_paid = rate["ingredient_rate"] * quantity
        if is_brand:
            ingredient_paid *= (1 - rate["brand_discount"] / 100)

        # Coverage phase adjustments
        phase_multiplier = {
            CoveragePhase.DEDUCTIBLE: 0.0,  # Patient pays all
            CoveragePhase.INITIAL_COVERAGE: 1.0,
            CoveragePhase.COVERAGE_GAP: 0.75,  # 25% manufacturer discount
            CoveragePhase.CATASTROPHIC: 1.15,  # Higher reimb, low patient cost
        }.get(coverage_phase, 1.0)

        ingredient_paid *= phase_multiplier
        dispensing_fee = rate["dispensing_fee"]

        copay = rate["copay_brand"] if is_brand else rate["copay_generic"]
        if coverage_phase == CoveragePhase.CATASTROPHIC:
            copay = min(copay, 5.0)
        elif coverage_phase == CoveragePhase.DEDUCTIBLE:
            copay = ingredient_paid + dispensing_fee  # Patient pays full

        total_paid = ingredient_paid + dispensing_fee

        return {
            "ingredient_paid": round(ingredient_paid, 2),
            "dispensing_fee": round(dispensing_fee, 2),
            "total_paid": round(total_paid, 2),
            "patient_copay": round(copay, 2),
            "pharmacy_received": round(total_paid, 2),
        }


class SplitBillingAnalyzer:
    """Analyzes and recommends optimal billing strategies."""

    def __init__(self, rate_engine: PayerRateEngine):
        self.rate_engine = rate_engine

    def analyze_prescription(
        self,
        rx: PrescriptionOrder,
        insurance: PatientInsurance,
        acquisition_cost_per_unit: float,
    ) -> BillingOptimizationResult:
        """Analyze all billing strategies for a prescription."""
        result = BillingOptimizationResult(
            rx_number=rx.rx_number,
            drug_name=rx.drug_name,
            patient_id=rx.patient_id,
            current_scenario=self._standard_scenario(rx, insurance, acquisition_cost_per_unit),
        )

        # Generate alternative scenarios
        scenarios = []

        # Split days supply (two 15-day fills vs one 30-day)
        if rx.days_supply >= 28 and not rx.is_controlled:
            split = self._split_days_supply_scenario(rx, insurance, acquisition_cost_per_unit)
            if split:
                scenarios.append(split)

        # Short cycle dispensing (14-day)
        if rx.days_supply >= 28 and insurance.is_medicare_d:
            short = self._short_cycle_scenario(rx, insurance, acquisition_cost_per_unit)
            if short:
                scenarios.append(short)

        # Coupon split strategy
        if insurance.has_manufacturer_coupon and rx.is_brand:
            coupon = self._coupon_split_scenario(rx, insurance, acquisition_cost_per_unit)
            if coupon:
                scenarios.append(coupon)

        # Partial fill (for coverage gap)
        if insurance.coverage_phase == CoveragePhase.COVERAGE_GAP:
            partial = self._partial_fill_scenario(rx, insurance, acquisition_cost_per_unit)
            if partial:
                scenarios.append(partial)

        # Evaluate and rank
        result.optimized_scenarios = sorted(
            scenarios, key=lambda s: s.pharmacy_profit, reverse=True
        )

        if result.optimized_scenarios:
            best = result.optimized_scenarios[0]
            if best.pharmacy_profit > result.current_scenario.pharmacy_profit:
                result.recommended_strategy = best.strategy
                result.potential_savings = round(
                    best.pharmacy_profit - result.current_scenario.pharmacy_profit, 2
                )
                result.patient_savings = round(
                    result.current_scenario.total_patient_cost - best.total_patient_cost, 2
                )

        return result

    def _standard_scenario(
        self, rx: PrescriptionOrder, insurance: PatientInsurance,
        acq_cost: float,
    ) -> ReimbursementScenario:
        """Standard single-fill scenario."""
        reimb = self.rate_engine.calculate_reimbursement(
            insurance.primary_payer, rx.ndc, rx.quantity_prescribed,
            rx.days_supply, rx.is_brand, insurance.coverage_phase,
        )

        total_acq = acq_cost * rx.quantity_prescribed
        profit = reimb["pharmacy_received"] - total_acq

        return ReimbursementScenario(
            scenario_id=f"SCN-STD-{uuid.uuid4().hex[:6]}",
            strategy=BillingStrategy.STANDARD,
            description=f"Standard fill: {rx.quantity_prescribed} units, {rx.days_supply} days",
            fills=[{
                "fill_number": 1,
                "quantity": rx.quantity_prescribed,
                "days_supply": rx.days_supply,
                "payer": insurance.primary_payer,
                "reimbursement": reimb,
            }],
            total_quantity=rx.quantity_prescribed,
            total_reimbursement=reimb["total_paid"],
            total_patient_cost=reimb["patient_copay"],
            pharmacy_profit=round(profit, 2),
            acquisition_cost=round(total_acq, 2),
            net_margin=round(profit, 2),
            net_margin_pct=round(profit / max(reimb["total_paid"], 0.01) * 100, 1),
        )

    def _split_days_supply_scenario(
        self, rx: PrescriptionOrder, insurance: PatientInsurance,
        acq_cost: float,
    ) -> Optional[ReimbursementScenario]:
        """Split into two fills to capture two dispensing fees."""
        half_qty = rx.quantity_prescribed / 2
        half_days = rx.days_supply // 2

        fill1 = self.rate_engine.calculate_reimbursement(
            insurance.primary_payer, rx.ndc, half_qty,
            half_days, rx.is_brand, insurance.coverage_phase,
        )
        fill2 = self.rate_engine.calculate_reimbursement(
            insurance.primary_payer, rx.ndc, half_qty,
            rx.days_supply - half_days, rx.is_brand, insurance.coverage_phase,
        )

        total_reimb = fill1["total_paid"] + fill2["total_paid"]
        total_copay = fill1["patient_copay"] + fill2["patient_copay"]
        total_acq = acq_cost * rx.quantity_prescribed
        profit = total_reimb - total_acq

        scenario = ReimbursementScenario(
            scenario_id=f"SCN-SPLIT-{uuid.uuid4().hex[:6]}",
            strategy=BillingStrategy.SPLIT_DAYS_SUPPLY,
            description=f"Split: 2x {half_qty:.0f} units ({half_days}+{rx.days_supply - half_days} days)",
            fills=[
                {"fill_number": 1, "quantity": half_qty, "days_supply": half_days, "reimbursement": fill1},
                {"fill_number": 2, "quantity": half_qty, "days_supply": rx.days_supply - half_days, "reimbursement": fill2},
            ],
            total_quantity=rx.quantity_prescribed,
            total_reimbursement=round(total_reimb, 2),
            total_patient_cost=round(total_copay, 2),
            pharmacy_profit=round(profit, 2),
            acquisition_cost=round(total_acq, 2),
            net_margin=round(profit, 2),
            net_margin_pct=round(profit / max(total_reimb, 0.01) * 100, 1),
            compliance_notes=[
                "Verify payer allows split billing",
                "Ensure both fills submitted within coverage period",
            ],
        )

        # Flag if patient pays double copay
        if total_copay > fill1["patient_copay"] * 1.5:
            scenario.regulatory_flags.append(
                "⚠️ Patient pays increased copay with split billing"
            )
            scenario.patient_benefit = "Patient copay increases — consider only if pharmacy margin justifies"

        return scenario

    def _short_cycle_scenario(
        self, rx: PrescriptionOrder, insurance: PatientInsurance,
        acq_cost: float,
    ) -> Optional[ReimbursementScenario]:
        """Medicare D short-cycle dispensing (14-day fills)."""
        num_fills = math.ceil(rx.days_supply / 14)
        qty_per_fill = rx.quantity_prescribed / (rx.days_supply / 14)

        fills = []
        total_reimb = 0
        total_copay = 0
        remaining_days = rx.days_supply

        for i in range(num_fills):
            fill_days = min(14, remaining_days)
            fill_qty = qty_per_fill if fill_days == 14 else (rx.quantity_prescribed / rx.days_supply) * fill_days

            reimb = self.rate_engine.calculate_reimbursement(
                insurance.primary_payer, rx.ndc, fill_qty,
                fill_days, rx.is_brand, insurance.coverage_phase,
            )
            fills.append({
                "fill_number": i + 1,
                "quantity": round(fill_qty, 1),
                "days_supply": fill_days,
                "reimbursement": reimb,
            })
            total_reimb += reimb["total_paid"]
            total_copay += reimb["patient_copay"]
            remaining_days -= fill_days

        total_acq = acq_cost * rx.quantity_prescribed
        profit = total_reimb - total_acq

        return ReimbursementScenario(
            scenario_id=f"SCN-SHORT-{uuid.uuid4().hex[:6]}",
            strategy=BillingStrategy.SHORT_CYCLE,
            description=f"Short cycle: {num_fills}x 14-day fills",
            fills=fills,
            total_quantity=rx.quantity_prescribed,
            total_reimbursement=round(total_reimb, 2),
            total_patient_cost=round(total_copay, 2),
            pharmacy_profit=round(profit, 2),
            acquisition_cost=round(total_acq, 2),
            net_margin=round(profit, 2),
            net_margin_pct=round(profit / max(total_reimb, 0.01) * 100, 1),
            compliance_notes=[
                "Permitted under Medicare Part D for LTC/ALF patients",
                "Must meet CMS short-cycle dispensing requirements",
            ],
            patient_benefit="Reduces medication waste; lower upfront cost per fill",
        )

    def _coupon_split_scenario(
        self, rx: PrescriptionOrder, insurance: PatientInsurance,
        acq_cost: float,
    ) -> Optional[ReimbursementScenario]:
        """Apply manufacturer coupon to maximize benefit."""
        reimb = self.rate_engine.calculate_reimbursement(
            insurance.primary_payer, rx.ndc, rx.quantity_prescribed,
            rx.days_supply, rx.is_brand, insurance.coverage_phase,
        )

        coupon_value = min(insurance.coupon_max_benefit, reimb["patient_copay"])
        adjusted_copay = reimb["patient_copay"] - coupon_value
        total_acq = acq_cost * rx.quantity_prescribed
        profit = reimb["pharmacy_received"] - total_acq

        scenario = ReimbursementScenario(
            scenario_id=f"SCN-COUP-{uuid.uuid4().hex[:6]}",
            strategy=BillingStrategy.COUPON_SPLIT,
            description=f"Standard fill with ${coupon_value:.2f} manufacturer coupon applied",
            fills=[{
                "fill_number": 1,
                "quantity": rx.quantity_prescribed,
                "days_supply": rx.days_supply,
                "reimbursement": reimb,
                "coupon_applied": coupon_value,
            }],
            total_quantity=rx.quantity_prescribed,
            total_reimbursement=reimb["total_paid"],
            total_patient_cost=round(adjusted_copay, 2),
            pharmacy_profit=round(profit, 2),
            acquisition_cost=round(total_acq, 2),
            net_margin=round(profit, 2),
            net_margin_pct=round(profit / max(reimb["total_paid"], 0.01) * 100, 1),
            compliance_notes=[
                "Manufacturer coupons NOT allowed for Medicare/Medicaid patients",
                "Verify coupon terms and conditions",
            ],
            patient_benefit=f"Patient saves ${coupon_value:.2f} via coupon",
        )

        if insurance.is_medicare_d:
            scenario.regulatory_flags.append(
                "🚨 ILLEGAL: Manufacturer coupons prohibited for Medicare Part D"
            )

        return scenario

    def _partial_fill_scenario(
        self, rx: PrescriptionOrder, insurance: PatientInsurance,
        acq_cost: float,
    ) -> Optional[ReimbursementScenario]:
        """Partial fill to manage coverage gap spending."""
        partial_qty = rx.quantity_prescribed * 0.75
        partial_days = int(rx.days_supply * 0.75)

        reimb = self.rate_engine.calculate_reimbursement(
            insurance.primary_payer, rx.ndc, partial_qty,
            partial_days, rx.is_brand, insurance.coverage_phase,
        )

        total_acq = acq_cost * partial_qty
        profit = reimb["pharmacy_received"] - total_acq

        return ReimbursementScenario(
            scenario_id=f"SCN-PART-{uuid.uuid4().hex[:6]}",
            strategy=BillingStrategy.PARTIAL_FILL,
            description=f"Partial fill: {partial_qty:.0f} units for {partial_days} days",
            fills=[{
                "fill_number": 1,
                "quantity": round(partial_qty, 1),
                "days_supply": partial_days,
                "reimbursement": reimb,
            }],
            total_quantity=round(partial_qty, 1),
            total_reimbursement=reimb["total_paid"],
            total_patient_cost=reimb["patient_copay"],
            pharmacy_profit=round(profit, 2),
            acquisition_cost=round(total_acq, 2),
            net_margin=round(profit, 2),
            net_margin_pct=round(profit / max(reimb["total_paid"], 0.01) * 100, 1),
            compliance_notes=[
                "Partial fills require prescriber authorization in some states",
                "Document reason for partial fill in pharmacy records",
            ],
            patient_benefit="Lower out-of-pocket during coverage gap",
        )

    def generate_optimization_report(self, result: BillingOptimizationResult) -> str:
        """Generate formatted optimization report."""
        lines = [
            f"{'='*60}",
            f"  SPLIT BILLING OPTIMIZATION REPORT",
            f"  Rx: {result.rx_number} | Drug: {result.drug_name}",
            f"{'='*60}",
            f"",
            f"  📋 CURRENT STRATEGY (Standard)",
            f"  {'─'*45}",
            f"  Reimbursement:    ${result.current_scenario.total_reimbursement:>10,.2f}",
            f"  Acquisition:      ${result.current_scenario.acquisition_cost:>10,.2f}",
            f"  Pharmacy Profit:  ${result.current_scenario.pharmacy_profit:>10,.2f}",
            f"  Patient Cost:     ${result.current_scenario.total_patient_cost:>10,.2f}",
            f"  Margin:           {result.current_scenario.net_margin_pct:>10.1f}%",
        ]

        for i, scenario in enumerate(result.optimized_scenarios):
            icon = "🏆" if i == 0 else "📊"
            improvement = scenario.pharmacy_profit - result.current_scenario.pharmacy_profit

            lines.extend([
                f"",
                f"  {icon} SCENARIO: {scenario.strategy.value.upper()}",
                f"  {scenario.description}",
                f"  {'─'*45}",
                f"  Reimbursement:    ${scenario.total_reimbursement:>10,.2f}",
                f"  Acquisition:      ${scenario.acquisition_cost:>10,.2f}",
                f"  Pharmacy Profit:  ${scenario.pharmacy_profit:>10,.2f}  "
                f"({'⬆' if improvement > 0 else '⬇'} ${abs(improvement):.2f})",
                f"  Patient Cost:     ${scenario.total_patient_cost:>10,.2f}",
                f"  Margin:           {scenario.net_margin_pct:>10.1f}%",
            ])

            if scenario.regulatory_flags:
                for flag in scenario.regulatory_flags:
                    lines.append(f"  {flag}")

            if scenario.patient_benefit:
                lines.append(f"  Patient: {scenario.patient_benefit}")

        if result.recommended_strategy:
            lines.extend([
                f"",
                f"  {'='*45}",
                f"  ✅ RECOMMENDED: {result.recommended_strategy.value.upper()}",
                f"  Pharmacy Gain: ${result.potential_savings:,.2f}",
                f"  Patient Savings: ${result.patient_savings:,.2f}",
            ])

        return "\n".join(lines)


if __name__ == "__main__":
    rate_engine = PayerRateEngine()

    # Add payer rates
    ndc = "00078-0123-30"
    rate_engine.add_payer_rate(
        "Anthem", ndc, ingredient_rate=3.50, dispensing_fee=2.50,
        brand_discount=12, copay_brand=45, copay_generic=15,
    )

    analyzer = SplitBillingAnalyzer(rate_engine)

    rx = PrescriptionOrder(
        rx_number="RX-2026-00123",
        patient_id="PT-001",
        ndc=ndc,
        drug_name="Entresto 49/51mg",
        quantity_prescribed=60,
        days_supply=30,
        refills_remaining=5,
        is_brand=True,
    )

    insurance = PatientInsurance(
        patient_id="PT-001",
        primary_payer="Anthem",
        primary_pbm="CVS Caremark",
        is_medicare_d=False,
        has_manufacturer_coupon=True,
        coupon_max_benefit=30.00,
        coupon_uses_remaining=6,
    )

    result = analyzer.analyze_prescription(rx, insurance, acquisition_cost_per_unit=2.80)
    print(analyzer.generate_optimization_report(result))
