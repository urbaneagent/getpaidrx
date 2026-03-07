"""
GetPaidRx - Generic Effective Rate (GER) Monitor
Tracks the effective reimbursement rate pharmacies receive for generic
medications vs MAC/NADAC benchmarks, detects underwater claims, and
identifies PBM contract performance issues.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import statistics
import math


class ClaimStatus(Enum):
    PAID = "paid"
    REJECTED = "rejected"
    REVERSED = "reversed"
    PENDING = "pending"


class ReimbursementStatus(Enum):
    PROFITABLE = "profitable"
    BREAK_EVEN = "break_even"
    UNDERWATER = "underwater"
    SEVERELY_UNDERWATER = "severely_underwater"


@dataclass
class GenericDrug:
    """Generic drug with pricing benchmarks."""
    ndc: str
    drug_name: str
    gpi: str  # Generic Product Identifier
    strength: str
    dosage_form: str
    manufacturer: str
    nadac_per_unit: float
    mac_per_unit: Optional[float] = None  # Maximum Allowable Cost
    awp_per_unit: float = 0.0
    wac_per_unit: float = 0.0
    acquisition_cost: float = 0.0
    last_price_update: str = ""


@dataclass
class GenericClaim:
    """Individual generic drug claim with reimbursement detail."""
    claim_id: str
    ndc: str
    drug_name: str
    gpi: str
    fill_date: str
    quantity: float
    days_supply: int
    payer_id: str
    payer_name: str
    pbm: str
    ingredient_paid: float
    dispensing_fee: float
    total_paid: float
    patient_copay: float
    acquisition_cost: float
    nadac_total: float
    mac_total: Optional[float] = None
    status: ClaimStatus = ClaimStatus.PAID
    bin_number: str = ""
    pcn: str = ""
    group_id: str = ""
    pharmacy_npi: str = ""


@dataclass
class GERResult:
    """GER calculation result for a drug or drug group."""
    identifier: str  # NDC or GPI
    drug_name: str
    total_claims: int = 0
    total_quantity: float = 0.0
    total_ingredient_paid: float = 0.0
    total_dispensing_fees: float = 0.0
    total_acquisition_cost: float = 0.0
    total_nadac: float = 0.0
    ger: float = 0.0  # Total paid / Total NADAC
    effective_rate_per_unit: float = 0.0
    nadac_per_unit: float = 0.0
    spread: float = 0.0  # $ difference per unit
    spread_pct: float = 0.0
    underwater_claims: int = 0
    underwater_amount: float = 0.0
    reimbursement_status: ReimbursementStatus = ReimbursementStatus.PROFITABLE
    payer_breakdown: Dict[str, Dict] = field(default_factory=dict)


class GERCalculator:
    """Calculates Generic Effective Rate metrics."""

    def __init__(self):
        self.claims: List[GenericClaim] = []
        self.drug_db: Dict[str, GenericDrug] = {}

    def add_drug(self, drug: GenericDrug):
        self.drug_db[drug.ndc] = drug

    def add_claim(self, claim: GenericClaim):
        self.claims.append(claim)

    def calculate_ger_by_ndc(self, ndc: str) -> GERResult:
        """Calculate GER for a specific NDC."""
        ndc_claims = [c for c in self.claims if c.ndc == ndc and c.status == ClaimStatus.PAID]
        drug = self.drug_db.get(ndc)
        drug_name = drug.drug_name if drug else ndc

        return self._compute_ger(ndc, drug_name, ndc_claims)

    def calculate_ger_by_gpi(self, gpi: str) -> GERResult:
        """Calculate GER for a GPI (all NDCs in product group)."""
        gpi_claims = [c for c in self.claims if c.gpi == gpi and c.status == ClaimStatus.PAID]

        # Find drug name from first matching claim
        drug_name = gpi_claims[0].drug_name if gpi_claims else gpi

        return self._compute_ger(gpi, drug_name, gpi_claims)

    def _compute_ger(
        self, identifier: str, drug_name: str, claims: List[GenericClaim]
    ) -> GERResult:
        """Core GER computation."""
        result = GERResult(identifier=identifier, drug_name=drug_name)

        if not claims:
            return result

        result.total_claims = len(claims)
        result.total_quantity = sum(c.quantity for c in claims)
        result.total_ingredient_paid = sum(c.ingredient_paid for c in claims)
        result.total_dispensing_fees = sum(c.dispensing_fee for c in claims)
        result.total_acquisition_cost = sum(c.acquisition_cost for c in claims)
        result.total_nadac = sum(c.nadac_total for c in claims)

        total_paid = sum(c.total_paid for c in claims)

        # GER = Total reimbursement / Total NADAC
        if result.total_nadac > 0:
            result.ger = round(total_paid / result.total_nadac, 4)

        # Effective rate per unit
        if result.total_quantity > 0:
            result.effective_rate_per_unit = round(
                total_paid / result.total_quantity, 4
            )
            result.nadac_per_unit = round(
                result.total_nadac / result.total_quantity, 4
            )

        # Spread analysis
        result.spread = round(result.effective_rate_per_unit - result.nadac_per_unit, 4)
        if result.nadac_per_unit > 0:
            result.spread_pct = round(
                (result.spread / result.nadac_per_unit) * 100, 2
            )

        # Underwater claims detection
        for claim in claims:
            if claim.total_paid < claim.acquisition_cost:
                result.underwater_claims += 1
                result.underwater_amount += (claim.acquisition_cost - claim.total_paid)
        result.underwater_amount = round(result.underwater_amount, 2)

        # Status classification
        if result.spread_pct > 10:
            result.reimbursement_status = ReimbursementStatus.PROFITABLE
        elif result.spread_pct > 0:
            result.reimbursement_status = ReimbursementStatus.BREAK_EVEN
        elif result.spread_pct > -15:
            result.reimbursement_status = ReimbursementStatus.UNDERWATER
        else:
            result.reimbursement_status = ReimbursementStatus.SEVERELY_UNDERWATER

        # Payer breakdown
        payer_groups: Dict[str, List[GenericClaim]] = defaultdict(list)
        for c in claims:
            payer_groups[c.payer_name].append(c)

        for payer, payer_claims in payer_groups.items():
            p_total_paid = sum(c.total_paid for c in payer_claims)
            p_total_nadac = sum(c.nadac_total for c in payer_claims)
            p_qty = sum(c.quantity for c in payer_claims)
            p_ger = round(p_total_paid / max(p_total_nadac, 0.01), 4)
            p_eff_rate = round(p_total_paid / max(p_qty, 1), 4)

            result.payer_breakdown[payer] = {
                "claims": len(payer_claims),
                "total_paid": round(p_total_paid, 2),
                "total_nadac": round(p_total_nadac, 2),
                "ger": p_ger,
                "effective_rate": p_eff_rate,
                "underwater": sum(
                    1 for c in payer_claims if c.total_paid < c.acquisition_cost
                ),
            }

        return result

    def calculate_portfolio_ger(self) -> Dict[str, Any]:
        """Calculate GER across entire generic portfolio."""
        paid_claims = [c for c in self.claims if c.status == ClaimStatus.PAID]
        if not paid_claims:
            return {"total_claims": 0}

        total_paid = sum(c.total_paid for c in paid_claims)
        total_nadac = sum(c.nadac_total for c in paid_claims)
        total_acquisition = sum(c.acquisition_cost for c in paid_claims)
        total_qty = sum(c.quantity for c in paid_claims)

        underwater = [c for c in paid_claims if c.total_paid < c.acquisition_cost]
        underwater_loss = sum(c.acquisition_cost - c.total_paid for c in underwater)

        # By PBM
        pbm_stats: Dict[str, Dict] = defaultdict(
            lambda: {"claims": 0, "paid": 0, "nadac": 0, "acquisition": 0}
        )
        for c in paid_claims:
            pbm_stats[c.pbm]["claims"] += 1
            pbm_stats[c.pbm]["paid"] += c.total_paid
            pbm_stats[c.pbm]["nadac"] += c.nadac_total
            pbm_stats[c.pbm]["acquisition"] += c.acquisition_cost

        pbm_gers = {}
        for pbm, stats in pbm_stats.items():
            pbm_gers[pbm] = {
                "claims": stats["claims"],
                "ger": round(stats["paid"] / max(stats["nadac"], 0.01), 4),
                "total_paid": round(stats["paid"], 2),
                "total_nadac": round(stats["nadac"], 2),
                "margin": round(stats["paid"] - stats["acquisition"], 2),
            }

        return {
            "total_claims": len(paid_claims),
            "total_quantity": round(total_qty, 2),
            "total_paid": round(total_paid, 2),
            "total_nadac": round(total_nadac, 2),
            "total_acquisition": round(total_acquisition, 2),
            "portfolio_ger": round(total_paid / max(total_nadac, 0.01), 4),
            "gross_margin": round(total_paid - total_acquisition, 2),
            "gross_margin_pct": round(
                (total_paid - total_acquisition) / max(total_paid, 0.01) * 100, 2
            ),
            "underwater_claims": len(underwater),
            "underwater_loss": round(underwater_loss, 2),
            "underwater_pct": round(len(underwater) / max(len(paid_claims), 1) * 100, 1),
            "by_pbm": pbm_gers,
        }


class UnderwaterAlertEngine:
    """Detects and alerts on underwater generic claims."""

    THRESHOLDS = {
        "single_claim_loss": -5.00,  # Alert if single claim loses >$5
        "daily_loss_total": -50.00,  # Alert if daily losses exceed $50
        "underwater_pct_threshold": 15.0,  # Alert if >15% claims underwater
        "ger_minimum": 0.85,  # Alert if GER drops below 0.85
    }

    def __init__(self, calculator: GERCalculator):
        self.calculator = calculator
        self.alerts: List[Dict] = []

    def scan_for_alerts(self) -> List[Dict]:
        """Scan all claims for alert conditions."""
        self.alerts = []

        portfolio = self.calculator.calculate_portfolio_ger()

        # Portfolio-level alerts
        if portfolio.get("portfolio_ger", 1.0) < self.THRESHOLDS["ger_minimum"]:
            self.alerts.append({
                "severity": "critical",
                "type": "low_portfolio_ger",
                "message": f"Portfolio GER at {portfolio['portfolio_ger']:.4f} — below {self.THRESHOLDS['ger_minimum']}",
                "impact": f"${abs(portfolio.get('gross_margin', 0)):,.2f} margin at risk",
            })

        if portfolio.get("underwater_pct", 0) > self.THRESHOLDS["underwater_pct_threshold"]:
            self.alerts.append({
                "severity": "high",
                "type": "high_underwater_rate",
                "message": f"{portfolio['underwater_pct']:.1f}% of claims are underwater",
                "impact": f"${portfolio.get('underwater_loss', 0):,.2f} total loss",
            })

        # NDC-level scanning
        ndc_groups: Dict[str, List] = defaultdict(list)
        for claim in self.calculator.claims:
            if claim.status == ClaimStatus.PAID:
                ndc_groups[claim.ndc].append(claim)

        for ndc, claims in ndc_groups.items():
            underwater_count = sum(
                1 for c in claims if c.total_paid < c.acquisition_cost
            )
            if underwater_count > 0:
                total_loss = sum(
                    c.acquisition_cost - c.total_paid
                    for c in claims if c.total_paid < c.acquisition_cost
                )
                if total_loss > abs(self.THRESHOLDS["single_claim_loss"]) * 3:
                    drug_name = claims[0].drug_name
                    self.alerts.append({
                        "severity": "medium",
                        "type": "ndc_underwater",
                        "ndc": ndc,
                        "drug": drug_name,
                        "message": f"{drug_name}: {underwater_count}/{len(claims)} claims underwater",
                        "impact": f"${total_loss:,.2f} loss",
                        "recommendation": "Review MAC pricing or switch manufacturers",
                    })

        # PBM-level performance
        for pbm, stats in portfolio.get("by_pbm", {}).items():
            if stats.get("ger", 1.0) < self.THRESHOLDS["ger_minimum"]:
                self.alerts.append({
                    "severity": "high",
                    "type": "pbm_low_ger",
                    "pbm": pbm,
                    "message": f"PBM '{pbm}' GER at {stats['ger']:.4f}",
                    "impact": f"{stats['claims']} claims affected",
                    "recommendation": "Escalate to PBM contract representative",
                })

        return sorted(self.alerts, key=lambda a: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(a["severity"], 4))


class GERReportGenerator:
    """Generates comprehensive GER reports."""

    def __init__(self, calculator: GERCalculator, alert_engine: UnderwaterAlertEngine):
        self.calculator = calculator
        self.alert_engine = alert_engine

    def generate_portfolio_report(self) -> str:
        """Generate full portfolio GER report."""
        portfolio = self.calculator.calculate_portfolio_ger()
        alerts = self.alert_engine.scan_for_alerts()

        lines = [
            f"{'='*60}",
            f"  GENERIC EFFECTIVE RATE (GER) PORTFOLIO REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"{'='*60}",
            f"",
            f"  📊 PORTFOLIO SUMMARY",
            f"  {'─'*45}",
            f"  Total Claims:       {portfolio.get('total_claims', 0):>10,}",
            f"  Total Quantity:     {portfolio.get('total_quantity', 0):>10,.0f} units",
            f"  Total Paid:         ${portfolio.get('total_paid', 0):>10,.2f}",
            f"  Total NADAC:        ${portfolio.get('total_nadac', 0):>10,.2f}",
            f"  Total Acquisition:  ${portfolio.get('total_acquisition', 0):>10,.2f}",
            f"",
            f"  📈 KEY METRICS",
            f"  {'─'*45}",
            f"  Portfolio GER:      {portfolio.get('portfolio_ger', 0):>10.4f}x",
            f"  Gross Margin:       ${portfolio.get('gross_margin', 0):>10,.2f}",
            f"  Gross Margin %:     {portfolio.get('gross_margin_pct', 0):>10.1f}%",
            f"  Underwater Claims:  {portfolio.get('underwater_claims', 0):>10,} ({portfolio.get('underwater_pct', 0):.1f}%)",
            f"  Underwater Loss:    ${portfolio.get('underwater_loss', 0):>10,.2f}",
        ]

        # PBM breakdown
        if portfolio.get("by_pbm"):
            lines.extend([f"", f"  🏢 PBM PERFORMANCE", f"  {'─'*45}"])
            for pbm, stats in sorted(
                portfolio["by_pbm"].items(),
                key=lambda x: x[1].get("ger", 0),
                reverse=True,
            ):
                ger_bar = "█" * int(stats.get("ger", 0) * 10) + "░" * (10 - int(stats.get("ger", 0) * 10))
                lines.append(
                    f"  {pbm:20s} GER: {stats.get('ger', 0):.4f} [{ger_bar}] "
                    f"Claims: {stats.get('claims', 0):>5}"
                )

        # Alerts
        if alerts:
            lines.extend([f"", f"  🚨 ALERTS ({len(alerts)})", f"  {'─'*45}"])
            severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
            for alert in alerts:
                icon = severity_icons.get(alert["severity"], "⚪")
                lines.append(f"  {icon} [{alert['severity'].upper()}] {alert['message']}")
                if alert.get("impact"):
                    lines.append(f"     Impact: {alert['impact']}")
                if alert.get("recommendation"):
                    lines.append(f"     → {alert['recommendation']}")

        return "\n".join(lines)

    def generate_drug_detail_report(self, ndc: str) -> str:
        """Generate detailed GER report for a specific drug."""
        result = self.calculator.calculate_ger_by_ndc(ndc)

        status_icon = {
            ReimbursementStatus.PROFITABLE: "✅",
            ReimbursementStatus.BREAK_EVEN: "⚠️",
            ReimbursementStatus.UNDERWATER: "🔴",
            ReimbursementStatus.SEVERELY_UNDERWATER: "🚨",
        }.get(result.reimbursement_status, "❓")

        lines = [
            f"  DRUG GER DETAIL: {result.drug_name}",
            f"  NDC: {result.identifier} | Status: {status_icon} {result.reimbursement_status.value}",
            f"  {'─'*45}",
            f"  Total Claims:    {result.total_claims:>8}",
            f"  Total Quantity:  {result.total_quantity:>8.0f}",
            f"  GER:             {result.ger:>8.4f}x",
            f"  Eff Rate/Unit:   ${result.effective_rate_per_unit:>7.4f}",
            f"  NADAC/Unit:      ${result.nadac_per_unit:>7.4f}",
            f"  Spread:          ${result.spread:>7.4f} ({result.spread_pct:>5.1f}%)",
            f"  Underwater:      {result.underwater_claims} claims (${result.underwater_amount:,.2f})",
        ]

        if result.payer_breakdown:
            lines.extend([f"", f"  By Payer:"])
            for payer, stats in result.payer_breakdown.items():
                lines.append(
                    f"    {payer:20s} GER: {stats['ger']:.4f} | "
                    f"{stats['claims']} claims | "
                    f"UW: {stats['underwater']}"
                )

        return "\n".join(lines)


if __name__ == "__main__":
    import random
    random.seed(42)

    calc = GERCalculator()

    # Register drugs
    drugs = [
        GenericDrug("12345-0100-30", "Metformin HCl 500mg", "27250050000110", "500mg",
                    "tablet", "Teva", nadac_per_unit=0.035, acquisition_cost=0.028),
        GenericDrug("12345-0200-90", "Lisinopril 10mg", "36200010001010", "10mg",
                    "tablet", "Lupin", nadac_per_unit=0.042, acquisition_cost=0.032),
        GenericDrug("12345-0300-60", "Omeprazole 20mg", "49270020000310", "20mg",
                    "capsule", "Dr. Reddy's", nadac_per_unit=0.065, acquisition_cost=0.048),
    ]
    for d in drugs:
        calc.add_drug(d)

    # Generate claims
    payers = [
        ("Anthem BCBS", "CVS Caremark"),
        ("UnitedHealth", "OptumRx"),
        ("Aetna", "Express Scripts"),
        ("KY Medicaid", "Magellan"),
    ]

    for i in range(120):
        drug = random.choice(drugs)
        payer_name, pbm = random.choice(payers)
        qty = random.choice([30, 60, 90])
        nadac_total = drug.nadac_per_unit * qty
        acq_cost = drug.acquisition_cost * qty

        # PBM spread varies
        spread_multiplier = random.uniform(0.7, 1.6)
        ingredient_paid = nadac_total * spread_multiplier
        disp_fee = random.uniform(0.50, 3.00)

        claim = GenericClaim(
            claim_id=f"CLM-{uuid.uuid4().hex[:8]}",
            ndc=drug.ndc, drug_name=drug.drug_name, gpi=drug.gpi,
            fill_date=(datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
            quantity=qty, days_supply=30,
            payer_id=payer_name.lower().replace(" ", "_"), payer_name=payer_name,
            pbm=pbm,
            ingredient_paid=round(ingredient_paid, 2),
            dispensing_fee=round(disp_fee, 2),
            total_paid=round(ingredient_paid + disp_fee, 2),
            patient_copay=round(random.uniform(0, 10), 2),
            acquisition_cost=round(acq_cost, 2),
            nadac_total=round(nadac_total, 2),
        )
        calc.add_claim(claim)

    alert_engine = UnderwaterAlertEngine(calc)
    reporter = GERReportGenerator(calc, alert_engine)

    print(reporter.generate_portfolio_report())
    print("\n")
    print(reporter.generate_drug_detail_report("12345-0100-30"))
