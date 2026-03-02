"""
GetPaidRx - Pharmacy Financial KPI Engine

Comprehensive financial KPI calculation engine for independent pharmacies.
Tracks profitability, cash flow, operational efficiency, and financial
health metrics. Powers the executive dashboard and investor reports.

Features:
  - 25+ pharmacy-specific KPIs
  - Profitability metrics (gross margin, net margin, EBITDA proxy)
  - Operational efficiency (scripts/day, labor cost ratio, inventory turns)
  - Cash flow indicators (DSO, DPO, cash conversion cycle)
  - Reimbursement health (underwater rate, payer mix, avg margin/rx)
  - Trending with period-over-period comparison
  - Industry benchmarking against NCPA Digest data
  - Financial health composite score
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass


# ============================================================
# Industry Benchmarks (NCPA Digest 2024-2025)
# ============================================================

NCPA_BENCHMARKS = {
    "gross_margin_pct": 22.5,       # % of revenue
    "net_profit_margin": 2.8,       # %
    "scripts_per_day": 175,         # average independent pharmacy
    "avg_revenue_per_rx": 62.50,    # $
    "inventory_turns": 12.0,        # per year
    "dso_days": 28,                 # days sales outstanding
    "labor_cost_pct": 12.5,         # % of revenue
    "generic_fill_rate": 88.0,      # %
    "underwater_rate": 8.0,         # % of claims
    "third_party_pct": 92.0,        # % of revenue from insurance
    "otc_front_end_pct": 8.0,      # % from OTC/front-end
    "dir_fees_pct": 1.5,           # DIR fees as % of revenue
    "cost_to_fill": 10.50,         # $ per prescription
}


@dataclass
class FinancialPeriod:
    """Financial data for a period (month/quarter/year)."""
    period: str                     # YYYY-MM or YYYY-QN
    revenue_rx: float = 0           # Prescription revenue
    revenue_otc: float = 0          # OTC/front-end revenue
    revenue_clinical: float = 0     # Clinical services (immunizations, MTM)
    cost_of_goods: float = 0        # COGS (drug acquisition)
    labor_cost: float = 0           # Pharmacy labor
    rent_utilities: float = 0       # Occupancy costs
    other_opex: float = 0           # Other operating expenses
    dir_fees: float = 0             # DIR fee clawbacks
    scripts_dispensed: int = 0
    generic_scripts: int = 0
    brand_scripts: int = 0
    underwater_claims: int = 0
    underwater_amount: float = 0
    total_claims: int = 0
    accounts_receivable: float = 0
    inventory_value: float = 0
    accounts_payable: float = 0
    cash_on_hand: float = 0
    clinical_encounters: int = 0


class PharmacyFinancialKPIEngine:
    """
    Calculates comprehensive financial KPIs for pharmacy performance
    monitoring and investor-ready reporting.
    """

    def __init__(self):
        self.periods: List[FinancialPeriod] = []

    def load_period(self, data: Dict[str, Any]) -> None:
        """Load a financial period."""
        period = FinancialPeriod(
            period=str(data.get("period", "")),
            revenue_rx=float(data.get("revenue_rx", 0)),
            revenue_otc=float(data.get("revenue_otc", 0)),
            revenue_clinical=float(data.get("revenue_clinical", 0)),
            cost_of_goods=float(data.get("cost_of_goods", 0)),
            labor_cost=float(data.get("labor_cost", 0)),
            rent_utilities=float(data.get("rent_utilities", 0)),
            other_opex=float(data.get("other_opex", 0)),
            dir_fees=float(data.get("dir_fees", 0)),
            scripts_dispensed=int(data.get("scripts_dispensed", 0)),
            generic_scripts=int(data.get("generic_scripts", 0)),
            brand_scripts=int(data.get("brand_scripts", 0)),
            underwater_claims=int(data.get("underwater_claims", 0)),
            underwater_amount=float(data.get("underwater_amount", 0)),
            total_claims=int(data.get("total_claims", 0)),
            accounts_receivable=float(data.get("accounts_receivable", 0)),
            inventory_value=float(data.get("inventory_value", 0)),
            accounts_payable=float(data.get("accounts_payable", 0)),
            cash_on_hand=float(data.get("cash_on_hand", 0)),
            clinical_encounters=int(data.get("clinical_encounters", 0)),
        )
        self.periods.append(period)

    def load_periods(self, periods_data: List[Dict[str, Any]]) -> int:
        """Load multiple financial periods."""
        for p in periods_data:
            self.load_period(p)
        return len(periods_data)

    # -------------------------------------------------------
    # Core KPI Calculation
    # -------------------------------------------------------

    def calculate_kpis(self, period_label: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate all KPIs for a specific period or the most recent.
        """
        if period_label:
            period = next((p for p in self.periods if p.period == period_label), None)
        else:
            period = self.periods[-1] if self.periods else None

        if not period:
            return {"error": "No period data available"}

        # Total revenue
        total_revenue = period.revenue_rx + period.revenue_otc + period.revenue_clinical
        if total_revenue == 0:
            return {"error": "Zero revenue — cannot compute KPIs"}

        # Gross profit
        gross_profit = total_revenue - period.cost_of_goods
        gross_margin_pct = round((gross_profit / total_revenue) * 100, 2)

        # Net adjusted for DIR fees
        net_revenue = total_revenue - period.dir_fees
        total_opex = period.labor_cost + period.rent_utilities + period.other_opex
        net_income = gross_profit - total_opex - period.dir_fees
        net_margin_pct = round((net_income / total_revenue) * 100, 2)

        # EBITDA proxy (no depreciation/amortization data, so operating income)
        ebitda_proxy = gross_profit - period.labor_cost - period.other_opex

        # Scripts per day (assuming 26 operating days/month)
        operating_days = 26
        scripts_per_day = round(period.scripts_dispensed / operating_days, 1) if period.scripts_dispensed > 0 else 0

        # Revenue per Rx
        avg_revenue_per_rx = round(
            total_revenue / period.scripts_dispensed, 2
        ) if period.scripts_dispensed > 0 else 0

        # Cost to fill
        cost_per_rx = round(
            (period.cost_of_goods + period.labor_cost) / period.scripts_dispensed, 2
        ) if period.scripts_dispensed > 0 else 0

        # Margin per Rx
        margin_per_rx = round(
            gross_profit / period.scripts_dispensed, 2
        ) if period.scripts_dispensed > 0 else 0

        # Generic fill rate
        generic_rate = round(
            (period.generic_scripts / period.scripts_dispensed) * 100, 1
        ) if period.scripts_dispensed > 0 else 0

        # Underwater rate
        underwater_rate = round(
            (period.underwater_claims / period.total_claims) * 100, 1
        ) if period.total_claims > 0 else 0

        # Labor cost ratio
        labor_pct = round((period.labor_cost / total_revenue) * 100, 2) if total_revenue > 0 else 0

        # Revenue mix
        rx_pct = round((period.revenue_rx / total_revenue) * 100, 1)
        otc_pct = round((period.revenue_otc / total_revenue) * 100, 1)
        clinical_pct = round((period.revenue_clinical / total_revenue) * 100, 1)

        # DIR fee impact
        dir_pct = round((period.dir_fees / total_revenue) * 100, 2) if total_revenue > 0 else 0

        # Cash flow metrics
        daily_revenue = total_revenue / 30
        dso = round(period.accounts_receivable / daily_revenue, 1) if daily_revenue > 0 else 0
        daily_cogs = period.cost_of_goods / 30
        dpo = round(period.accounts_payable / daily_cogs, 1) if daily_cogs > 0 else 0
        dio = round((period.inventory_value / period.cost_of_goods) * 30, 1) if period.cost_of_goods > 0 else 0
        ccc = round(dso + dio - dpo, 1)

        # Inventory turns (annualized)
        inv_turns = round(
            (period.cost_of_goods * 12) / period.inventory_value, 1
        ) if period.inventory_value > 0 else 0

        # Clinical revenue per encounter
        clinical_per_encounter = round(
            period.revenue_clinical / period.clinical_encounters, 2
        ) if period.clinical_encounters > 0 else 0

        kpis = {
            "period": period.period,
            "profitability": {
                "total_revenue": round(total_revenue, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_margin_pct": gross_margin_pct,
                "net_income": round(net_income, 2),
                "net_margin_pct": net_margin_pct,
                "ebitda_proxy": round(ebitda_proxy, 2),
                "dir_fee_impact": round(period.dir_fees, 2),
                "dir_fee_pct": dir_pct,
            },
            "operational_efficiency": {
                "scripts_per_day": scripts_per_day,
                "avg_revenue_per_rx": avg_revenue_per_rx,
                "cost_per_rx": cost_per_rx,
                "margin_per_rx": margin_per_rx,
                "generic_fill_rate": generic_rate,
                "labor_cost_pct": labor_pct,
                "inventory_turns_annualized": inv_turns,
            },
            "reimbursement_health": {
                "underwater_rate": underwater_rate,
                "underwater_amount": round(period.underwater_amount, 2),
                "total_claims": period.total_claims,
                "underwater_claims": period.underwater_claims,
            },
            "cash_flow": {
                "dso_days": dso,
                "dpo_days": dpo,
                "dio_days": dio,
                "cash_conversion_cycle": ccc,
                "cash_on_hand": round(period.cash_on_hand, 2),
                "accounts_receivable": round(period.accounts_receivable, 2),
                "accounts_payable": round(period.accounts_payable, 2),
                "inventory_value": round(period.inventory_value, 2),
            },
            "revenue_mix": {
                "prescription_pct": rx_pct,
                "otc_front_end_pct": otc_pct,
                "clinical_services_pct": clinical_pct,
                "clinical_per_encounter": clinical_per_encounter,
                "clinical_encounters": period.clinical_encounters,
            },
            "scripts_volume": {
                "total_dispensed": period.scripts_dispensed,
                "generic": period.generic_scripts,
                "brand": period.brand_scripts,
            },
        }

        # Benchmark comparison
        kpis["benchmarks"] = self._compare_benchmarks(kpis)

        # Financial health score
        kpis["financial_health"] = self._compute_health_score(kpis)

        return kpis

    # -------------------------------------------------------
    # Benchmarking
    # -------------------------------------------------------

    def _compare_benchmarks(self, kpis: Dict) -> Dict[str, Any]:
        """Compare KPIs against NCPA Digest benchmarks."""
        comparisons = {}

        metrics = [
            ("gross_margin_pct", kpis["profitability"]["gross_margin_pct"], NCPA_BENCHMARKS["gross_margin_pct"], True),
            ("scripts_per_day", kpis["operational_efficiency"]["scripts_per_day"], NCPA_BENCHMARKS["scripts_per_day"], True),
            ("avg_revenue_per_rx", kpis["operational_efficiency"]["avg_revenue_per_rx"], NCPA_BENCHMARKS["avg_revenue_per_rx"], True),
            ("generic_fill_rate", kpis["operational_efficiency"]["generic_fill_rate"], NCPA_BENCHMARKS["generic_fill_rate"], True),
            ("labor_cost_pct", kpis["operational_efficiency"]["labor_cost_pct"], NCPA_BENCHMARKS["labor_cost_pct"], False),
            ("inventory_turns", kpis["operational_efficiency"]["inventory_turns_annualized"], NCPA_BENCHMARKS["inventory_turns"], True),
            ("dso_days", kpis["cash_flow"]["dso_days"], NCPA_BENCHMARKS["dso_days"], False),
            ("underwater_rate", kpis["reimbursement_health"]["underwater_rate"], NCPA_BENCHMARKS["underwater_rate"], False),
            ("dir_fee_pct", kpis["profitability"]["dir_fee_pct"], NCPA_BENCHMARKS["dir_fees_pct"], False),
        ]

        for name, actual, benchmark, higher_is_better in metrics:
            if benchmark == 0:
                continue
            diff_pct = round(((actual - benchmark) / benchmark) * 100, 1)
            if higher_is_better:
                status = "above" if actual >= benchmark else "below"
            else:
                status = "below" if actual <= benchmark else "above"

            is_good = (
                (status == "above" and higher_is_better) or
                (status == "below" and not higher_is_better)
            )

            comparisons[name] = {
                "actual": actual,
                "benchmark": benchmark,
                "difference_pct": diff_pct,
                "status": status,
                "favorable": is_good,
            }

        favorable = sum(1 for c in comparisons.values() if c["favorable"])
        return {
            "metrics": comparisons,
            "favorable_count": favorable,
            "total_metrics": len(comparisons),
            "benchmark_score": round(favorable / len(comparisons) * 100, 1) if comparisons else 0,
        }

    # -------------------------------------------------------
    # Financial Health Score
    # -------------------------------------------------------

    def _compute_health_score(self, kpis: Dict) -> Dict[str, Any]:
        """Compute composite financial health score (0-100)."""
        score = 50  # baseline

        # Profitability
        gm = kpis["profitability"]["gross_margin_pct"]
        if gm >= 25:
            score += 15
        elif gm >= 20:
            score += 8
        elif gm < 18:
            score -= 10

        nm = kpis["profitability"]["net_margin_pct"]
        if nm >= 5:
            score += 10
        elif nm >= 2:
            score += 5
        elif nm < 0:
            score -= 15

        # Operational
        spd = kpis["operational_efficiency"]["scripts_per_day"]
        if spd >= 200:
            score += 8
        elif spd >= 150:
            score += 4
        elif spd < 100:
            score -= 5

        gr = kpis["operational_efficiency"]["generic_fill_rate"]
        if gr >= 90:
            score += 5
        elif gr < 80:
            score -= 5

        # Cash flow
        ccc = kpis["cash_flow"]["cash_conversion_cycle"]
        if ccc <= 20:
            score += 8
        elif ccc <= 35:
            score += 3
        elif ccc > 50:
            score -= 8

        # Underwater
        uw = kpis["reimbursement_health"]["underwater_rate"]
        if uw <= 5:
            score += 8
        elif uw <= 10:
            score += 3
        elif uw > 15:
            score -= 10

        # DIR fee impact
        dir_pct = kpis["profitability"]["dir_fee_pct"]
        if dir_pct > 3:
            score -= 8
        elif dir_pct > 2:
            score -= 4

        score = round(max(0, min(100, score)), 1)

        if score >= 80:
            grade, status = "A", "Strong"
        elif score >= 65:
            grade, status = "B", "Good"
        elif score >= 50:
            grade, status = "C", "Fair"
        elif score >= 35:
            grade, status = "D", "Weak"
        else:
            grade, status = "F", "Critical"

        return {
            "score": score,
            "grade": grade,
            "status": status,
        }

    # -------------------------------------------------------
    # Trending
    # -------------------------------------------------------

    def get_kpi_trends(self) -> Dict[str, Any]:
        """Calculate KPI trends across all loaded periods."""
        if len(self.periods) < 2:
            return {"message": "Need at least 2 periods for trending"}

        trend_data = []
        for period in sorted(self.periods, key=lambda p: p.period):
            kpis = self.calculate_kpis(period.period)
            trend_data.append({
                "period": period.period,
                "gross_margin_pct": kpis["profitability"]["gross_margin_pct"],
                "net_margin_pct": kpis["profitability"]["net_margin_pct"],
                "scripts_per_day": kpis["operational_efficiency"]["scripts_per_day"],
                "underwater_rate": kpis["reimbursement_health"]["underwater_rate"],
                "health_score": kpis["financial_health"]["score"],
            })

        # Direction detection
        if len(trend_data) >= 2:
            first = trend_data[0]
            last = trend_data[-1]
            trends = {}
            for key in ["gross_margin_pct", "net_margin_pct", "scripts_per_day", "health_score"]:
                diff = last[key] - first[key]
                trends[key] = "improving" if diff > 0 else ("declining" if diff < 0 else "stable")
            uw_diff = last["underwater_rate"] - first["underwater_rate"]
            trends["underwater_rate"] = "improving" if uw_diff < 0 else ("worsening" if uw_diff > 0 else "stable")
        else:
            trends = {}

        return {
            "periods_analyzed": len(trend_data),
            "data": trend_data,
            "trends": trends,
        }


# ============================================================
# Module-level convenience
# ============================================================

def calculate_pharmacy_kpis(periods_data: List[Dict], period: Optional[str] = None) -> Dict[str, Any]:
    """Quick KPI calculation from period data."""
    engine = PharmacyFinancialKPIEngine()
    engine.load_periods(periods_data)
    return engine.calculate_kpis(period)
