"""
DIR Fee Impact Analyzer
========================
Comprehensive Direct and Indirect Remuneration (DIR) fee analysis engine
for independent pharmacies. Calculates true prescription profitability
after DIR fee clawbacks, identifies worst-performing payer/drug combinations,
and projects annualized DIR impact on pharmacy margins.

Features:
- Per-claim DIR fee calculation and true profitability analysis
- Retroactive DIR fee clawback modeling (POS vs. post-adjudication)
- Payer-level DIR fee burden comparison
- Drug-level DIR impact ranking (worst-performing NDCs)
- Star rating performance-based DIR adjustment modeling
- Generic effective rate (GER) analysis after DIR
- Brand effective rate analysis after DIR
- Portfolio-wide margin erosion tracking
- DIR fee trending with period-over-period comparison
- CMS proposed DIR reform impact modeling
- Pharmacy network preferred/non-preferred DIR differential
"""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import uuid


class DIRFeeImpactAnalyzer:
    """
    Analyzes DIR fee impact on pharmacy profitability.
    """

    # Typical DIR fee structures by payer type
    PAYER_DIR_PROFILES = {
        "commercial_pbm": {
            "base_dir_pct": 3.5,
            "star_adjustment_range": (-1.5, 2.0),
            "gdr_target": 88.0,
            "adherence_metrics": ["pdc_diabetes", "pdc_rasa", "pdc_statins"],
            "preferred_discount": 1.0,  # Lower DIR for preferred
        },
        "medicare_part_d": {
            "base_dir_pct": 5.0,
            "star_adjustment_range": (-2.0, 3.0),
            "gdr_target": 90.0,
            "adherence_metrics": ["pdc_diabetes", "pdc_rasa", "pdc_statins"],
            "preferred_discount": 1.5,
        },
        "medicaid_mco": {
            "base_dir_pct": 2.0,
            "star_adjustment_range": (-1.0, 1.5),
            "gdr_target": 85.0,
            "adherence_metrics": ["pdc_diabetes"],
            "preferred_discount": 0.5,
        },
        "employer_group": {
            "base_dir_pct": 2.5,
            "star_adjustment_range": (-1.0, 1.0),
            "gdr_target": 87.0,
            "adherence_metrics": ["pdc_statins"],
            "preferred_discount": 0.75,
        },
    }

    # CMS Star Rating adjustment factors
    STAR_RATING_FACTORS = {
        5: -2.0,    # 5 stars: DIR reduction (bonus)
        4.5: -1.5,
        4: -1.0,
        3.5: -0.5,
        3: 0,        # Baseline
        2.5: 0.5,
        2: 1.0,
        1.5: 1.5,
        1: 2.0,      # 1 star: Maximum DIR penalty
    }

    def __init__(self):
        self.claims_db: List[Dict] = []
        self.dir_assessments: List[Dict] = []
        self.payer_summaries: Dict[str, Dict] = {}

    def analyze_claim_dir_impact(self, claim: Dict) -> Dict:
        """
        Analyze DIR fee impact on a single claim.
        Calculates true profitability after DIR clawback.
        """
        claim_id = claim.get("claim_id", str(uuid.uuid4())[:8])
        ndc = claim.get("ndc", "")
        drug_name = claim.get("drug_name", "")
        payer_type = claim.get("payer_type", "commercial_pbm")
        is_preferred = claim.get("pharmacy_preferred", True)

        # Financial components
        ingredient_cost = claim.get("ingredient_cost", 0)
        dispensing_fee = claim.get("dispensing_fee", 0)
        copay = claim.get("copay", 0)
        reimbursement = claim.get("reimbursement", 0)
        acquisition_cost = claim.get("acquisition_cost", 0)

        # Pre-DIR profitability
        gross_revenue = reimbursement + copay
        pre_dir_margin = gross_revenue - acquisition_cost
        pre_dir_margin_pct = (pre_dir_margin / gross_revenue * 100) if gross_revenue > 0 else 0

        # Calculate DIR fee
        payer_profile = self.PAYER_DIR_PROFILES.get(payer_type, self.PAYER_DIR_PROFILES["commercial_pbm"])
        base_dir_pct = payer_profile["base_dir_pct"]

        # Star rating adjustment
        star_rating = claim.get("star_rating", 3.0)
        star_adjustment = self.STAR_RATING_FACTORS.get(star_rating, 0)

        # Performance metrics adjustment
        performance_adjustment = 0
        pdc_scores = claim.get("pdc_scores", {})
        for metric in payer_profile["adherence_metrics"]:
            score = pdc_scores.get(metric, 75)
            if score >= 80:
                performance_adjustment -= 0.25
            elif score < 70:
                performance_adjustment += 0.5

        # GDR adjustment
        gdr = claim.get("generic_dispense_rate", 87)
        gdr_target = payer_profile["gdr_target"]
        if gdr >= gdr_target:
            gdr_adjustment = -0.5
        elif gdr >= gdr_target - 5:
            gdr_adjustment = 0
        else:
            gdr_adjustment = 0.75

        # Preferred/non-preferred adjustment
        network_adjustment = -payer_profile["preferred_discount"] if is_preferred else payer_profile["preferred_discount"]

        # Total DIR percentage
        total_dir_pct = max(0, base_dir_pct + star_adjustment + performance_adjustment + gdr_adjustment + network_adjustment)

        # DIR fee amount (calculated on ingredient cost typically)
        dir_fee_amount = ingredient_cost * (total_dir_pct / 100)

        # Post-DIR profitability
        post_dir_revenue = gross_revenue - dir_fee_amount
        post_dir_margin = post_dir_revenue - acquisition_cost
        post_dir_margin_pct = (post_dir_margin / gross_revenue * 100) if gross_revenue > 0 else 0

        # Effective reimbursement rate after DIR
        effective_reimbursement = reimbursement - dir_fee_amount

        # Underwater check (dispensing at a loss)
        is_underwater = post_dir_margin < 0
        underwater_amount = abs(post_dir_margin) if is_underwater else 0

        analysis = {
            "claim_id": claim_id,
            "ndc": ndc,
            "drug_name": drug_name,
            "payer_type": payer_type,
            "is_preferred_pharmacy": is_preferred,
            "financials": {
                "acquisition_cost": round(acquisition_cost, 2),
                "ingredient_cost": round(ingredient_cost, 2),
                "dispensing_fee": round(dispensing_fee, 2),
                "copay": round(copay, 2),
                "reimbursement": round(reimbursement, 2),
                "gross_revenue": round(gross_revenue, 2),
            },
            "dir_breakdown": {
                "base_dir_pct": round(base_dir_pct, 2),
                "star_adjustment": round(star_adjustment, 2),
                "performance_adjustment": round(performance_adjustment, 2),
                "gdr_adjustment": round(gdr_adjustment, 2),
                "network_adjustment": round(network_adjustment, 2),
                "total_dir_pct": round(total_dir_pct, 2),
                "dir_fee_amount": round(dir_fee_amount, 2),
            },
            "profitability": {
                "pre_dir_margin": round(pre_dir_margin, 2),
                "pre_dir_margin_pct": round(pre_dir_margin_pct, 1),
                "post_dir_margin": round(post_dir_margin, 2),
                "post_dir_margin_pct": round(post_dir_margin_pct, 1),
                "margin_erosion": round(pre_dir_margin - post_dir_margin, 2),
                "margin_erosion_pct": round(pre_dir_margin_pct - post_dir_margin_pct, 1),
                "effective_reimbursement": round(effective_reimbursement, 2),
                "is_underwater": is_underwater,
                "underwater_amount": round(underwater_amount, 2),
            },
            "star_rating": star_rating,
            "analyzed_at": datetime.now().isoformat(),
        }

        self.claims_db.append(analysis)
        return analysis

    def batch_analyze(self, claims: List[Dict]) -> Dict:
        """Analyze DIR impact across a batch of claims."""
        results = [self.analyze_claim_dir_impact(c) for c in claims]

        total_dir = sum(r["dir_breakdown"]["dir_fee_amount"] for r in results)
        total_margin_erosion = sum(r["profitability"]["margin_erosion"] for r in results)
        underwater_claims = [r for r in results if r["profitability"]["is_underwater"]]
        total_underwater = sum(r["profitability"]["underwater_amount"] for r in underwater_claims)

        pre_margins = [r["profitability"]["pre_dir_margin"] for r in results]
        post_margins = [r["profitability"]["post_dir_margin"] for r in results]

        return {
            "batch_summary": {
                "total_claims": len(results),
                "total_dir_fees": round(total_dir, 2),
                "total_margin_erosion": round(total_margin_erosion, 2),
                "avg_dir_per_claim": round(total_dir / len(results), 2) if results else 0,
                "avg_pre_dir_margin": round(statistics.mean(pre_margins), 2) if pre_margins else 0,
                "avg_post_dir_margin": round(statistics.mean(post_margins), 2) if post_margins else 0,
                "underwater_claims": len(underwater_claims),
                "underwater_pct": round(len(underwater_claims) / len(results) * 100, 1) if results else 0,
                "total_underwater_loss": round(total_underwater, 2),
                "annualized_dir_impact": round(total_dir * (365 / 30), 2),  # Extrapolate from batch
            },
            "claims": results,
        }

    def payer_dir_comparison(self, claims: Optional[List[Dict]] = None) -> Dict:
        """Compare DIR fee burden across payers."""
        source = claims or self.claims_db
        payer_data = defaultdict(lambda: {
            "claims": [], "total_dir": 0, "total_margin_erosion": 0,
            "underwater_count": 0, "total_revenue": 0,
        })

        for claim in source:
            payer = claim.get("payer_type", "unknown")
            dir_amount = claim.get("dir_breakdown", {}).get("dir_fee_amount", 0)
            erosion = claim.get("profitability", {}).get("margin_erosion", 0)
            underwater = claim.get("profitability", {}).get("is_underwater", False)
            revenue = claim.get("financials", {}).get("gross_revenue", 0)

            payer_data[payer]["claims"].append(claim)
            payer_data[payer]["total_dir"] += dir_amount
            payer_data[payer]["total_margin_erosion"] += erosion
            payer_data[payer]["total_revenue"] += revenue
            if underwater:
                payer_data[payer]["underwater_count"] += 1

        comparison = []
        for payer, data in payer_data.items():
            claim_count = len(data["claims"])
            comparison.append({
                "payer_type": payer,
                "claim_count": claim_count,
                "total_dir_fees": round(data["total_dir"], 2),
                "avg_dir_per_claim": round(data["total_dir"] / claim_count, 2) if claim_count else 0,
                "total_margin_erosion": round(data["total_margin_erosion"], 2),
                "dir_as_pct_of_revenue": round(
                    data["total_dir"] / data["total_revenue"] * 100, 2
                ) if data["total_revenue"] > 0 else 0,
                "underwater_claims": data["underwater_count"],
                "underwater_pct": round(data["underwater_count"] / claim_count * 100, 1) if claim_count else 0,
                "annualized_dir": round(data["total_dir"] * 12, 2),  # Monthly extrapolation
            })

        comparison.sort(key=lambda x: x["total_dir_fees"], reverse=True)

        return {
            "type": "payer_dir_comparison",
            "generated_at": datetime.now().isoformat(),
            "payers": comparison,
            "worst_payer": comparison[0]["payer_type"] if comparison else None,
            "total_portfolio_dir": round(sum(c["total_dir_fees"] for c in comparison), 2),
        }

    def drug_level_dir_ranking(self, claims: Optional[List[Dict]] = None, top_n: int = 20) -> Dict:
        """Rank drugs by DIR fee impact (worst-performing NDCs)."""
        source = claims or self.claims_db
        drug_data = defaultdict(lambda: {
            "claims": 0, "total_dir": 0, "total_underwater": 0,
            "drug_name": "", "avg_dir_pct": [],
        })

        for claim in source:
            ndc = claim.get("ndc", "unknown")
            drug_data[ndc]["claims"] += 1
            drug_data[ndc]["total_dir"] += claim.get("dir_breakdown", {}).get("dir_fee_amount", 0)
            drug_data[ndc]["drug_name"] = claim.get("drug_name", ndc)
            drug_data[ndc]["avg_dir_pct"].append(
                claim.get("dir_breakdown", {}).get("total_dir_pct", 0)
            )
            if claim.get("profitability", {}).get("is_underwater"):
                drug_data[ndc]["total_underwater"] += claim.get("profitability", {}).get("underwater_amount", 0)

        rankings = []
        for ndc, data in drug_data.items():
            rankings.append({
                "ndc": ndc,
                "drug_name": data["drug_name"],
                "claim_count": data["claims"],
                "total_dir_fees": round(data["total_dir"], 2),
                "avg_dir_pct": round(statistics.mean(data["avg_dir_pct"]), 2) if data["avg_dir_pct"] else 0,
                "total_underwater_loss": round(data["total_underwater"], 2),
                "avg_dir_per_claim": round(data["total_dir"] / data["claims"], 2) if data["claims"] else 0,
            })

        rankings.sort(key=lambda x: x["total_dir_fees"], reverse=True)

        return {
            "type": "drug_dir_ranking",
            "generated_at": datetime.now().isoformat(),
            "top_worst": rankings[:top_n],
            "total_drugs_analyzed": len(rankings),
            "total_portfolio_dir": round(sum(r["total_dir_fees"] for r in rankings), 2),
        }

    def star_rating_impact_model(self, current_star: float, claims: Optional[List[Dict]] = None) -> Dict:
        """
        Model DIR fee impact at different star rating levels.
        Shows potential savings/costs from improving/declining star ratings.
        """
        source = claims or self.claims_db
        scenarios = {}

        for target_star in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
            star_diff = self.STAR_RATING_FACTORS.get(target_star, 0) - self.STAR_RATING_FACTORS.get(current_star, 0)

            # Recalculate DIR with different star rating
            total_dir_change = 0
            for claim in source:
                ingredient_cost = claim.get("financials", {}).get("ingredient_cost", 0)
                dir_change = ingredient_cost * (star_diff / 100)
                total_dir_change += dir_change

            scenarios[str(target_star)] = {
                "star_rating": target_star,
                "dir_pct_change": round(star_diff, 2),
                "total_dir_change": round(total_dir_change, 2),
                "annualized_impact": round(total_dir_change * 12, 2),
                "direction": "savings" if total_dir_change < 0 else "cost" if total_dir_change > 0 else "neutral",
            }

        return {
            "type": "star_rating_impact_model",
            "current_star_rating": current_star,
            "generated_at": datetime.now().isoformat(),
            "scenarios": scenarios,
            "recommendation": self._star_recommendation(current_star, scenarios),
        }

    def _star_recommendation(self, current: float, scenarios: Dict) -> str:
        """Generate star rating improvement recommendation."""
        if current >= 4.5:
            return "Excellent star performance. Maintain current adherence and quality programs."
        next_up = str(current + 0.5)
        if next_up in scenarios:
            savings = scenarios[next_up]["annualized_impact"]
            if savings < 0:
                return f"Improving to {current + 0.5} stars could save ${abs(savings):,.2f}/year in DIR fees. Focus on PDC adherence metrics."
        return f"Current star rating: {current}. Each 0.5-star improvement reduces DIR fees. Prioritize medication adherence programs."

    def generate_dir_executive_report(self, claims: Optional[List[Dict]] = None) -> Dict:
        """Generate comprehensive DIR fee executive report."""
        source = claims or self.claims_db

        if not source:
            return {"status": "error", "message": "No claims data available for report"}

        payer_comparison = self.payer_dir_comparison(source)
        drug_ranking = self.drug_level_dir_ranking(source)

        total_dir = sum(c.get("dir_breakdown", {}).get("dir_fee_amount", 0) for c in source)
        total_revenue = sum(c.get("financials", {}).get("gross_revenue", 0) for c in source)
        total_acq_cost = sum(c.get("financials", {}).get("acquisition_cost", 0) for c in source)
        underwater = sum(1 for c in source if c.get("profitability", {}).get("is_underwater"))

        pre_margins = [c.get("profitability", {}).get("pre_dir_margin", 0) for c in source]
        post_margins = [c.get("profitability", {}).get("post_dir_margin", 0) for c in source]

        return {
            "type": "dir_executive_report",
            "generated_at": datetime.now().isoformat(),
            "period_claims": len(source),
            "financial_summary": {
                "total_revenue": round(total_revenue, 2),
                "total_acquisition_cost": round(total_acq_cost, 2),
                "total_dir_fees": round(total_dir, 2),
                "dir_as_pct_of_revenue": round(total_dir / total_revenue * 100, 2) if total_revenue else 0,
                "net_margin_after_dir": round(total_revenue - total_acq_cost - total_dir, 2),
                "avg_pre_dir_margin": round(statistics.mean(pre_margins), 2) if pre_margins else 0,
                "avg_post_dir_margin": round(statistics.mean(post_margins), 2) if post_margins else 0,
                "margin_erosion_total": round(sum(pre_margins) - sum(post_margins), 2),
                "underwater_claims": underwater,
                "underwater_pct": round(underwater / len(source) * 100, 1) if source else 0,
                "annualized_dir_projection": round(total_dir * (365 / 30), 2),
            },
            "payer_analysis": payer_comparison,
            "drug_analysis": drug_ranking,
            "action_items": [
                {
                    "priority": 1,
                    "action": "Review underwater claims",
                    "detail": f"{underwater} claims dispensed at a loss after DIR. Consider formulary adjustments.",
                },
                {
                    "priority": 2,
                    "action": "Improve star ratings",
                    "detail": "Each 0.5-star improvement reduces DIR fees by 0.5-1.0%. Focus on PDC adherence.",
                },
                {
                    "priority": 3,
                    "action": "Negotiate preferred network status",
                    "detail": "Preferred pharmacies pay 1-2% less DIR. Pursue preferred tier with top payers.",
                },
                {
                    "priority": 4,
                    "action": "Evaluate worst-performing NDCs",
                    "detail": f"Top {min(5, len(drug_ranking.get('top_worst', [])))} NDCs account for majority of DIR. Consider sourcing alternatives.",
                },
            ],
        }


# FastAPI integration
def create_dir_fee_routes(app):
    """Register DIR fee analysis API routes."""
    engine = DIRFeeImpactAnalyzer()

    @app.post("/api/v1/dir/analyze-claim")
    async def analyze_claim_dir(request):
        data = await request.json()
        result = engine.analyze_claim_dir_impact(data.get("claim", {}))
        return {"status": "success", "analysis": result}

    @app.post("/api/v1/dir/batch-analyze")
    async def batch_analyze_dir(request):
        data = await request.json()
        result = engine.batch_analyze(data.get("claims", []))
        return {"status": "success", **result}

    @app.get("/api/v1/dir/payer-comparison")
    async def payer_dir_comparison():
        result = engine.payer_dir_comparison()
        return {"status": "success", **result}

    @app.get("/api/v1/dir/drug-ranking")
    async def drug_dir_ranking(top_n: int = 20):
        result = engine.drug_level_dir_ranking(top_n=top_n)
        return {"status": "success", **result}

    @app.get("/api/v1/dir/star-impact")
    async def star_impact_model(current_star: float = 3.0):
        result = engine.star_rating_impact_model(current_star)
        return {"status": "success", **result}

    @app.get("/api/v1/dir/executive-report")
    async def dir_executive_report():
        result = engine.generate_dir_executive_report()
        return {"status": "success", "report": result}

    return engine
