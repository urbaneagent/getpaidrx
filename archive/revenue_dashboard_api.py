"""
GetPaidRx - Pharmacy Revenue Dashboard API

Unified FastAPI router providing dashboard endpoints for revenue tracking,
payer performance, underpayment alerts, and financial KPIs. Powers the
pharmacy owner dashboard with real-time analytics.

Endpoints:
  /api/v1/dashboard/overview        - High-level KPI overview
  /api/v1/dashboard/revenue         - Revenue breakdown by period
  /api/v1/dashboard/payers          - Payer performance summary
  /api/v1/dashboard/underpayments   - Active underpayment alerts
  /api/v1/dashboard/trends          - Revenue trend data for charts
  /api/v1/dashboard/kpi-cards       - Individual KPI card data
"""

import json
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass

try:
    from fastapi import APIRouter, Query, HTTPException
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ============================================================
# Revenue Data Models
# ============================================================

@dataclass
class RevenuePeriod:
    """Revenue data for a time period."""
    period: str              # YYYY-MM or YYYY-WW
    total_revenue: float
    total_cost: float
    gross_margin: float
    claim_count: int
    avg_revenue_per_claim: float
    avg_margin_per_claim: float
    underwater_count: int
    underwater_amount: float


class PharmacyRevenueDashboard:
    """
    In-memory analytics engine for pharmacy revenue dashboard.
    Processes claim data into dashboard-ready KPIs and visualizations.
    """

    def __init__(self):
        self.claims = []

    def load_claims(self, claims_data: List[Dict[str, Any]]) -> int:
        """Load claim data for dashboard analysis."""
        loaded = 0
        for c in claims_data:
            try:
                self.claims.append({
                    "claim_id": str(c.get("claim_id", "")),
                    "fill_date": str(c.get("fill_date", "")),
                    "drug_name": str(c.get("drug_name", "")),
                    "ndc": str(c.get("ndc", "")),
                    "payer": str(c.get("payer", "")),
                    "pbm": str(c.get("pbm", "")),
                    "plan_type": str(c.get("plan_type", "")),
                    "quantity": float(c.get("quantity", 0)),
                    "days_supply": int(c.get("days_supply", 0)),
                    "reimbursement": float(c.get("reimbursement", 0)),
                    "copay": float(c.get("copay", 0)),
                    "cost": float(c.get("cost", 0)),
                    "dispensing_fee": float(c.get("dispensing_fee", 0)),
                    "status": str(c.get("status", "paid")),
                    "therapeutic_class": str(c.get("therapeutic_class", "")),
                    "drug_type": str(c.get("drug_type", "generic")),
                })
                loaded += 1
            except (ValueError, TypeError):
                continue
        return loaded

    # -------------------------------------------------------
    # Overview Dashboard
    # -------------------------------------------------------

    def get_overview(self, period_days: int = 30) -> Dict[str, Any]:
        """Generate high-level KPI overview."""
        cutoff = datetime.now() - timedelta(days=period_days)
        recent = self._filter_by_date(cutoff)
        prior_cutoff = cutoff - timedelta(days=period_days)
        prior = self._filter_by_date(prior_cutoff, cutoff)

        current_kpis = self._compute_kpis(recent)
        prior_kpis = self._compute_kpis(prior)

        # Compute deltas
        deltas = {}
        for key in current_kpis:
            if isinstance(current_kpis[key], (int, float)) and isinstance(prior_kpis.get(key), (int, float)):
                prior_val = prior_kpis[key]
                current_val = current_kpis[key]
                if prior_val != 0:
                    deltas[f"{key}_change_pct"] = round(
                        ((current_val - prior_val) / abs(prior_val)) * 100, 1
                    )
                else:
                    deltas[f"{key}_change_pct"] = 0

        return {
            "generated_at": datetime.now().isoformat(),
            "period_days": period_days,
            "current_period": current_kpis,
            "prior_period": prior_kpis,
            "deltas": deltas,
            "alerts": self._generate_alerts(current_kpis, prior_kpis),
        }

    def _compute_kpis(self, claims: List[Dict]) -> Dict[str, Any]:
        """Compute KPIs from claim set."""
        if not claims:
            return {
                "total_revenue": 0, "total_cost": 0, "gross_margin": 0,
                "margin_percent": 0, "claim_count": 0, "avg_revenue_per_rx": 0,
                "avg_margin_per_rx": 0, "underwater_count": 0, "underwater_rate": 0,
                "underwater_amount": 0, "scripts_per_day": 0,
            }

        paid = [c for c in claims if c["status"] == "paid"]
        total_revenue = sum(c["reimbursement"] + c["copay"] for c in paid)
        total_cost = sum(c["cost"] for c in paid)
        gross_margin = total_revenue - total_cost

        underwater = [c for c in paid if (c["reimbursement"] + c["copay"]) < c["cost"]]
        underwater_amount = sum(
            c["cost"] - (c["reimbursement"] + c["copay"]) for c in underwater
        )

        # Calculate daily scripts
        dates = set()
        for c in paid:
            if c.get("fill_date"):
                dates.add(c["fill_date"][:10])
        active_days = max(1, len(dates))

        return {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "gross_margin": round(gross_margin, 2),
            "margin_percent": round((gross_margin / total_revenue * 100) if total_revenue > 0 else 0, 1),
            "claim_count": len(paid),
            "avg_revenue_per_rx": round(total_revenue / len(paid), 2) if paid else 0,
            "avg_margin_per_rx": round(gross_margin / len(paid), 2) if paid else 0,
            "underwater_count": len(underwater),
            "underwater_rate": round(len(underwater) / len(paid) * 100, 1) if paid else 0,
            "underwater_amount": round(underwater_amount, 2),
            "scripts_per_day": round(len(paid) / active_days, 1),
        }

    # -------------------------------------------------------
    # Revenue Breakdown
    # -------------------------------------------------------

    def get_revenue_breakdown(self, group_by: str = "payer") -> Dict[str, Any]:
        """Break down revenue by dimension (payer, drug_type, plan_type, therapeutic_class)."""
        groups = defaultdict(list)
        for c in self.claims:
            if c["status"] == "paid":
                key = c.get(group_by, "Unknown")
                groups[key].append(c)

        breakdown = []
        for group_name, claims in sorted(groups.items()):
            revenue = sum(c["reimbursement"] + c["copay"] for c in claims)
            cost = sum(c["cost"] for c in claims)
            margin = revenue - cost
            underwater = sum(1 for c in claims if (c["reimbursement"] + c["copay"]) < c["cost"])

            breakdown.append({
                "group": group_name,
                "claim_count": len(claims),
                "revenue": round(revenue, 2),
                "cost": round(cost, 2),
                "margin": round(margin, 2),
                "margin_percent": round((margin / revenue * 100) if revenue > 0 else 0, 1),
                "underwater_count": underwater,
                "avg_per_rx": round(revenue / len(claims), 2) if claims else 0,
            })

        breakdown.sort(key=lambda x: x["revenue"], reverse=True)

        return {
            "group_by": group_by,
            "groups": breakdown,
            "total_groups": len(breakdown),
        }

    # -------------------------------------------------------
    # Payer Performance Summary
    # -------------------------------------------------------

    def get_payer_summary(self) -> Dict[str, Any]:
        """Get payer performance summary for dashboard."""
        payer_groups = defaultdict(list)
        for c in self.claims:
            if c["status"] == "paid":
                payer_groups[c["payer"]].append(c)

        payers = []
        for payer, claims in sorted(payer_groups.items()):
            revenue = sum(c["reimbursement"] + c["copay"] for c in claims)
            cost = sum(c["cost"] for c in claims)
            margin = revenue - cost
            underwater = sum(1 for c in claims if (c["reimbursement"] + c["copay"]) < c["cost"])

            health = "good" if margin > 0 and len(underwater) / len(claims) < 0.1 else (
                "warning" if len(underwater) / len(claims) < 0.2 else "critical"
            ) if claims else "unknown"

            payers.append({
                "payer": payer,
                "claim_count": len(claims),
                "revenue": round(revenue, 2),
                "margin": round(margin, 2),
                "margin_percent": round((margin / revenue * 100) if revenue > 0 else 0, 1),
                "underwater_count": underwater,
                "underwater_rate": round(len(underwater) / len(claims) * 100 if claims else 0, 1),
                "health": health,
            })

        payers.sort(key=lambda x: x["margin"])  # Worst margin first

        return {"payers": payers, "total_payers": len(payers)}

    # -------------------------------------------------------
    # Underpayment Alerts
    # -------------------------------------------------------

    def get_underpayment_alerts(self, min_gap: float = 5.0) -> Dict[str, Any]:
        """Get active underpayment alerts."""
        alerts = []
        for c in self.claims:
            if c["status"] != "paid":
                continue
            total_received = c["reimbursement"] + c["copay"]
            gap = c["cost"] - total_received
            if gap >= min_gap:
                alerts.append({
                    "claim_id": c["claim_id"],
                    "drug_name": c["drug_name"],
                    "payer": c["payer"],
                    "fill_date": c["fill_date"],
                    "cost": round(c["cost"], 2),
                    "received": round(total_received, 2),
                    "gap": round(gap, 2),
                    "gap_percent": round((gap / c["cost"] * 100) if c["cost"] > 0 else 0, 1),
                })

        alerts.sort(key=lambda x: x["gap"], reverse=True)

        return {
            "total_alerts": len(alerts),
            "total_gap_amount": round(sum(a["gap"] for a in alerts), 2),
            "alerts": alerts[:50],  # Top 50
        }

    # -------------------------------------------------------
    # Trend Data
    # -------------------------------------------------------

    def get_trends(self, granularity: str = "monthly") -> Dict[str, Any]:
        """Get revenue trend data for charts."""
        paid = [c for c in self.claims if c["status"] == "paid"]
        period_data = defaultdict(list)

        for c in paid:
            if not c.get("fill_date"):
                continue
            if granularity == "weekly":
                try:
                    dt = datetime.strptime(c["fill_date"][:10], "%Y-%m-%d")
                    key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                except ValueError:
                    continue
            else:  # monthly
                key = c["fill_date"][:7]
            period_data[key].append(c)

        trends = []
        for period in sorted(period_data.keys()):
            claims = period_data[period]
            revenue = sum(c["reimbursement"] + c["copay"] for c in claims)
            cost = sum(c["cost"] for c in claims)
            margin = revenue - cost
            underwater = sum(1 for c in claims if (c["reimbursement"] + c["copay"]) < c["cost"])

            trends.append({
                "period": period,
                "revenue": round(revenue, 2),
                "cost": round(cost, 2),
                "margin": round(margin, 2),
                "margin_percent": round((margin / revenue * 100) if revenue > 0 else 0, 1),
                "claim_count": len(claims),
                "underwater_count": underwater,
            })

        return {
            "granularity": granularity,
            "periods": len(trends),
            "data": trends,
        }

    # -------------------------------------------------------
    # KPI Cards
    # -------------------------------------------------------

    def get_kpi_cards(self) -> List[Dict[str, Any]]:
        """Get individual KPI card data for dashboard widgets."""
        paid = [c for c in self.claims if c["status"] == "paid"]
        if not paid:
            return []

        total_revenue = sum(c["reimbursement"] + c["copay"] for c in paid)
        total_cost = sum(c["cost"] for c in paid)
        margin = total_revenue - total_cost
        underwater = [c for c in paid if (c["reimbursement"] + c["copay"]) < c["cost"]]
        denied = [c for c in self.claims if c["status"] == "denied"]

        unique_payers = len(set(c["payer"] for c in paid))
        unique_drugs = len(set(c["drug_name"] for c in paid))

        # Payer with worst margin
        payer_margins = defaultdict(lambda: {"revenue": 0, "cost": 0})
        for c in paid:
            payer_margins[c["payer"]]["revenue"] += c["reimbursement"] + c["copay"]
            payer_margins[c["payer"]]["cost"] += c["cost"]
        worst_payer = min(
            payer_margins.items(),
            key=lambda x: (x[1]["revenue"] - x[1]["cost"]) / x[1]["cost"] if x[1]["cost"] > 0 else 0,
            default=("N/A", {"revenue": 0, "cost": 0}),
        )

        return [
            {
                "id": "total_revenue",
                "label": "Total Revenue",
                "value": f"${total_revenue:,.2f}",
                "raw_value": total_revenue,
                "icon": "💰",
                "color": "green",
            },
            {
                "id": "gross_margin",
                "label": "Gross Margin",
                "value": f"${margin:,.2f}",
                "raw_value": margin,
                "icon": "📊",
                "color": "green" if margin > 0 else "red",
            },
            {
                "id": "margin_percent",
                "label": "Margin %",
                "value": f"{(margin / total_revenue * 100) if total_revenue > 0 else 0:.1f}%",
                "raw_value": (margin / total_revenue * 100) if total_revenue > 0 else 0,
                "icon": "📈",
                "color": "green" if margin > 0 else "red",
            },
            {
                "id": "total_scripts",
                "label": "Total Rx",
                "value": f"{len(paid):,}",
                "raw_value": len(paid),
                "icon": "💊",
                "color": "blue",
            },
            {
                "id": "underwater_rate",
                "label": "Underwater Rate",
                "value": f"{len(underwater) / len(paid) * 100:.1f}%" if paid else "0%",
                "raw_value": len(underwater) / len(paid) * 100 if paid else 0,
                "icon": "⚠️",
                "color": "red" if len(underwater) / len(paid) > 0.1 else "yellow",
            },
            {
                "id": "underwater_amount",
                "label": "Underwater Losses",
                "value": f"${sum(c['cost'] - (c['reimbursement'] + c['copay']) for c in underwater):,.2f}",
                "raw_value": sum(c["cost"] - (c["reimbursement"] + c["copay"]) for c in underwater),
                "icon": "🔴",
                "color": "red",
            },
            {
                "id": "denial_count",
                "label": "Denied Claims",
                "value": f"{len(denied):,}",
                "raw_value": len(denied),
                "icon": "❌",
                "color": "red" if denied else "green",
            },
            {
                "id": "active_payers",
                "label": "Active Payers",
                "value": str(unique_payers),
                "raw_value": unique_payers,
                "icon": "🏢",
                "color": "blue",
            },
            {
                "id": "unique_drugs",
                "label": "Unique Drugs",
                "value": str(unique_drugs),
                "raw_value": unique_drugs,
                "icon": "🧪",
                "color": "blue",
            },
            {
                "id": "worst_payer",
                "label": "Worst Payer",
                "value": worst_payer[0],
                "raw_value": 0,
                "icon": "⚠️",
                "color": "red",
            },
        ]

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------

    def _filter_by_date(
        self, start: datetime, end: Optional[datetime] = None
    ) -> List[Dict]:
        """Filter claims by date range."""
        result = []
        end = end or datetime.now()
        for c in self.claims:
            if c.get("fill_date"):
                try:
                    dt = datetime.strptime(c["fill_date"][:10], "%Y-%m-%d")
                    if start <= dt <= end:
                        result.append(c)
                except ValueError:
                    continue
        return result

    def _generate_alerts(
        self, current: Dict[str, Any], prior: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate dashboard alerts from KPI comparison."""
        alerts = []

        if current.get("underwater_rate", 0) > 15:
            alerts.append({
                "type": "critical",
                "title": "High Underwater Rate",
                "message": f"{current['underwater_rate']}% of claims are below cost.",
            })

        if current.get("margin_percent", 0) < 3:
            alerts.append({
                "type": "warning",
                "title": "Low Margin",
                "message": f"Overall margin is only {current['margin_percent']}%.",
            })

        if prior.get("claim_count", 0) > 0:
            volume_change = (
                (current["claim_count"] - prior["claim_count"]) / prior["claim_count"] * 100
            )
            if volume_change < -15:
                alerts.append({
                    "type": "warning",
                    "title": "Volume Decline",
                    "message": f"Script volume down {abs(volume_change):.0f}% vs prior period.",
                })

        return alerts


# ============================================================
# FastAPI Router (conditional)
# ============================================================

if HAS_FASTAPI:
    router = APIRouter(prefix="/api/v1/dashboard", tags=["Revenue Dashboard"])
    _dashboard = PharmacyRevenueDashboard()

    @router.get("/overview")
    async def dashboard_overview(
        period_days: int = Query(30, ge=1, le=365, description="Lookback period in days")
    ):
        return _dashboard.get_overview(period_days)

    @router.get("/revenue")
    async def revenue_breakdown(
        group_by: str = Query("payer", description="Group by: payer, drug_type, plan_type, therapeutic_class")
    ):
        return _dashboard.get_revenue_breakdown(group_by)

    @router.get("/payers")
    async def payer_summary():
        return _dashboard.get_payer_summary()

    @router.get("/underpayments")
    async def underpayment_alerts(
        min_gap: float = Query(5.0, description="Minimum gap amount to alert")
    ):
        return _dashboard.get_underpayment_alerts(min_gap)

    @router.get("/trends")
    async def revenue_trends(
        granularity: str = Query("monthly", description="monthly or weekly")
    ):
        return _dashboard.get_trends(granularity)

    @router.get("/kpi-cards")
    async def kpi_cards():
        return _dashboard.get_kpi_cards()


# ============================================================
# Module-level convenience
# ============================================================

def create_dashboard(claims_data: List[Dict]) -> PharmacyRevenueDashboard:
    """Create a dashboard instance with loaded claims."""
    dashboard = PharmacyRevenueDashboard()
    dashboard.load_claims(claims_data)
    return dashboard
