"""
GetPaidRx - Payer Performance Report Card Generator

Generates structured payer performance report cards analyzing payment
timeliness, reimbursement accuracy, denial rates, appeal success rates,
and overall relationship health. Used for contract negotiations and
identifying problematic payers.

Features:
  - Overall payer grade (A+ to F)
  - Timeliness scoring (days to payment)
  - Accuracy scoring (claim adjudication correctness)
  - Denial rate analysis with reason-code breakdown
  - Appeal success tracking
  - Trend comparison (period over period)
  - Contract compliance scoring
  - Peer benchmarking (how payer compares to peers)
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# Grading Scales
# ============================================================

GRADE_THRESHOLDS = [
    (95, "A+"), (90, "A"), (85, "A-"),
    (80, "B+"), (75, "B"), (70, "B-"),
    (65, "C+"), (60, "C"), (55, "C-"),
    (50, "D+"), (45, "D"), (40, "D-"),
    (0, "F"),
]

DIMENSION_WEIGHTS = {
    "timeliness": 0.25,       # How fast do they pay?
    "accuracy": 0.25,         # How correct are adjudications?
    "denial_rate": 0.20,      # How often do they deny?
    "appeal_success": 0.10,   # How often do appeals succeed?
    "reimbursement": 0.20,    # Fair reimbursement levels?
}

# Industry benchmarks
BENCHMARKS = {
    "avg_days_to_pay": 21,            # days
    "clean_claim_rate": 95.0,         # percent
    "denial_rate": 5.0,               # percent
    "appeal_overturn_rate": 40.0,     # percent
    "underwater_rate": 8.0,           # percent
    "avg_margin_percent": 8.0,        # percent
}


@dataclass
class PayerClaim:
    """Single claim data for payer analysis."""
    claim_id: str
    payer: str
    pbm: str = ""
    submit_date: str = ""           # YYYY-MM-DD
    adjudication_date: str = ""     # YYYY-MM-DD
    payment_date: str = ""          # YYYY-MM-DD
    billed_amount: float = 0.0
    allowed_amount: float = 0.0
    paid_amount: float = 0.0
    copay: float = 0.0
    cost: float = 0.0               # pharmacy acquisition cost
    status: str = "paid"            # paid, denied, pending, reversed
    denial_reason: str = ""
    appeal_filed: bool = False
    appeal_outcome: str = ""        # overturned, upheld, pending
    drug_name: str = ""
    ndc: str = ""
    therapeutic_class: str = ""
    contract_rate: Optional[float] = None  # contracted reimbursement rate


class PayerReportCard:
    """
    Generates comprehensive performance report cards for payers
    based on historical claim data analysis.
    """

    def __init__(self):
        self.claims: List[PayerClaim] = []

    def load_claims(self, claims_data: List[Dict[str, Any]]) -> int:
        """Load claims from list of dicts."""
        loaded = 0
        for c in claims_data:
            try:
                claim = PayerClaim(
                    claim_id=str(c.get("claim_id", f"CLM-{loaded}")),
                    payer=str(c.get("payer", "Unknown")),
                    pbm=str(c.get("pbm", "")),
                    submit_date=str(c.get("submit_date", "")),
                    adjudication_date=str(c.get("adjudication_date", "")),
                    payment_date=str(c.get("payment_date", "")),
                    billed_amount=float(c.get("billed_amount", 0)),
                    allowed_amount=float(c.get("allowed_amount", 0)),
                    paid_amount=float(c.get("paid_amount", 0)),
                    copay=float(c.get("copay", 0)),
                    cost=float(c.get("cost", 0)),
                    status=str(c.get("status", "paid")),
                    denial_reason=str(c.get("denial_reason", "")),
                    appeal_filed=bool(c.get("appeal_filed", False)),
                    appeal_outcome=str(c.get("appeal_outcome", "")),
                    drug_name=str(c.get("drug_name", "")),
                    ndc=str(c.get("ndc", "")),
                    therapeutic_class=str(c.get("therapeutic_class", "")),
                    contract_rate=c.get("contract_rate"),
                )
                self.claims.append(claim)
                loaded += 1
            except (ValueError, TypeError):
                continue
        return loaded

    # -------------------------------------------------------
    # Report Card Generation
    # -------------------------------------------------------

    def generate_all_report_cards(self) -> Dict[str, Any]:
        """Generate report cards for all payers in the dataset."""
        payer_groups = defaultdict(list)
        for claim in self.claims:
            payer_groups[claim.payer].append(claim)

        report_cards = []
        for payer, claims in sorted(payer_groups.items()):
            card = self._generate_single_report_card(payer, claims)
            report_cards.append(card)

        # Compute peer rankings
        self._compute_peer_rankings(report_cards)

        return {
            "generated_at": datetime.now().isoformat(),
            "total_payers": len(report_cards),
            "total_claims_analyzed": len(self.claims),
            "report_cards": report_cards,
            "industry_benchmarks": BENCHMARKS,
            "portfolio_summary": self._portfolio_summary(report_cards),
        }

    def generate_report_card(self, payer_name: str) -> Dict[str, Any]:
        """Generate a report card for a specific payer."""
        payer_claims = [c for c in self.claims if c.payer == payer_name]
        if not payer_claims:
            return {"error": f"No claims found for payer: {payer_name}"}
        return self._generate_single_report_card(payer_name, payer_claims)

    def _generate_single_report_card(
        self, payer: str, claims: List[PayerClaim]
    ) -> Dict[str, Any]:
        """Build a complete report card for one payer."""
        total = len(claims)

        # Score each dimension
        timeliness = self._score_timeliness(claims)
        accuracy = self._score_accuracy(claims)
        denial = self._score_denial_rate(claims)
        appeals = self._score_appeals(claims)
        reimbursement = self._score_reimbursement(claims)

        dimensions = {
            "timeliness": timeliness,
            "accuracy": accuracy,
            "denial_rate": denial,
            "appeal_success": appeals,
            "reimbursement": reimbursement,
        }

        # Weighted composite score
        composite = sum(
            dim["score"] * DIMENSION_WEIGHTS[name]
            for name, dim in dimensions.items()
        )
        composite = round(composite, 1)
        grade = self._assign_grade(composite)

        # PBM association
        pbms = list(set(c.pbm for c in claims if c.pbm))

        # Volume and financial summary
        paid_claims = [c for c in claims if c.status == "paid"]
        total_billed = sum(c.billed_amount for c in claims)
        total_paid = sum(c.paid_amount for c in paid_claims)
        total_cost = sum(c.cost for c in paid_claims)
        total_margin = total_paid + sum(c.copay for c in paid_claims) - total_cost

        return {
            "payer": payer,
            "pbms": pbms,
            "composite_score": composite,
            "grade": grade,
            "claim_count": total,
            "date_range": self._get_date_range(claims),
            "financial_summary": {
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "total_cost": round(total_cost, 2),
                "total_margin": round(total_margin, 2),
                "margin_percent": round(
                    (total_margin / total_cost * 100) if total_cost > 0 else 0, 2
                ),
                "avg_paid_per_claim": round(total_paid / len(paid_claims), 2) if paid_claims else 0,
            },
            "dimensions": {
                name: {
                    "score": dim["score"],
                    "grade": self._assign_grade(dim["score"]),
                    "weight": DIMENSION_WEIGHTS[name],
                    "weighted_score": round(dim["score"] * DIMENSION_WEIGHTS[name], 1),
                    "details": dim.get("details", {}),
                    "benchmark_comparison": dim.get("benchmark_comparison", ""),
                }
                for name, dim in dimensions.items()
            },
            "strengths": self._identify_strengths(dimensions),
            "weaknesses": self._identify_weaknesses(dimensions),
            "recommendations": self._generate_payer_recommendations(
                payer, dimensions, claims
            ),
        }

    # -------------------------------------------------------
    # Dimension Scorers
    # -------------------------------------------------------

    def _score_timeliness(self, claims: List[PayerClaim]) -> Dict[str, Any]:
        """Score payment timeliness."""
        days_to_pay = []
        for c in claims:
            if c.submit_date and c.payment_date and c.status == "paid":
                try:
                    submit = datetime.strptime(c.submit_date[:10], "%Y-%m-%d")
                    payment = datetime.strptime(c.payment_date[:10], "%Y-%m-%d")
                    days = (payment - submit).days
                    if days >= 0:
                        days_to_pay.append(days)
                except ValueError:
                    continue

        if not days_to_pay:
            return {"score": 50, "details": {"message": "Insufficient date data"}}

        avg_days = statistics.mean(days_to_pay)
        median_days = statistics.median(days_to_pay)
        over_30 = sum(1 for d in days_to_pay if d > 30)
        over_45 = sum(1 for d in days_to_pay if d > 45)

        # Score: 100 if avg ≤7 days, scales down linearly
        if avg_days <= 7:
            score = 100
        elif avg_days <= 14:
            score = 90
        elif avg_days <= 21:
            score = 80
        elif avg_days <= 30:
            score = 65
        elif avg_days <= 45:
            score = 45
        else:
            score = max(10, 45 - (avg_days - 45))

        # Penalty for late payments
        late_rate = over_30 / len(days_to_pay) * 100 if days_to_pay else 0
        if late_rate > 20:
            score -= 10
        if over_45 > 0:
            score -= 5

        benchmark = BENCHMARKS["avg_days_to_pay"]
        comparison = (
            f"{'Better' if avg_days < benchmark else 'Worse'} than "
            f"industry avg ({benchmark} days)"
        )

        return {
            "score": round(max(0, min(100, score)), 1),
            "details": {
                "avg_days_to_pay": round(avg_days, 1),
                "median_days_to_pay": round(median_days, 1),
                "min_days": min(days_to_pay),
                "max_days": max(days_to_pay),
                "claims_over_30_days": over_30,
                "claims_over_45_days": over_45,
                "late_rate_percent": round(late_rate, 1),
            },
            "benchmark_comparison": comparison,
        }

    def _score_accuracy(self, claims: List[PayerClaim]) -> Dict[str, Any]:
        """Score claim adjudication accuracy."""
        total = len(claims)
        paid = sum(1 for c in claims if c.status == "paid")
        denied = sum(1 for c in claims if c.status == "denied")
        reversed_claims = sum(1 for c in claims if c.status == "reversed")

        # Overturned appeals indicate initial adjudication errors
        overturned = sum(1 for c in claims if c.appeal_outcome == "overturned")

        # Clean claim rate (paid without issues)
        clean_rate = (paid / total * 100) if total > 0 else 0

        # Adjudication error rate (denials that were overturned)
        error_rate = (overturned / total * 100) if total > 0 else 0

        score = clean_rate
        score -= error_rate * 5  # Heavy penalty for wrong denials
        score -= (reversed_claims / total * 100) * 2 if total > 0 else 0

        benchmark = BENCHMARKS["clean_claim_rate"]
        comparison = (
            f"{'Above' if clean_rate >= benchmark else 'Below'} "
            f"industry clean claim rate ({benchmark}%)"
        )

        return {
            "score": round(max(0, min(100, score)), 1),
            "details": {
                "clean_claim_rate": round(clean_rate, 1),
                "error_rate": round(error_rate, 2),
                "paid_claims": paid,
                "denied_claims": denied,
                "reversed_claims": reversed_claims,
                "overturned_on_appeal": overturned,
            },
            "benchmark_comparison": comparison,
        }

    def _score_denial_rate(self, claims: List[PayerClaim]) -> Dict[str, Any]:
        """Score denial rate and patterns."""
        total = len(claims)
        denied = [c for c in claims if c.status == "denied"]
        denial_rate = (len(denied) / total * 100) if total > 0 else 0

        # Denial reason breakdown
        reason_counts = defaultdict(int)
        for c in denied:
            reason = c.denial_reason if c.denial_reason else "Unspecified"
            reason_counts[reason] += 1

        # Score inversely proportional to denial rate
        # 0% denials = 100, 5% = 75, 10% = 50, 20% = 25
        if denial_rate <= 2:
            score = 100
        elif denial_rate <= 5:
            score = 85 - (denial_rate - 2) * 5
        elif denial_rate <= 10:
            score = 70 - (denial_rate - 5) * 4
        elif denial_rate <= 20:
            score = 50 - (denial_rate - 10) * 2.5
        else:
            score = max(0, 25 - (denial_rate - 20))

        benchmark = BENCHMARKS["denial_rate"]
        comparison = (
            f"{'Below' if denial_rate < benchmark else 'Above'} "
            f"industry avg denial rate ({benchmark}%)"
        )

        return {
            "score": round(max(0, min(100, score)), 1),
            "details": {
                "denial_rate": round(denial_rate, 2),
                "denied_count": len(denied),
                "denial_reasons": dict(
                    sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
                ),
                "top_denial_reason": (
                    max(reason_counts, key=reason_counts.get) if reason_counts else "N/A"
                ),
            },
            "benchmark_comparison": comparison,
        }

    def _score_appeals(self, claims: List[PayerClaim]) -> Dict[str, Any]:
        """Score appeal outcomes."""
        appealed = [c for c in claims if c.appeal_filed]
        if not appealed:
            return {
                "score": 50,  # neutral if no appeals
                "details": {"message": "No appeals in dataset"},
                "benchmark_comparison": "No appeals data",
            }

        overturned = sum(1 for c in appealed if c.appeal_outcome == "overturned")
        upheld = sum(1 for c in appealed if c.appeal_outcome == "upheld")
        pending = sum(1 for c in appealed if c.appeal_outcome == "pending")

        overturn_rate = (overturned / len(appealed) * 100) if appealed else 0

        # Higher overturn rate = payer initially denied incorrectly = LOWER score
        # From payer perspective: high overturn means bad initial adjudication
        if overturn_rate <= 20:
            score = 90
        elif overturn_rate <= 35:
            score = 70
        elif overturn_rate <= 50:
            score = 50
        elif overturn_rate <= 70:
            score = 30
        else:
            score = 15

        benchmark = BENCHMARKS["appeal_overturn_rate"]
        comparison = (
            f"Overturn rate {'below' if overturn_rate < benchmark else 'above'} "
            f"industry avg ({benchmark}%)"
        )

        return {
            "score": round(max(0, min(100, score)), 1),
            "details": {
                "appeals_filed": len(appealed),
                "overturned": overturned,
                "upheld": upheld,
                "pending": pending,
                "overturn_rate": round(overturn_rate, 1),
            },
            "benchmark_comparison": comparison,
        }

    def _score_reimbursement(self, claims: List[PayerClaim]) -> Dict[str, Any]:
        """Score reimbursement fairness."""
        paid_claims = [c for c in claims if c.status == "paid" and c.cost > 0]
        if not paid_claims:
            return {"score": 50, "details": {"message": "No paid claims with cost data"}}

        margins = []
        underwater = 0
        for c in paid_claims:
            total_received = c.paid_amount + c.copay
            margin_pct = ((total_received - c.cost) / c.cost * 100) if c.cost > 0 else 0
            margins.append(margin_pct)
            if total_received < c.cost:
                underwater += 1

        avg_margin = statistics.mean(margins)
        underwater_rate = (underwater / len(paid_claims) * 100)

        # Score based on margin and underwater rate
        if avg_margin >= 10:
            score = 95
        elif avg_margin >= 8:
            score = 85
        elif avg_margin >= 5:
            score = 70
        elif avg_margin >= 2:
            score = 55
        elif avg_margin >= 0:
            score = 40
        else:
            score = max(0, 20 + avg_margin * 2)

        # Penalty for underwater claims
        score -= min(30, underwater_rate * 1.5)

        benchmark_margin = BENCHMARKS["avg_margin_percent"]
        comparison = (
            f"Margin {'above' if avg_margin > benchmark_margin else 'below'} "
            f"industry target ({benchmark_margin}%)"
        )

        return {
            "score": round(max(0, min(100, score)), 1),
            "details": {
                "avg_margin_percent": round(avg_margin, 2),
                "median_margin_percent": round(statistics.median(margins), 2),
                "min_margin_percent": round(min(margins), 2),
                "max_margin_percent": round(max(margins), 2),
                "underwater_count": underwater,
                "underwater_rate": round(underwater_rate, 1),
                "total_paid_analyzed": len(paid_claims),
            },
            "benchmark_comparison": comparison,
        }

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------

    def _assign_grade(self, score: float) -> str:
        """Assign letter grade from score."""
        for threshold, grade in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "F"

    def _get_date_range(self, claims: List[PayerClaim]) -> Dict[str, str]:
        """Get date range of claims."""
        dates = []
        for c in claims:
            for d in [c.submit_date, c.payment_date]:
                if d:
                    dates.append(d[:10])
        if dates:
            return {"start": min(dates), "end": max(dates)}
        return {"start": "unknown", "end": "unknown"}

    def _identify_strengths(self, dimensions: Dict) -> List[str]:
        """Identify payer strengths."""
        strengths = []
        for name, dim in dimensions.items():
            if dim["score"] >= 80:
                label = name.replace("_", " ").title()
                strengths.append(f"Strong {label} (score: {dim['score']})")
        return strengths

    def _identify_weaknesses(self, dimensions: Dict) -> List[str]:
        """Identify payer weaknesses."""
        weaknesses = []
        for name, dim in dimensions.items():
            if dim["score"] < 50:
                label = name.replace("_", " ").title()
                weaknesses.append(f"Weak {label} (score: {dim['score']})")
        return weaknesses

    def _generate_payer_recommendations(
        self, payer: str, dimensions: Dict, claims: List[PayerClaim]
    ) -> List[str]:
        """Generate payer-specific recommendations."""
        recs = []

        if dimensions["timeliness"]["score"] < 60:
            avg_days = dimensions["timeliness"]["details"].get("avg_days_to_pay", "?")
            recs.append(
                f"File prompt-pay compliance complaint — avg {avg_days} days exceeds "
                "state prompt-pay requirements."
            )

        if dimensions["denial_rate"]["score"] < 50:
            top_reason = dimensions["denial_rate"]["details"].get("top_denial_reason", "N/A")
            recs.append(
                f"Address primary denial reason: '{top_reason}'. "
                "Review claim submission workflow for preventable denials."
            )

        if dimensions["reimbursement"]["score"] < 50:
            margin = dimensions["reimbursement"]["details"].get("avg_margin_percent", 0)
            recs.append(
                f"Negotiate rate increase — current avg margin ({margin}%) "
                "is below sustainable threshold."
            )

        if dimensions["appeal_success"]["details"].get("overturn_rate", 0) > 50:
            recs.append(
                "High appeal overturn rate indicates incorrect initial denials. "
                "Request payer audit of adjudication logic."
            )

        if not recs:
            recs.append(f"{payer} is performing well across all dimensions.")

        return recs

    def _compute_peer_rankings(self, report_cards: List[Dict]) -> None:
        """Add peer ranking to each report card."""
        sorted_cards = sorted(
            report_cards,
            key=lambda c: c["composite_score"],
            reverse=True,
        )
        for i, card in enumerate(sorted_cards):
            card["peer_rank"] = i + 1
            card["peer_total"] = len(sorted_cards)
            card["peer_percentile"] = round(
                (1 - i / len(sorted_cards)) * 100, 1
            ) if sorted_cards else 0

    def _portfolio_summary(self, report_cards: List[Dict]) -> Dict[str, Any]:
        """Generate portfolio-level summary across all payers."""
        if not report_cards:
            return {}

        scores = [c["composite_score"] for c in report_cards]
        grades = defaultdict(int)
        for c in report_cards:
            grades[c["grade"]] += 1

        best = max(report_cards, key=lambda c: c["composite_score"])
        worst = min(report_cards, key=lambda c: c["composite_score"])

        return {
            "avg_score": round(statistics.mean(scores), 1),
            "median_score": round(statistics.median(scores), 1),
            "grade_distribution": dict(grades),
            "best_payer": {"name": best["payer"], "score": best["composite_score"], "grade": best["grade"]},
            "worst_payer": {"name": worst["payer"], "score": worst["composite_score"], "grade": worst["grade"]},
            "payers_below_c": sum(1 for s in scores if s < 60),
        }


# ============================================================
# Module-level convenience
# ============================================================

def generate_payer_report_cards(claims_data: List[Dict]) -> Dict[str, Any]:
    """Quick report card generation from claims data."""
    generator = PayerReportCard()
    generator.load_claims(claims_data)
    return generator.generate_all_report_cards()
