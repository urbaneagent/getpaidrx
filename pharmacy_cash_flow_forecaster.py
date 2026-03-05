"""
Pharmacy Cash Flow Forecasting Engine
========================================
Predicts pharmacy cash position based on claim payment cycles,
DIR fee timing, inventory costs, and seasonal patterns to optimize
working capital and identify cash crunches before they happen.

Features:
- Daily/weekly/monthly cash flow projection
- Claim payment cycle modeling by payer
- DIR fee timing and impact forecasting
- Inventory cost projection with supplier terms
- Seasonal adjustment (flu season, open enrollment)
- Cash reserve adequacy scoring
- What-if scenario modeling
- Working capital optimization recommendations

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import math
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentCycleType(Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    NET_90 = "net_90"


class CashFlowCategory(Enum):
    CLAIM_REVENUE = "claim_revenue"
    CASH_SALES = "cash_sales"
    DIR_FEE = "dir_fee"
    INVENTORY_COST = "inventory_cost"
    PAYROLL = "payroll"
    RENT = "rent"
    UTILITIES = "utilities"
    INSURANCE = "insurance"
    LOAN_PAYMENT = "loan_payment"
    EQUIPMENT = "equipment"
    MARKETING = "marketing"
    OTHER_INCOME = "other_income"
    OTHER_EXPENSE = "other_expense"


@dataclass
class PayerPaymentProfile:
    """Payment cycle characteristics for a specific payer."""
    payer_id: str
    payer_name: str
    payment_cycle: PaymentCycleType
    avg_days_to_payment: float
    payment_reliability: float          # 0-1, how consistent they pay on time
    avg_daily_claims: float             # Average daily claim volume
    avg_claim_value: float              # Average reimbursement per claim
    dir_fee_pct: float = 0.0            # DIR fee as % of reimbursement
    dir_fee_frequency: str = "quarterly"  # quarterly, monthly, annually
    next_dir_fee_date: Optional[str] = None
    rejection_rate: float = 0.02        # Average rejection rate
    clawback_rate: float = 0.01         # Historical clawback rate


@dataclass
class RecurringExpense:
    """A recurring fixed or semi-fixed expense."""
    expense_id: str
    name: str
    category: CashFlowCategory
    amount: float
    frequency: str                       # weekly, biweekly, monthly, quarterly, annual
    day_of_month: int = 1               # For monthly expenses
    next_due_date: str = ""
    is_variable: bool = False
    variance_pct: float = 0.0           # Expected variance (e.g., utilities ±15%)


@dataclass
class InventoryForecast:
    """Inventory cost projection parameters."""
    avg_daily_cogs: float               # Average daily cost of goods sold
    supplier_terms_days: int = 30       # Net terms with primary supplier
    secondary_supplier_terms: int = 14  # Secondary supplier terms
    primary_supplier_pct: float = 0.75  # % of inventory from primary
    seasonal_multipliers: Dict[int, float] = field(default_factory=lambda: {
        1: 1.15, 2: 1.05, 3: 0.95, 4: 0.90, 5: 0.85, 6: 0.85,
        7: 0.85, 8: 0.90, 9: 1.00, 10: 1.10, 11: 1.20, 12: 1.25
    })
    buffer_stock_days: int = 3          # Safety stock in days


@dataclass 
class CashFlowProjection:
    """A single day's cash flow projection."""
    projection_date: str
    opening_balance: float
    inflows: Dict[str, float]
    outflows: Dict[str, float]
    net_flow: float
    closing_balance: float
    confidence: float                    # 0-1 confidence in this projection
    warnings: List[str] = field(default_factory=list)
    is_negative: bool = False


class SeasonalAdjuster:
    """Adjusts projections for seasonal pharmacy patterns."""

    # Revenue multipliers by month (1=January)
    REVENUE_SEASONALITY = {
        1: 1.15,   # Flu season + new insurance year
        2: 1.05,   # Continued flu season
        3: 0.95,
        4: 0.90,
        5: 0.88,
        6: 0.85,   # Summer dip
        7: 0.85,
        8: 0.90,   # Back to school
        9: 1.00,   # Allergy season
        10: 1.05,  # Open enrollment begins
        11: 1.15,  # Holiday + flu season start
        12: 1.20,  # Peak holiday + year-end prescriptions
    }

    # Prescription fill patterns by day of week (0=Monday)
    DAY_OF_WEEK_FACTORS = {
        0: 1.15,   # Monday - high volume
        1: 1.10,
        2: 1.05,
        3: 1.00,
        4: 1.10,   # Friday - before weekend
        5: 0.70,   # Saturday - reduced hours
        6: 0.40,   # Sunday - minimal
    }

    @classmethod
    def adjust_revenue(cls, base_amount: float, target_date: date) -> float:
        month_factor = cls.REVENUE_SEASONALITY.get(target_date.month, 1.0)
        dow_factor = cls.DAY_OF_WEEK_FACTORS.get(target_date.weekday(), 1.0)
        return base_amount * month_factor * dow_factor

    @classmethod
    def get_monthly_factor(cls, month: int) -> float:
        return cls.REVENUE_SEASONALITY.get(month, 1.0)


class ClaimRevenueProjector:
    """Projects claim revenue based on payer profiles and payment cycles."""

    def __init__(self, payer_profiles: List[PayerPaymentProfile]):
        self.payers = {p.payer_id: p for p in payer_profiles}
        self.adjuster = SeasonalAdjuster()

    def project_daily_revenue(self, target_date: date) -> Dict:
        """Project expected claim revenue for a specific date."""
        total_expected = 0.0
        payer_breakdown = {}

        for payer_id, payer in self.payers.items():
            # Calculate base daily revenue
            base_daily = payer.avg_daily_claims * payer.avg_claim_value
            
            # Apply rejection deduction
            net_daily = base_daily * (1 - payer.rejection_rate)
            
            # Apply seasonal adjustment
            adjusted = self.adjuster.adjust_revenue(net_daily, target_date)

            # Apply payment cycle delay
            # Revenue earned today arrives X days later based on payment cycle
            payment_days = payer.avg_days_to_payment
            earn_date = target_date - timedelta(days=int(payment_days))

            # Confidence degrades with time horizon
            days_out = (target_date - date.today()).days
            confidence = max(0.3, payer.payment_reliability * (1 - days_out * 0.005))

            payer_breakdown[payer_id] = {
                "payer_name": payer.payer_name,
                "expected_amount": round(adjusted, 2),
                "payment_cycle": payer.payment_cycle.value,
                "confidence": round(confidence, 2),
                "claims_earned_date": earn_date.isoformat()
            }

            total_expected += adjusted

        return {
            "date": target_date.isoformat(),
            "total_expected_revenue": round(total_expected, 2),
            "payer_breakdown": payer_breakdown
        }

    def project_dir_fees(self, start_date: date, days: int) -> List[Dict]:
        """Project DIR fee deductions over a time period."""
        dir_events = []

        for payer in self.payers.values():
            if payer.dir_fee_pct <= 0:
                continue

            # Calculate quarterly DIR fee amount
            quarterly_revenue = payer.avg_daily_claims * payer.avg_claim_value * 90
            dir_amount = quarterly_revenue * (payer.dir_fee_pct / 100)

            # Check if DIR fee falls within projection window
            if payer.next_dir_fee_date:
                dir_date = date.fromisoformat(payer.next_dir_fee_date)
                if start_date <= dir_date <= start_date + timedelta(days=days):
                    dir_events.append({
                        "payer_id": payer.payer_id,
                        "payer_name": payer.payer_name,
                        "date": dir_date.isoformat(),
                        "amount": round(dir_amount, 2),
                        "type": "dir_fee",
                        "frequency": payer.dir_fee_frequency
                    })

        return dir_events


class ExpenseProjector:
    """Projects recurring and variable expenses."""

    def __init__(self, expenses: List[RecurringExpense], inventory: InventoryForecast):
        self.expenses = expenses
        self.inventory = inventory

    def project_daily_expenses(self, target_date: date) -> Dict:
        """Project all expenses for a specific date."""
        expense_items = {}
        total = 0.0

        # Check recurring expenses
        for expense in self.expenses:
            amount = self._check_expense_due(expense, target_date)
            if amount > 0:
                expense_items[expense.expense_id] = {
                    "name": expense.name,
                    "category": expense.category.value,
                    "amount": round(amount, 2)
                }
                total += amount

        # Add inventory costs
        inventory_cost = self._project_inventory_cost(target_date)
        if inventory_cost > 0:
            expense_items["inventory"] = {
                "name": "Inventory / COGS",
                "category": CashFlowCategory.INVENTORY_COST.value,
                "amount": round(inventory_cost, 2)
            }
            total += inventory_cost

        return {
            "date": target_date.isoformat(),
            "total_expenses": round(total, 2),
            "items": expense_items
        }

    def _check_expense_due(self, expense: RecurringExpense, target_date: date) -> float:
        amount = expense.amount
        if expense.is_variable:
            # Add variance for variable expenses
            import random
            variance = amount * expense.variance_pct / 100
            amount += random.uniform(-variance, variance)

        if expense.frequency == "daily":
            return amount
        elif expense.frequency == "weekly":
            if target_date.weekday() == 0:  # Monday
                return amount
        elif expense.frequency == "biweekly":
            week_num = target_date.isocalendar()[1]
            if week_num % 2 == 0 and target_date.weekday() == 4:  # Every other Friday
                return amount
        elif expense.frequency == "monthly":
            if target_date.day == expense.day_of_month:
                return amount
        elif expense.frequency == "quarterly":
            if target_date.month in (1, 4, 7, 10) and target_date.day == expense.day_of_month:
                return amount
        elif expense.frequency == "annual":
            if expense.next_due_date:
                due = date.fromisoformat(expense.next_due_date)
                if target_date.month == due.month and target_date.day == due.day:
                    return amount

        return 0.0

    def _project_inventory_cost(self, target_date: date) -> float:
        base_cost = self.inventory.avg_daily_cogs
        month = target_date.month
        seasonal = self.inventory.seasonal_multipliers.get(month, 1.0)
        
        # Weekend reduction
        if target_date.weekday() >= 5:
            seasonal *= 0.5

        return base_cost * seasonal


class CashReserveAnalyzer:
    """Analyzes cash reserve adequacy and provides recommendations."""

    RESERVE_TARGETS = {
        "minimum": 14,       # 14 days operating expenses
        "adequate": 30,      # 30 days
        "comfortable": 60,   # 60 days
        "excess": 90         # 90+ days may indicate underinvestment
    }

    def analyze(self, current_balance: float, avg_daily_expense: float,
                projections: List[CashFlowProjection]) -> Dict:
        """Analyze cash reserve adequacy."""
        days_of_reserves = current_balance / avg_daily_expense if avg_daily_expense > 0 else 999

        # Find minimum projected balance
        min_balance = min(p.closing_balance for p in projections) if projections else current_balance
        min_date = ""
        for p in projections:
            if p.closing_balance == min_balance:
                min_date = p.projection_date
                break

        # Count negative balance days
        negative_days = sum(1 for p in projections if p.is_negative)

        # Determine adequacy level
        if days_of_reserves >= 90:
            adequacy = "excess"
            score = 100
        elif days_of_reserves >= 60:
            adequacy = "comfortable"
            score = 90
        elif days_of_reserves >= 30:
            adequacy = "adequate"
            score = 75
        elif days_of_reserves >= 14:
            adequacy = "minimum"
            score = 50
        else:
            adequacy = "critical"
            score = max(0, int(days_of_reserves / 14 * 50))

        recommendations = self._generate_recommendations(
            days_of_reserves, negative_days, min_balance, avg_daily_expense
        )

        return {
            "current_balance": round(current_balance, 2),
            "avg_daily_expense": round(avg_daily_expense, 2),
            "days_of_reserves": round(days_of_reserves, 1),
            "adequacy_level": adequacy,
            "reserve_score": score,
            "minimum_projected_balance": round(min_balance, 2),
            "minimum_balance_date": min_date,
            "negative_balance_days": negative_days,
            "recommendations": recommendations,
            "analyzed_at": datetime.utcnow().isoformat()
        }

    def _generate_recommendations(self, days_reserves: float, negative_days: int,
                                   min_balance: float, avg_daily_expense: float) -> List[Dict]:
        recs = []

        if negative_days > 0:
            recs.append({
                "priority": "critical",
                "action": "Arrange line of credit or emergency funding",
                "detail": f"{negative_days} day(s) with projected negative balance. "
                          f"Minimum projected: ${min_balance:,.2f}",
                "impact": "Prevent overdraft fees and supplier payment failures"
            })

        if days_reserves < 14:
            recs.append({
                "priority": "high",
                "action": "Build cash reserves to 14+ days",
                "detail": f"Current reserves cover only {days_reserves:.1f} days. "
                          f"Target minimum: ${avg_daily_expense * 14:,.2f}",
                "impact": "Buffer against payment delays and unexpected costs"
            })

        if days_reserves < 30:
            recs.append({
                "priority": "medium",
                "action": "Negotiate extended payment terms with suppliers",
                "detail": "Moving from Net-30 to Net-45 or Net-60 improves cash position",
                "impact": f"Could free up ${avg_daily_expense * 15:,.2f} in working capital"
            })

        if days_reserves > 90:
            recs.append({
                "priority": "low",
                "action": "Consider investing excess cash",
                "detail": f"Reserves exceed 90 days ({days_reserves:.0f} days). "
                          "Consider high-yield savings or short-term instruments.",
                "impact": "Earn interest on idle cash"
            })

        recs.append({
            "priority": "medium",
            "action": "Accelerate claim follow-up on aged receivables",
            "detail": "Reducing average days-to-payment by 5 days improves cash position",
            "impact": f"Could accelerate ${avg_daily_expense * 5:,.2f} in receivables"
        })

        return recs


class ScenarioModeler:
    """What-if scenario modeling for cash flow projections."""

    def __init__(self, base_projections: List[CashFlowProjection]):
        self.base = base_projections

    def model_scenario(self, scenario_name: str, adjustments: Dict) -> List[CashFlowProjection]:
        """
        Apply adjustments to base projections.
        
        adjustments keys:
        - revenue_change_pct: +/- % change in revenue
        - expense_change_pct: +/- % change in expenses
        - payment_delay_days: Additional days delay in payments
        - one_time_expense: {date: amount}
        - one_time_income: {date: amount}
        """
        adjusted = []
        balance = self.base[0].opening_balance if self.base else 0

        rev_factor = 1 + (adjustments.get("revenue_change_pct", 0) / 100)
        exp_factor = 1 + (adjustments.get("expense_change_pct", 0) / 100)
        one_time_exp = adjustments.get("one_time_expense", {})
        one_time_inc = adjustments.get("one_time_income", {})

        for proj in self.base:
            inflows = {k: v * rev_factor for k, v in proj.inflows.items()}
            outflows = {k: v * exp_factor for k, v in proj.outflows.items()}

            # Add one-time items
            if proj.projection_date in one_time_exp:
                outflows["one_time"] = one_time_exp[proj.projection_date]
            if proj.projection_date in one_time_inc:
                inflows["one_time"] = one_time_inc[proj.projection_date]

            total_in = sum(inflows.values())
            total_out = sum(outflows.values())
            net = total_in - total_out
            closing = balance + net

            adjusted.append(CashFlowProjection(
                projection_date=proj.projection_date,
                opening_balance=round(balance, 2),
                inflows=inflows,
                outflows=outflows,
                net_flow=round(net, 2),
                closing_balance=round(closing, 2),
                confidence=proj.confidence * 0.8,  # Lower confidence for scenarios
                warnings=[f"Scenario: {scenario_name}"],
                is_negative=closing < 0
            ))

            balance = closing

        return adjusted


class PharmacyCashFlowForecaster:
    """
    Main cash flow forecasting engine for pharmacy operations.
    
    Usage:
        forecaster = PharmacyCashFlowForecaster(
            current_balance=150000,
            payer_profiles=[...],
            expenses=[...],
            inventory_forecast=InventoryForecast(...)
        )
        
        projection = forecaster.forecast(days=90)
        analysis = forecaster.analyze_reserves()
    """

    def __init__(self, current_balance: float,
                 payer_profiles: List[PayerPaymentProfile],
                 expenses: List[RecurringExpense],
                 inventory_forecast: InventoryForecast):
        self.current_balance = current_balance
        self.revenue_projector = ClaimRevenueProjector(payer_profiles)
        self.expense_projector = ExpenseProjector(expenses, inventory_forecast)
        self.reserve_analyzer = CashReserveAnalyzer()

    def forecast(self, days: int = 90, start_date: Optional[date] = None) -> Dict:
        """Generate cash flow forecast for the specified period."""
        start = start_date or date.today()
        projections = []
        balance = self.current_balance
        total_inflows = 0.0
        total_outflows = 0.0

        for day_offset in range(days):
            target_date = start + timedelta(days=day_offset)

            # Project revenue
            revenue = self.revenue_projector.project_daily_revenue(target_date)
            inflows = {"claim_revenue": revenue["total_expected_revenue"]}

            # Weekend cash sales
            if target_date.weekday() < 5:
                inflows["cash_sales"] = 850.0  # Average daily OTC/cash sales
            else:
                inflows["cash_sales"] = 400.0

            # Project expenses
            expenses = self.expense_projector.project_daily_expenses(target_date)
            outflows = {}
            for item_id, item in expenses["items"].items():
                outflows[item["name"]] = item["amount"]

            total_in = sum(inflows.values())
            total_out = sum(outflows.values())
            net = total_in - total_out
            closing = balance + net

            total_inflows += total_in
            total_outflows += total_out

            # Confidence decreases with time
            confidence = max(0.3, 1.0 - (day_offset * 0.008))

            warnings = []
            if closing < 0:
                warnings.append(f"NEGATIVE BALANCE: ${closing:,.2f}")
            elif closing < self.current_balance * 0.2:
                warnings.append(f"LOW BALANCE: ${closing:,.2f} (below 20% of current)")

            projections.append(CashFlowProjection(
                projection_date=target_date.isoformat(),
                opening_balance=round(balance, 2),
                inflows=inflows,
                outflows=outflows,
                net_flow=round(net, 2),
                closing_balance=round(closing, 2),
                confidence=round(confidence, 2),
                warnings=warnings,
                is_negative=closing < 0
            ))

            balance = closing

        # DIR fee events
        dir_fees = self.revenue_projector.project_dir_fees(start, days)

        # Summary statistics
        balances = [p.closing_balance for p in projections]

        return {
            "forecast_period": {
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(days=days - 1)).isoformat(),
                "days": days
            },
            "summary": {
                "opening_balance": round(self.current_balance, 2),
                "projected_closing": round(balance, 2),
                "total_inflows": round(total_inflows, 2),
                "total_outflows": round(total_outflows, 2),
                "net_change": round(total_inflows - total_outflows, 2),
                "min_balance": round(min(balances), 2),
                "max_balance": round(max(balances), 2),
                "avg_balance": round(sum(balances) / len(balances), 2),
                "negative_days": sum(1 for p in projections if p.is_negative),
                "warning_days": sum(1 for p in projections if p.warnings)
            },
            "dir_fee_events": dir_fees,
            "daily_projections": [
                {
                    "date": p.projection_date,
                    "opening": p.opening_balance,
                    "inflows": p.inflows,
                    "outflows": p.outflows,
                    "net": p.net_flow,
                    "closing": p.closing_balance,
                    "confidence": p.confidence,
                    "warnings": p.warnings
                }
                for p in projections
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

    def analyze_reserves(self, days: int = 90) -> Dict:
        """Analyze cash reserve adequacy based on forecast."""
        forecast = self.forecast(days)
        avg_daily_expense = forecast["summary"]["total_outflows"] / days

        projections = []
        balance = self.current_balance
        start = date.today()

        for i in range(days):
            target = start + timedelta(days=i)
            rev = self.revenue_projector.project_daily_revenue(target)
            exp = self.expense_projector.project_daily_expenses(target)
            net = rev["total_expected_revenue"] - exp["total_expenses"]
            balance += net
            projections.append(CashFlowProjection(
                projection_date=target.isoformat(),
                opening_balance=balance - net,
                inflows={},
                outflows={},
                net_flow=net,
                closing_balance=balance,
                confidence=0.8,
                is_negative=balance < 0
            ))

        return self.reserve_analyzer.analyze(self.current_balance, avg_daily_expense, projections)

    def run_scenario(self, scenario_name: str, adjustments: Dict, days: int = 90) -> Dict:
        """Run a what-if scenario on the forecast."""
        base_forecast = self.forecast(days)

        base_projections = []
        balance = self.current_balance
        start = date.today()

        for i in range(days):
            target = start + timedelta(days=i)
            rev = self.revenue_projector.project_daily_revenue(target)
            exp = self.expense_projector.project_daily_expenses(target)
            net = rev["total_expected_revenue"] - exp["total_expenses"]

            base_projections.append(CashFlowProjection(
                projection_date=target.isoformat(),
                opening_balance=balance,
                inflows={"revenue": rev["total_expected_revenue"]},
                outflows={"expenses": exp["total_expenses"]},
                net_flow=net,
                closing_balance=balance + net,
                confidence=0.8,
                is_negative=(balance + net) < 0
            ))
            balance += net

        modeler = ScenarioModeler(base_projections)
        scenario = modeler.model_scenario(scenario_name, adjustments)

        scenario_balances = [p.closing_balance for p in scenario]

        return {
            "scenario_name": scenario_name,
            "adjustments": adjustments,
            "base_closing": round(base_projections[-1].closing_balance, 2),
            "scenario_closing": round(scenario[-1].closing_balance, 2),
            "difference": round(
                scenario[-1].closing_balance - base_projections[-1].closing_balance, 2
            ),
            "scenario_min_balance": round(min(scenario_balances), 2),
            "scenario_negative_days": sum(1 for p in scenario if p.is_negative),
            "daily_comparison": [
                {
                    "date": scenario[i].projection_date,
                    "base_balance": round(base_projections[i].closing_balance, 2),
                    "scenario_balance": round(scenario[i].closing_balance, 2)
                }
                for i in range(0, len(scenario), 7)  # Weekly snapshots
            ],
            "generated_at": datetime.utcnow().isoformat()
        }


# FastAPI Integration
try:
    from fastapi import APIRouter, Query
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/v1/cashflow", tags=["Cash Flow"])

    class ForecastRequest(BaseModel):
        current_balance: float
        days: int = 90

    class ScenarioRequest(BaseModel):
        scenario_name: str
        current_balance: float
        adjustments: Dict
        days: int = 90

    @router.post("/forecast")
    async def create_forecast(req: ForecastRequest):
        # Create with sample data for demo
        payers = [
            PayerPaymentProfile("CVS", "CVS Caremark", PaymentCycleType.BIWEEKLY,
                                14, 0.95, 85, 125.50, 3.5, "quarterly", "2026-04-01"),
            PayerPaymentProfile("ESI", "Express Scripts", PaymentCycleType.WEEKLY,
                                7, 0.92, 65, 142.00, 4.2, "quarterly", "2026-04-15"),
            PayerPaymentProfile("OPTUM", "OptumRx", PaymentCycleType.BIWEEKLY,
                                14, 0.90, 55, 135.75, 3.8, "quarterly", "2026-04-01"),
        ]
        expenses = [
            RecurringExpense("PAYROLL", "Payroll", CashFlowCategory.PAYROLL, 28000, "biweekly"),
            RecurringExpense("RENT", "Rent", CashFlowCategory.RENT, 8500, "monthly", 1),
            RecurringExpense("UTIL", "Utilities", CashFlowCategory.UTILITIES, 2200, "monthly", 15, is_variable=True, variance_pct=15),
            RecurringExpense("INS", "Insurance", CashFlowCategory.INSURANCE, 3500, "monthly", 1),
        ]
        inventory = InventoryForecast(avg_daily_cogs=8500)

        forecaster = PharmacyCashFlowForecaster(req.current_balance, payers, expenses, inventory)
        return forecaster.forecast(req.days)

    @router.post("/scenario")
    async def run_scenario(req: ScenarioRequest):
        payers = [
            PayerPaymentProfile("CVS", "CVS Caremark", PaymentCycleType.BIWEEKLY,
                                14, 0.95, 85, 125.50, 3.5),
        ]
        expenses = [
            RecurringExpense("PAYROLL", "Payroll", CashFlowCategory.PAYROLL, 28000, "biweekly"),
        ]
        inventory = InventoryForecast(avg_daily_cogs=8500)

        forecaster = PharmacyCashFlowForecaster(req.current_balance, payers, expenses, inventory)
        return forecaster.run_scenario(req.scenario_name, req.adjustments, req.days)

except ImportError:
    router = None
