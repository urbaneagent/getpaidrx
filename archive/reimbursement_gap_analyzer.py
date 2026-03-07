"""
GetPaidRx - Pharmacy Reimbursement Gap Analyzer

Identifies systematic underpayments by comparing NADAC acquisition cost
benchmarks against actual reimbursement amounts. Detects payer-specific
underpayment patterns, trending underwater claims, and generates appeal-ready
gap analysis reports with projected revenue recovery estimates.

Core capabilities:
  - Per-claim gap analysis (reimbursement vs NADAC + dispensing fee)
  - Payer-level pattern detection (systematic underpayers)
  - Drug-class gap aggregation (GPI/therapeutic class)
  - Trending analysis (worsening/improving gaps over time)
  - Revenue recovery projection
  - Appeal priority scoring
"""

import json
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# Constants
# ============================================================

# Standard dispensing fee assumptions by state (national average if unknown)
STATE_DISPENSING_FEES = {
    "KY": 10.64,
    "FL": 9.00,
    "OH": 10.49,
    "TX": 7.50,
    "CA": 7.25,
    "NY": 8.00,
    "PA": 10.00,
    "IL": 6.80,
    "GA": 8.01,
    "NC": 6.00,
    "DEFAULT": 10.00,
}

# Minimum acceptable margin thresholds
MIN_MARGIN_PERCENT = 2.0        # Claims below 2% margin flagged
UNDERWATER_THRESHOLD = 0.0       # Below cost = underwater
CRITICAL_GAP_THRESHOLD = -5.0    # >$5 below cost = critical

# PBM standard dispensing fees (what should be added to ingredient cost)
PBM_DISPENSING_FEES = {
    "express_scripts": 1.75,
    "cvs_caremark": 1.25,
    "optumrx": 1.50,
    "cigna": 1.75,
    "medimpact": 2.00,
    "prime_therapeutics": 1.50,
    "elixir": 2.25,
    "navitus": 2.00,
    "default": 1.75,
}

# Therapeutic class risk weights for appeal prioritization
THERAPEUTIC_CLASS_WEIGHTS = {
    "specialty": 3.0,
    "brand": 2.0,
    "generic_sole_source": 2.5,
    "generic_multi_source": 1.0,
    "otc": 0.5,
    "compound": 2.5,
    "controlled": 1.5,
}


@dataclass
class Claim:
    """Represents a single pharmacy claim for gap analysis."""
    claim_id: str
    ndc: str
    drug_name: str
    payer: str
    pbm: str = ""
    plan_type: str = ""            # commercial, medicaid, medicare, cash
    fill_date: str = ""             # YYYY-MM-DD
    quantity: float = 0.0
    days_supply: int = 0
    nadac_per_unit: float = 0.0
    acquisition_cost: float = 0.0   # pharmacy's actual cost
    reimbursement: float = 0.0      # total amount paid by payer
    patient_copay: float = 0.0
    dispensing_fee_paid: float = 0.0
    therapeutic_class: str = ""
    drug_type: str = "generic_multi_source"  # generic/brand/specialty
    gpi: str = ""
    state: str = ""


@dataclass
class GapResult:
    """Result of gap analysis for a single claim."""
    claim_id: str
    drug_name: str
    payer: str
    pbm: str
    fill_date: str
    # Cost components
    nadac_cost: float           # NADAC per unit × quantity
    acquisition_cost: float     # Actual cost to pharmacy
    benchmark_cost: float       # Higher of NADAC or acquisition
    expected_dispensing_fee: float
    total_expected: float       # benchmark_cost + dispensing fee
    # Reimbursement
    total_reimbursement: float  # payer paid + copay
    # Gap
    gap_amount: float           # total_reimbursement - total_expected
    gap_percent: float          # gap as % of expected
    margin: float               # actual margin dollars
    margin_percent: float       # actual margin %
    # Classification
    is_underwater: bool
    is_critical: bool
    is_marginal: bool           # positive but below MIN_MARGIN
    severity: str               # critical / underwater / marginal / adequate / profitable
    appeal_priority: float      # 0-100 score


class ReimbursementGapAnalyzer:
    """
    Analyzes pharmacy claims to identify systematic underpayment patterns
    and generates appeal-ready gap analysis with recovery projections.
    """

    def __init__(self, state: str = "DEFAULT"):
        self.state = state
        self.dispensing_fee = STATE_DISPENSING_FEES.get(state, STATE_DISPENSING_FEES["DEFAULT"])
        self.claims: List[Claim] = []
        self.results: List[GapResult] = []

    # -------------------------------------------------------
    # Claim Loading
    # -------------------------------------------------------

    def load_claims(self, claims: List[Dict[str, Any]]) -> int:
        """Load claims from list of dicts. Returns count loaded."""
        loaded = 0
        for c in claims:
            try:
                claim = Claim(
                    claim_id=str(c.get("claim_id", f"CLM-{loaded}")),
                    ndc=str(c.get("ndc", "")),
                    drug_name=str(c.get("drug_name", "Unknown")),
                    payer=str(c.get("payer", "Unknown")),
                    pbm=str(c.get("pbm", "")),
                    plan_type=str(c.get("plan_type", "")),
                    fill_date=str(c.get("fill_date", "")),
                    quantity=float(c.get("quantity", 0)),
                    days_supply=int(c.get("days_supply", 0)),
                    nadac_per_unit=float(c.get("nadac_per_unit", 0)),
                    acquisition_cost=float(c.get("acquisition_cost", 0)),
                    reimbursement=float(c.get("reimbursement", 0)),
                    patient_copay=float(c.get("patient_copay", 0)),
                    dispensing_fee_paid=float(c.get("dispensing_fee_paid", 0)),
                    therapeutic_class=str(c.get("therapeutic_class", "")),
                    drug_type=str(c.get("drug_type", "generic_multi_source")),
                    gpi=str(c.get("gpi", "")),
                    state=str(c.get("state", self.state)),
                )
                self.claims.append(claim)
                loaded += 1
            except (ValueError, TypeError):
                continue
        return loaded

    # -------------------------------------------------------
    # Core Gap Analysis
    # -------------------------------------------------------

    def analyze_all(self) -> Dict[str, Any]:
        """Run gap analysis on all loaded claims."""
        self.results = []

        for claim in self.claims:
            result = self._analyze_single_claim(claim)
            self.results.append(result)

        return self._build_analysis_report()

    def _analyze_single_claim(self, claim: Claim) -> GapResult:
        """Analyze a single claim for reimbursement gap."""
        # Calculate benchmark cost
        nadac_cost = claim.nadac_per_unit * claim.quantity
        acquisition = claim.acquisition_cost if claim.acquisition_cost > 0 else nadac_cost
        benchmark_cost = max(nadac_cost, acquisition)

        # Expected dispensing fee
        state_fee = STATE_DISPENSING_FEES.get(claim.state, self.dispensing_fee)
        pbm_key = claim.pbm.lower().replace(" ", "_") if claim.pbm else "default"
        pbm_fee = PBM_DISPENSING_FEES.get(pbm_key, PBM_DISPENSING_FEES["default"])
        expected_fee = max(state_fee, pbm_fee) if claim.plan_type == "medicaid" else state_fee

        total_expected = benchmark_cost + expected_fee

        # Total reimbursement (payer + copay)
        total_reimbursement = claim.reimbursement + claim.patient_copay

        # Gap calculation
        gap_amount = total_reimbursement - total_expected
        gap_percent = (gap_amount / total_expected * 100) if total_expected > 0 else 0

        # Actual margin (vs acquisition cost)
        margin = total_reimbursement - acquisition
        margin_percent = (margin / acquisition * 100) if acquisition > 0 else 0

        # Classification
        is_underwater = gap_amount < UNDERWATER_THRESHOLD
        is_critical = gap_amount < CRITICAL_GAP_THRESHOLD
        is_marginal = 0 <= margin_percent < MIN_MARGIN_PERCENT

        if is_critical:
            severity = "critical"
        elif is_underwater:
            severity = "underwater"
        elif is_marginal:
            severity = "marginal"
        elif margin_percent < 10:
            severity = "adequate"
        else:
            severity = "profitable"

        # Appeal priority scoring
        appeal_priority = self._compute_appeal_priority(
            gap_amount, gap_percent, claim.drug_type,
            claim.quantity, claim.days_supply, severity
        )

        return GapResult(
            claim_id=claim.claim_id,
            drug_name=claim.drug_name,
            payer=claim.payer,
            pbm=claim.pbm,
            fill_date=claim.fill_date,
            nadac_cost=round(nadac_cost, 2),
            acquisition_cost=round(acquisition, 2),
            benchmark_cost=round(benchmark_cost, 2),
            expected_dispensing_fee=round(expected_fee, 2),
            total_expected=round(total_expected, 2),
            total_reimbursement=round(total_reimbursement, 2),
            gap_amount=round(gap_amount, 2),
            gap_percent=round(gap_percent, 2),
            margin=round(margin, 2),
            margin_percent=round(margin_percent, 2),
            is_underwater=is_underwater,
            is_critical=is_critical,
            is_marginal=is_marginal,
            severity=severity,
            appeal_priority=round(appeal_priority, 1),
        )

    def _compute_appeal_priority(
        self, gap_amount, gap_percent, drug_type, quantity, days_supply, severity
    ) -> float:
        """Compute appeal priority score (0-100) for a claim."""
        score = 0.0

        # Gap magnitude (40 points max)
        abs_gap = abs(gap_amount)
        if abs_gap > 50:
            score += 40
        elif abs_gap > 20:
            score += 30
        elif abs_gap > 10:
            score += 20
        elif abs_gap > 5:
            score += 10

        # Severity (25 points)
        severity_scores = {"critical": 25, "underwater": 20, "marginal": 10, "adequate": 0, "profitable": 0}
        score += severity_scores.get(severity, 0)

        # Drug type weight (20 points)
        type_weight = THERAPEUTIC_CLASS_WEIGHTS.get(drug_type, 1.0)
        score += min(20, type_weight * 8)

        # Frequency factor (15 points) - higher day supply = recurring loss
        if days_supply >= 90:
            score += 15
        elif days_supply >= 30:
            score += 10
        elif days_supply >= 14:
            score += 5

        return min(100, score)

    # -------------------------------------------------------
    # Aggregated Analysis Report
    # -------------------------------------------------------

    def _build_analysis_report(self) -> Dict[str, Any]:
        """Build comprehensive analysis report from results."""
        if not self.results:
            return {"error": "No results to analyze", "total_claims": 0}

        total = len(self.results)
        underwater = [r for r in self.results if r.is_underwater]
        critical = [r for r in self.results if r.is_critical]
        marginal = [r for r in self.results if r.is_marginal]
        profitable = [r for r in self.results if r.severity == "profitable"]

        gaps = [r.gap_amount for r in self.results]
        margins = [r.margin for r in self.results]

        total_gap = sum(r.gap_amount for r in underwater)
        total_margin = sum(margins)

        return {
            "analyzed_at": datetime.now().isoformat(),
            "total_claims": total,
            "summary": {
                "total_reimbursement": round(sum(r.total_reimbursement for r in self.results), 2),
                "total_expected": round(sum(r.total_expected for r in self.results), 2),
                "total_gap": round(total_gap, 2),
                "total_margin": round(total_margin, 2),
                "avg_gap": round(statistics.mean(gaps), 2) if gaps else 0,
                "median_gap": round(statistics.median(gaps), 2) if gaps else 0,
                "avg_margin_percent": round(
                    statistics.mean(r.margin_percent for r in self.results), 2
                ) if self.results else 0,
            },
            "severity_breakdown": {
                "critical": len(critical),
                "underwater": len(underwater),
                "marginal": len(marginal),
                "adequate": sum(1 for r in self.results if r.severity == "adequate"),
                "profitable": len(profitable),
            },
            "underwater_rate": round(len(underwater) / total * 100, 1),
            "recovery_potential": self._compute_recovery_potential(underwater),
            "payer_analysis": self._analyze_by_payer(),
            "drug_analysis": self._analyze_by_drug(),
            "trend_analysis": self._analyze_trends(),
            "top_appeal_targets": self._get_top_appeal_targets(20),
            "recommendations": self._generate_recommendations(underwater, critical, total),
        }

    # -------------------------------------------------------
    # Payer Analysis
    # -------------------------------------------------------

    def _analyze_by_payer(self) -> List[Dict[str, Any]]:
        """Analyze gaps grouped by payer."""
        payer_data = defaultdict(list)
        for r in self.results:
            payer_data[r.payer].append(r)

        payer_analysis = []
        for payer, results in sorted(payer_data.items()):
            total = len(results)
            underwater = [r for r in results if r.is_underwater]
            gaps = [r.gap_amount for r in results]
            total_gap = sum(r.gap_amount for r in underwater)

            payer_analysis.append({
                "payer": payer,
                "claim_count": total,
                "underwater_count": len(underwater),
                "underwater_rate": round(len(underwater) / total * 100, 1) if total > 0 else 0,
                "total_gap": round(total_gap, 2),
                "avg_gap": round(statistics.mean(gaps), 2) if gaps else 0,
                "avg_margin_percent": round(
                    statistics.mean(r.margin_percent for r in results), 2
                ) if results else 0,
                "worst_gap": round(min(gaps), 2) if gaps else 0,
                "annualized_loss": round(total_gap * (365 / 30), 2),  # rough annualization
                "risk_level": (
                    "critical" if len(underwater) / total > 0.3 else
                    "high" if len(underwater) / total > 0.15 else
                    "moderate" if len(underwater) / total > 0.05 else
                    "low"
                ) if total > 0 else "unknown",
            })

        # Sort by total gap (worst first)
        payer_analysis.sort(key=lambda x: x["total_gap"])
        return payer_analysis

    # -------------------------------------------------------
    # Drug Analysis
    # -------------------------------------------------------

    def _analyze_by_drug(self) -> List[Dict[str, Any]]:
        """Analyze gaps grouped by drug name."""
        drug_data = defaultdict(list)
        for r in self.results:
            drug_data[r.drug_name].append(r)

        drug_analysis = []
        for drug, results in drug_data.items():
            total = len(results)
            underwater = [r for r in results if r.is_underwater]
            if not underwater:
                continue  # Only report drugs with gaps

            total_gap = sum(r.gap_amount for r in underwater)
            drug_analysis.append({
                "drug_name": drug,
                "claim_count": total,
                "underwater_count": len(underwater),
                "total_gap": round(total_gap, 2),
                "avg_gap_per_claim": round(total_gap / len(underwater), 2) if underwater else 0,
                "payers_involved": list(set(r.payer for r in underwater)),
                "avg_appeal_priority": round(
                    statistics.mean(r.appeal_priority for r in underwater), 1
                ),
            })

        drug_analysis.sort(key=lambda x: x["total_gap"])
        return drug_analysis[:30]  # Top 30 worst drugs

    # -------------------------------------------------------
    # Trend Analysis
    # -------------------------------------------------------

    def _analyze_trends(self) -> Dict[str, Any]:
        """Analyze gap trends over time."""
        monthly_data = defaultdict(list)
        for r in self.results:
            if r.fill_date:
                month_key = r.fill_date[:7]  # YYYY-MM
                monthly_data[month_key].append(r)

        if len(monthly_data) < 2:
            return {"message": "Insufficient data for trend analysis", "months": 0}

        monthly_stats = []
        for month in sorted(monthly_data.keys()):
            results = monthly_data[month]
            underwater = [r for r in results if r.is_underwater]
            monthly_stats.append({
                "month": month,
                "claim_count": len(results),
                "underwater_count": len(underwater),
                "underwater_rate": round(len(underwater) / len(results) * 100, 1),
                "total_gap": round(sum(r.gap_amount for r in underwater), 2),
                "avg_margin": round(statistics.mean(r.margin_percent for r in results), 2),
            })

        # Detect trend direction
        if len(monthly_stats) >= 2:
            rates = [m["underwater_rate"] for m in monthly_stats]
            first_half = statistics.mean(rates[:len(rates) // 2])
            second_half = statistics.mean(rates[len(rates) // 2:])
            trend = "worsening" if second_half > first_half + 2 else (
                "improving" if second_half < first_half - 2 else "stable"
            )
        else:
            trend = "insufficient_data"

        return {
            "months_analyzed": len(monthly_stats),
            "trend_direction": trend,
            "monthly_data": monthly_stats,
        }

    # -------------------------------------------------------
    # Recovery & Recommendations
    # -------------------------------------------------------

    def _compute_recovery_potential(self, underwater: List[GapResult]) -> Dict[str, Any]:
        """Estimate revenue recovery potential from appeals."""
        if not underwater:
            return {"total_potential": 0, "realistic_recovery": 0, "claims_to_appeal": 0}

        total_potential = abs(sum(r.gap_amount for r in underwater))

        # Historical appeal success rates by severity
        success_rates = {"critical": 0.45, "underwater": 0.35, "marginal": 0.20}
        weighted_recovery = sum(
            abs(r.gap_amount) * success_rates.get(r.severity, 0.25)
            for r in underwater
        )

        # High-priority appeals only
        high_priority = [r for r in underwater if r.appeal_priority >= 50]

        return {
            "total_potential": round(total_potential, 2),
            "realistic_recovery": round(weighted_recovery, 2),
            "recovery_rate_estimate": round(
                (weighted_recovery / total_potential * 100) if total_potential > 0 else 0, 1
            ),
            "claims_to_appeal": len(underwater),
            "high_priority_appeals": len(high_priority),
            "high_priority_recovery": round(
                sum(abs(r.gap_amount) * success_rates.get(r.severity, 0.25) for r in high_priority), 2
            ),
            "annualized_potential": round(total_potential * 12, 2),  # Monthly to annual
        }

    def _get_top_appeal_targets(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get top claims to appeal by priority score."""
        underwater = [r for r in self.results if r.is_underwater]
        underwater.sort(key=lambda r: r.appeal_priority, reverse=True)

        return [
            {
                "claim_id": r.claim_id,
                "drug_name": r.drug_name,
                "payer": r.payer,
                "pbm": r.pbm,
                "fill_date": r.fill_date,
                "gap_amount": r.gap_amount,
                "total_expected": r.total_expected,
                "total_reimbursement": r.total_reimbursement,
                "severity": r.severity,
                "appeal_priority": r.appeal_priority,
            }
            for r in underwater[:count]
        ]

    def _generate_recommendations(
        self, underwater: List[GapResult], critical: List[GapResult], total: int
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recs = []

        underwater_rate = len(underwater) / total * 100 if total > 0 else 0

        if len(critical) > 0:
            total_critical_loss = abs(sum(r.gap_amount for r in critical))
            recs.append({
                "priority": "critical",
                "title": "Appeal Critical Underpayments Immediately",
                "description": f"{len(critical)} claims are critically underpaid "
                               f"(>${abs(CRITICAL_GAP_THRESHOLD)}/claim below cost). "
                               f"Total loss: ${total_critical_loss:,.2f}.",
                "action": "File formal appeals with supporting NADAC documentation for all critical claims.",
            })

        # Payer-specific recommendations
        payer_analysis = self._analyze_by_payer()
        worst_payers = [p for p in payer_analysis if p["risk_level"] in ("critical", "high")]
        if worst_payers:
            payer_names = ", ".join(p["payer"] for p in worst_payers[:3])
            recs.append({
                "priority": "high",
                "title": "Renegotiate Contracts with Worst Payers",
                "description": f"Systematic underpayment detected from: {payer_names}. "
                               f"These payers have underwater rates above 15%.",
                "action": "Schedule contract renegotiation meetings. Present NADAC gap data as evidence.",
            })

        if underwater_rate > 20:
            recs.append({
                "priority": "high",
                "title": "Review Overall Contract Portfolio",
                "description": f"{underwater_rate:.0f}% of claims are underwater. "
                               "This indicates systemic reimbursement issues.",
                "action": "Engage pharmacy benefit consultant to review all payer contracts.",
            })

        # Drug-specific
        drug_analysis = self._analyze_by_drug()
        if drug_analysis:
            worst_drug = drug_analysis[0]
            recs.append({
                "priority": "medium",
                "title": f"Address {worst_drug['drug_name']} Underpayments",
                "description": f"Largest drug-level gap: ${abs(worst_drug['total_gap']):,.2f} "
                               f"across {worst_drug['underwater_count']} claims.",
                "action": "Consider formulary alternatives, manufacturer rebate programs, "
                          "or GPO contract renegotiation.",
            })

        if not recs:
            recs.append({
                "priority": "info",
                "title": "Reimbursement Levels Healthy",
                "description": "No significant underpayment patterns detected.",
                "action": "Continue monitoring monthly. Set up NADAC price alerts for key drugs.",
            })

        return recs

    # -------------------------------------------------------
    # Serialization
    # -------------------------------------------------------

    def to_json(self) -> str:
        """Serialize full analysis to JSON."""
        report = self.analyze_all()
        return json.dumps(report, indent=2, default=str)


# ============================================================
# Module-level convenience
# ============================================================

def analyze_claims(claims: List[Dict], state: str = "KY") -> Dict[str, Any]:
    """Quick analysis of claims list."""
    analyzer = ReimbursementGapAnalyzer(state=state)
    analyzer.load_claims(claims)
    return analyzer.analyze_all()
