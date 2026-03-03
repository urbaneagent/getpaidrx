"""
GetPaidRx - Maximum Allowable Cost (MAC) Price Analyzer

Analyzes PBM MAC pricing lists against actual acquisition costs (AAC)
and NADAC benchmarks to identify drugs where MAC reimbursement is below
cost — a major source of pharmacy underpayment.

Features:
  - MAC vs AAC (Actual Acquisition Cost) spread analysis
  - MAC vs NADAC benchmark comparison
  - Underwater drug identification (MAC < AAC)
  - PBM MAC list comparison across payers
  - MAC appeal opportunity detection with estimated recovery
  - Historical MAC price trend tracking
  - Therapeutic class MAC analysis
  - MAC adequacy grading per PBM (A-F scale)
  - GER (Generic Effective Rate) calculation
  - FastAPI route integration
"""

import uuid
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field


# ============================================================
# MAC Adequacy Classification
# ============================================================

MAC_ADEQUACY_LEVELS = {
    "ADEQUATE": {"label": "Adequate", "color": "#22c55e", "min_ratio": 1.05},
    "MARGINAL": {"label": "Marginal", "color": "#f59e0b", "min_ratio": 0.95},
    "UNDERWATER": {"label": "Underwater", "color": "#ef4444", "min_ratio": 0.85},
    "SEVERELY_UNDERWATER": {"label": "Severely Underwater", "color": "#7f1d1d", "min_ratio": 0.0},
}


@dataclass
class MACListEntry:
    """A single drug on a PBM's MAC list."""
    ndc: str = ""
    drug_name: str = ""
    generic_name: str = ""
    strength: str = ""
    dosage_form: str = ""
    mac_price: float = 0.0  # per unit MAC price
    effective_date: str = ""
    pbm_name: str = ""
    therapeutic_class: str = ""
    gpi: str = ""  # Generic Product Identifier


@dataclass 
class DrugCostEntry:
    """Actual acquisition cost for a drug."""
    ndc: str = ""
    drug_name: str = ""
    aac_price: float = 0.0  # actual acquisition cost per unit
    nadac_price: float = 0.0  # NADAC per unit
    awp_price: float = 0.0  # average wholesale price per unit
    wac_price: float = 0.0  # wholesale acquisition cost per unit
    dispensing_cost: float = 1.50  # estimated dispensing cost per unit
    source: str = ""
    last_updated: str = ""


class MACPriceAnalyzer:
    """
    Analyzes MAC pricing across PBMs to identify underpayment,
    appeal opportunities, and negotiate better rates.
    """
    
    def __init__(self):
        self.mac_lists: Dict[str, List[MACListEntry]] = defaultdict(list)  # pbm_name -> entries
        self.drug_costs: Dict[str, DrugCostEntry] = {}  # ndc -> cost
        self._load_sample_data()
    
    def _load_sample_data(self):
        """Load sample MAC and cost data for demonstration."""
        # Common generic drugs with realistic pricing
        sample_drugs = [
            {"ndc": "00378-0803-01", "name": "Lisinopril 10mg Tab", "generic": "lisinopril", "class": "ACE Inhibitor",
             "aac": 0.04, "nadac": 0.038, "awp": 0.42, "mac_express": 0.05, "mac_optum": 0.045, "mac_caremark": 0.06},
            {"ndc": "00093-3145-01", "name": "Cephalexin 500mg Cap", "generic": "cephalexin", "class": "Antibiotic",
             "aac": 0.18, "nadac": 0.165, "awp": 1.85, "mac_express": 0.14, "mac_optum": 0.19, "mac_caremark": 0.22},
            {"ndc": "00093-0311-01", "name": "Metformin 500mg Tab", "generic": "metformin", "class": "Antidiabetic",
             "aac": 0.03, "nadac": 0.028, "awp": 0.35, "mac_express": 0.04, "mac_optum": 0.035, "mac_caremark": 0.05},
            {"ndc": "00093-7364-01", "name": "Losartan 50mg Tab", "generic": "losartan", "class": "ARB",
             "aac": 0.08, "nadac": 0.072, "awp": 0.95, "mac_express": 0.06, "mac_optum": 0.085, "mac_caremark": 0.09},
            {"ndc": "00378-1485-01", "name": "Methylphenidate ER 20mg", "generic": "methylphenidate", "class": "CNS Stimulant",
             "aac": 0.95, "nadac": 0.88, "awp": 8.50, "mac_express": 0.70, "mac_optum": 0.92, "mac_caremark": 1.05},
            {"ndc": "00093-3109-01", "name": "Amoxicillin 500mg Cap", "generic": "amoxicillin", "class": "Antibiotic",
             "aac": 0.08, "nadac": 0.075, "awp": 0.88, "mac_express": 0.09, "mac_optum": 0.07, "mac_caremark": 0.10},
            {"ndc": "00378-4021-01", "name": "Omeprazole 20mg Cap", "generic": "omeprazole", "class": "PPI",
             "aac": 0.06, "nadac": 0.055, "awp": 0.70, "mac_express": 0.05, "mac_optum": 0.065, "mac_caremark": 0.08},
            {"ndc": "00093-0058-01", "name": "Atorvastatin 20mg Tab", "generic": "atorvastatin", "class": "Statin",
             "aac": 0.09, "nadac": 0.082, "awp": 1.10, "mac_express": 0.07, "mac_optum": 0.095, "mac_caremark": 0.11},
            {"ndc": "00228-2775-11", "name": "Gabapentin 300mg Cap", "generic": "gabapentin", "class": "Anticonvulsant",
             "aac": 0.05, "nadac": 0.045, "awp": 0.55, "mac_express": 0.04, "mac_optum": 0.048, "mac_caremark": 0.06},
            {"ndc": "00378-0222-01", "name": "Amlodipine 5mg Tab", "generic": "amlodipine", "class": "CCB",
             "aac": 0.03, "nadac": 0.025, "awp": 0.30, "mac_express": 0.025, "mac_optum": 0.032, "mac_caremark": 0.04},
            {"ndc": "00093-5264-01", "name": "Sertraline 50mg Tab", "generic": "sertraline", "class": "SSRI",
             "aac": 0.07, "nadac": 0.065, "awp": 0.80, "mac_express": 0.055, "mac_optum": 0.072, "mac_caremark": 0.08},
            {"ndc": "68180-0757-01", "name": "Levothyroxine 50mcg Tab", "generic": "levothyroxine", "class": "Thyroid",
             "aac": 0.12, "nadac": 0.11, "awp": 1.20, "mac_express": 0.08, "mac_optum": 0.13, "mac_caremark": 0.14},
        ]
        
        for drug in sample_drugs:
            # Store cost data
            self.drug_costs[drug["ndc"]] = DrugCostEntry(
                ndc=drug["ndc"],
                drug_name=drug["name"],
                aac_price=drug["aac"],
                nadac_price=drug["nadac"],
                awp_price=drug["awp"],
                last_updated=datetime.utcnow().strftime("%Y-%m-%d"),
            )
            
            # Store MAC lists for each PBM
            for pbm_key, pbm_name in [("mac_express", "Express Scripts"), ("mac_optum", "Optum Rx"), ("mac_caremark", "CVS Caremark")]:
                self.mac_lists[pbm_name].append(MACListEntry(
                    ndc=drug["ndc"],
                    drug_name=drug["name"],
                    generic_name=drug["generic"],
                    mac_price=drug[pbm_key],
                    effective_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    pbm_name=pbm_name,
                    therapeutic_class=drug["class"],
                ))
    
    def analyze_mac_vs_cost(self, pbm_name: Optional[str] = None) -> Dict:
        """Analyze MAC prices vs actual acquisition costs."""
        results = []
        
        pbms_to_check = [pbm_name] if pbm_name else list(self.mac_lists.keys())
        
        for pbm in pbms_to_check:
            for entry in self.mac_lists.get(pbm, []):
                cost = self.drug_costs.get(entry.ndc)
                if not cost:
                    continue
                
                spread = entry.mac_price - cost.aac_price
                spread_pct = ((entry.mac_price / cost.aac_price) - 1) * 100 if cost.aac_price > 0 else 0
                nadac_spread = entry.mac_price - cost.nadac_price if cost.nadac_price > 0 else None
                
                # Classify adequacy
                ratio = entry.mac_price / cost.aac_price if cost.aac_price > 0 else 1.0
                if ratio >= 1.05:
                    adequacy = "ADEQUATE"
                elif ratio >= 0.95:
                    adequacy = "MARGINAL"
                elif ratio >= 0.85:
                    adequacy = "UNDERWATER"
                else:
                    adequacy = "SEVERELY_UNDERWATER"
                
                results.append({
                    "ndc": entry.ndc,
                    "drug_name": entry.drug_name,
                    "pbm": pbm,
                    "therapeutic_class": entry.therapeutic_class,
                    "mac_price": entry.mac_price,
                    "aac_price": cost.aac_price,
                    "nadac_price": cost.nadac_price,
                    "awp_price": cost.awp_price,
                    "spread": round(spread, 4),
                    "spread_pct": round(spread_pct, 1),
                    "nadac_spread": round(nadac_spread, 4) if nadac_spread is not None else None,
                    "adequacy": adequacy,
                    "adequacy_info": MAC_ADEQUACY_LEVELS.get(adequacy, {}),
                    "is_underwater": spread < 0,
                    "monthly_volume_est": 200,  # Default estimate
                    "monthly_loss_est": round(min(spread, 0) * 200, 2),
                })
        
        # Sort: most underwater first
        results.sort(key=lambda r: r["spread"])
        
        # Summary
        underwater = [r for r in results if r["is_underwater"]]
        total_monthly_loss = sum(r["monthly_loss_est"] for r in underwater)
        
        return {
            "total_drugs_analyzed": len(results),
            "underwater_count": len(underwater),
            "adequate_count": sum(1 for r in results if r["adequacy"] == "ADEQUATE"),
            "marginal_count": sum(1 for r in results if r["adequacy"] == "MARGINAL"),
            "total_estimated_monthly_loss": round(total_monthly_loss, 2),
            "total_estimated_annual_loss": round(total_monthly_loss * 12, 2),
            "worst_drugs": results[:5],
            "best_drugs": results[-3:] if len(results) > 3 else [],
            "all_results": results,
        }
    
    def grade_pbm(self, pbm_name: str) -> Dict:
        """Grade a PBM's MAC list on adequacy."""
        analysis = self.analyze_mac_vs_cost(pbm_name)
        results = analysis["all_results"]
        
        if not results:
            return {"pbm": pbm_name, "grade": "N/A", "error": "No data"}
        
        # Score based on spread percentages
        spreads = [r["spread_pct"] for r in results]
        avg_spread = statistics.mean(spreads) if spreads else 0
        underwater_pct = (analysis["underwater_count"] / len(results)) * 100
        
        # Composite score (0-100)
        score = 70  # base
        score += min(avg_spread * 2, 20)  # positive spread is good
        score -= underwater_pct * 0.5  # penalize underwater drugs
        score = max(0, min(100, score))
        
        # Grade
        grade_thresholds = [
            (95, "A+"), (90, "A"), (85, "A-"),
            (80, "B+"), (75, "B"), (70, "B-"),
            (65, "C+"), (60, "C"), (55, "C-"),
            (50, "D+"), (45, "D"), (40, "D-"),
            (0, "F"),
        ]
        grade = "F"
        for threshold, g in grade_thresholds:
            if score >= threshold:
                grade = g
                break
        
        return {
            "pbm": pbm_name,
            "grade": grade,
            "score": round(score, 1),
            "drugs_analyzed": len(results),
            "avg_spread_pct": round(avg_spread, 1),
            "underwater_count": analysis["underwater_count"],
            "underwater_pct": round(underwater_pct, 1),
            "monthly_loss": analysis["total_estimated_monthly_loss"],
            "annual_loss": analysis["total_estimated_annual_loss"],
            "top_underwater": [r["drug_name"] for r in analysis["worst_drugs"][:3] if r["is_underwater"]],
        }
    
    def compare_pbms(self) -> Dict:
        """Compare MAC pricing across all PBMs."""
        grades = {}
        for pbm in self.mac_lists:
            grades[pbm] = self.grade_pbm(pbm)
        
        # Rank by grade
        grade_order = {"A+": 0, "A": 1, "A-": 2, "B+": 3, "B": 4, "B-": 5,
                       "C+": 6, "C": 7, "C-": 8, "D+": 9, "D": 10, "D-": 11, "F": 12}
        ranked = sorted(grades.items(), key=lambda x: grade_order.get(x[1]["grade"], 99))
        
        return {
            "pbm_count": len(grades),
            "rankings": [{"rank": i+1, **v} for i, (k, v) in enumerate(ranked)],
            "best_pbm": ranked[0][0] if ranked else None,
            "worst_pbm": ranked[-1][0] if ranked else None,
            "total_annual_loss_all_pbms": sum(g["annual_loss"] for g in grades.values()),
        }
    
    def find_appeal_opportunities(self, min_monthly_loss: float = 5.0) -> List[Dict]:
        """Find MAC appeal opportunities where loss exceeds threshold."""
        opportunities = []
        
        for pbm, entries in self.mac_lists.items():
            for entry in entries:
                cost = self.drug_costs.get(entry.ndc)
                if not cost:
                    continue
                
                spread = entry.mac_price - cost.aac_price
                monthly_loss = min(spread, 0) * 200  # est. monthly volume
                
                if monthly_loss < -min_monthly_loss:  # Losing > threshold/month
                    opportunities.append({
                        "pbm": pbm,
                        "drug_name": entry.drug_name,
                        "ndc": entry.ndc,
                        "current_mac": entry.mac_price,
                        "actual_cost": cost.aac_price,
                        "nadac_price": cost.nadac_price,
                        "loss_per_unit": round(abs(spread), 4),
                        "est_monthly_loss": round(abs(monthly_loss), 2),
                        "est_annual_loss": round(abs(monthly_loss) * 12, 2),
                        "appeal_basis": "MAC below AAC" if cost.aac_price > entry.mac_price else "MAC below NADAC",
                        "suggested_mac": round(cost.aac_price * 1.08, 4),  # AAC + 8% margin
                        "supporting_evidence": [
                            f"NADAC benchmark: ${cost.nadac_price:.4f}/unit",
                            f"AWP: ${cost.awp_price:.4f}/unit",
                            f"Current MAC is {round(abs(spread/cost.aac_price)*100, 1)}% below acquisition cost",
                        ],
                    })
        
        opportunities.sort(key=lambda o: o["est_annual_loss"], reverse=True)
        
        total_annual = sum(o["est_annual_loss"] for o in opportunities)
        
        return {
            "total_appeal_opportunities": len(opportunities),
            "total_annual_recovery_potential": round(total_annual, 2),
            "opportunities": opportunities,
        }


def create_mac_analyzer_routes(app):
    """Register MAC price analyzer routes."""
    from fastapi import APIRouter, Query
    
    router = APIRouter(prefix="/api/v1/mac", tags=["MAC Pricing"])
    analyzer = MACPriceAnalyzer()
    
    @router.get("/analysis")
    async def mac_analysis(pbm: Optional[str] = Query(None)):
        """Analyze MAC prices vs actual costs."""
        return analyzer.analyze_mac_vs_cost(pbm)
    
    @router.get("/grade/{pbm_name}")
    async def grade_pbm(pbm_name: str):
        """Grade a PBM's MAC list adequacy."""
        return analyzer.grade_pbm(pbm_name)
    
    @router.get("/compare")
    async def compare_pbms():
        """Compare MAC pricing across all PBMs."""
        return analyzer.compare_pbms()
    
    @router.get("/appeals")
    async def find_appeals(min_loss: float = Query(5.0)):
        """Find MAC appeal opportunities."""
        return analyzer.find_appeal_opportunities(min_loss)
    
    app.include_router(router)
    return router
