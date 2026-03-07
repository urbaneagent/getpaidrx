"""
GetPaidRx — DIR Fee Impact Forecaster
Forecasts and analyzes Direct and Indirect Remuneration (DIR) fees
under the 2026 CMS regulatory changes including point-of-sale (POS)
transparency requirements.

Features:
  - DIR fee projection based on historical data and CMS 2026 rules
  - Point-of-sale vs retrospective DIR comparison
  - Pharmacy profitability impact modeling per drug/payer
  - GER (Generic Effective Rate) analysis with DIR adjustments
  - Star rating correlation to DIR fee exposure
  - Network-level DIR fee aggregation
  - CMS regulatory change impact scoring
  - Monthly/quarterly DIR fee reporting with trend analysis
"""

import json
import uuid
import math
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class DIRCategory(str, Enum):
    PERFORMANCE = "performance"          # Quality metric-based
    PRICE_CONCESSION = "price_concession"  # Post-POS price adjustments
    NETWORK_FEE = "network_fee"          # Pharmacy network access fee
    ADMIN_FEE = "admin_fee"              # PBM administrative fee
    CLAWBACK = "clawback"               # Retroactive payment reduction
    BRAND_REBATE = "brand_rebate"        # Brand drug rebate pass-through


class FeeStructure(str, Enum):
    FLAT_PER_CLAIM = "flat_per_claim"
    PERCENTAGE_OF_INGREDIENT = "percentage_of_ingredient"
    PERCENTAGE_OF_REIMBURSEMENT = "percentage_of_reimbursement"
    TIERED_VOLUME = "tiered_volume"
    STAR_RATING_BASED = "star_rating_based"


class ImpactLevel(str, Enum):
    CRITICAL = "critical"  # >15% margin impact
    HIGH = "high"          # 10-15% margin impact
    MODERATE = "moderate"  # 5-10% margin impact
    LOW = "low"            # <5% margin impact


class RegulationPhase(str, Enum):
    PRE_2024 = "pre_2024"         # Old rules (fully retrospective)
    TRANSITION_2024 = "transition_2024"  # CMS transition period
    POS_2026 = "pos_2026"         # Full POS DIR transparency
    PROJECTED = "projected"       # Future projection


# CMS 2026 DIR reform parameters
CMS_2026_POS_MAX_PCT = 0.05   # Max 5% of negotiated price at POS
PERFORMANCE_WITHHOLD_MAX = 0.03  # Max 3% performance withhold
CLAWBACK_PROHIBITED = True      # Retrospective clawbacks prohibited under 2026 rules
STAR_RATING_THRESHOLD = 3.5     # Below this = higher DIR exposure

# Average margins by drug type (used for impact calculation)
MARGIN_BENCHMARKS = {
    "brand": 0.02,      # 2% average brand margin
    "generic": 0.45,    # 45% average generic margin
    "specialty": 0.03,  # 3% average specialty margin
}


# ============================================================
# Data Classes
# ============================================================

@dataclass
class DIRFeeSchedule:
    """A DIR fee schedule from a PBM/payer."""
    schedule_id: str
    payer_id: str
    payer_name: str
    pbm_name: str
    effective_date: str
    expiration_date: str
    category: DIRCategory
    fee_structure: FeeStructure
    flat_fee: Optional[float]       # For flat_per_claim
    percentage: Optional[float]     # For percentage-based
    tiers: Optional[List[Dict[str, Any]]]  # For tiered_volume
    star_rating_adjustments: Optional[Dict[str, float]]  # Rating -> adjustment
    applies_to_brand: bool
    applies_to_generic: bool
    applies_to_specialty: bool

    def calculate_fee(
        self,
        ingredient_cost: float,
        reimbursement: float,
        claim_count: int = 1,
        star_rating: float = 4.0,
    ) -> float:
        """Calculate the DIR fee for a given claim."""
        if self.fee_structure == FeeStructure.FLAT_PER_CLAIM:
            return (self.flat_fee or 0) * claim_count

        elif self.fee_structure == FeeStructure.PERCENTAGE_OF_INGREDIENT:
            return ingredient_cost * (self.percentage or 0)

        elif self.fee_structure == FeeStructure.PERCENTAGE_OF_REIMBURSEMENT:
            return reimbursement * (self.percentage or 0)

        elif self.fee_structure == FeeStructure.STAR_RATING_BASED:
            if self.star_rating_adjustments:
                # Find the applicable tier based on star rating
                for threshold, adj in sorted(self.star_rating_adjustments.items()):
                    if star_rating <= float(threshold):
                        return reimbursement * adj
            return reimbursement * (self.percentage or 0)

        elif self.fee_structure == FeeStructure.TIERED_VOLUME:
            if self.tiers:
                for tier in self.tiers:
                    if claim_count <= tier.get("max_claims", float("inf")):
                        return reimbursement * tier.get("percentage", 0)
            return reimbursement * (self.percentage or 0)

        return 0.0


@dataclass
class PharmacyProfile:
    """A pharmacy's profile for DIR fee analysis."""
    pharmacy_id: str
    pharmacy_name: str
    npi: str
    star_rating: float
    claim_volume_monthly: int
    brand_pct: float
    generic_pct: float
    specialty_pct: float
    avg_brand_reimbursement: float
    avg_generic_reimbursement: float
    avg_specialty_reimbursement: float
    avg_brand_cost: float
    avg_generic_cost: float
    avg_specialty_cost: float
    network_memberships: List[str]


@dataclass
class DIRProjection:
    """Projected DIR fee impact for a pharmacy."""
    projection_id: str
    pharmacy_id: str
    pharmacy_name: str
    period: str  # e.g., "2026-Q1"
    regulation_phase: RegulationPhase
    total_claims: int
    total_dir_fees: float
    dir_per_claim: float
    dir_as_pct_revenue: float
    margin_before_dir: float
    margin_after_dir: float
    margin_impact_pct: float
    impact_level: ImpactLevel
    by_category: Dict[str, float]
    by_drug_type: Dict[str, float]
    pos_vs_retro_savings: float  # Savings from POS vs retrospective
    recommendations: List[str]


@dataclass
class GERAnalysis:
    """Generic Effective Rate analysis with DIR adjustments."""
    drug_name: str
    ndc: str
    claims_analyzed: int
    gross_ger: float           # GER before DIR
    net_ger: float             # GER after DIR deductions
    dir_impact_per_unit: float
    underwater_after_dir: bool
    cost_per_unit: float
    reimbursement_per_unit: float
    dir_per_unit: float
    effective_margin: float


# ============================================================
# DIR Fee Forecaster Engine
# ============================================================

class DIRFeeForecaster:
    """
    Forecasts DIR fee impact on pharmacy profitability under
    CMS 2026 regulations and provides optimization recommendations.
    """

    def __init__(self, regulation_phase: RegulationPhase = RegulationPhase.POS_2026):
        self.regulation_phase = regulation_phase
        self.fee_schedules: List[DIRFeeSchedule] = []
        self.pharmacies: Dict[str, PharmacyProfile] = {}
        self.projections: List[DIRProjection] = []
        self.historical_dir: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def add_fee_schedule(
        self,
        payer_id: str,
        payer_name: str,
        pbm_name: str,
        category: DIRCategory,
        fee_structure: FeeStructure,
        flat_fee: Optional[float] = None,
        percentage: Optional[float] = None,
        tiers: Optional[List[Dict[str, Any]]] = None,
        star_adjustments: Optional[Dict[str, float]] = None,
        applies_brand: bool = True,
        applies_generic: bool = True,
        applies_specialty: bool = True,
        effective_date: Optional[str] = None,
        expiration_date: Optional[str] = None,
    ) -> DIRFeeSchedule:
        """Add a DIR fee schedule."""
        now = datetime.utcnow()
        schedule = DIRFeeSchedule(
            schedule_id=str(uuid.uuid4()),
            payer_id=payer_id,
            payer_name=payer_name,
            pbm_name=pbm_name,
            effective_date=effective_date or now.isoformat() + "Z",
            expiration_date=expiration_date or (now + timedelta(days=365)).isoformat() + "Z",
            category=category,
            fee_structure=fee_structure,
            flat_fee=flat_fee,
            percentage=percentage,
            tiers=tiers,
            star_rating_adjustments=star_adjustments,
            applies_to_brand=applies_brand,
            applies_to_generic=applies_generic,
            applies_to_specialty=applies_specialty,
        )
        self.fee_schedules.append(schedule)
        return schedule

    def register_pharmacy(
        self,
        pharmacy_name: str,
        npi: str,
        star_rating: float,
        claim_volume_monthly: int,
        brand_pct: float = 0.25,
        generic_pct: float = 0.70,
        specialty_pct: float = 0.05,
        avg_brand_reimb: float = 250.0,
        avg_generic_reimb: float = 15.0,
        avg_specialty_reimb: float = 3500.0,
        avg_brand_cost: float = 245.0,
        avg_generic_cost: float = 5.0,
        avg_specialty_cost: float = 3400.0,
        networks: Optional[List[str]] = None,
    ) -> PharmacyProfile:
        """Register a pharmacy for DIR analysis."""
        pharmacy_id = str(uuid.uuid4())
        profile = PharmacyProfile(
            pharmacy_id=pharmacy_id,
            pharmacy_name=pharmacy_name,
            npi=npi,
            star_rating=star_rating,
            claim_volume_monthly=claim_volume_monthly,
            brand_pct=brand_pct,
            generic_pct=generic_pct,
            specialty_pct=specialty_pct,
            avg_brand_reimbursement=avg_brand_reimb,
            avg_generic_reimbursement=avg_generic_reimb,
            avg_specialty_reimbursement=avg_specialty_reimb,
            avg_brand_cost=avg_brand_cost,
            avg_generic_cost=avg_generic_cost,
            avg_specialty_cost=avg_specialty_cost,
            network_memberships=networks or [],
        )
        self.pharmacies[pharmacy_id] = profile
        return profile

    def project_dir_impact(
        self, pharmacy_id: str, months: int = 3,
    ) -> DIRProjection:
        """Project DIR fee impact for a pharmacy over a period."""
        pharmacy = self.pharmacies.get(pharmacy_id)
        if not pharmacy:
            raise ValueError(f"Pharmacy {pharmacy_id} not found")

        total_claims = pharmacy.claim_volume_monthly * months
        brand_claims = int(total_claims * pharmacy.brand_pct)
        generic_claims = int(total_claims * pharmacy.generic_pct)
        specialty_claims = int(total_claims * pharmacy.specialty_pct)

        # Calculate revenue
        brand_revenue = brand_claims * pharmacy.avg_brand_reimbursement
        generic_revenue = generic_claims * pharmacy.avg_generic_reimbursement
        specialty_revenue = specialty_claims * pharmacy.avg_specialty_reimbursement
        total_revenue = brand_revenue + generic_revenue + specialty_revenue

        # Calculate cost
        brand_cost = brand_claims * pharmacy.avg_brand_cost
        generic_cost = generic_claims * pharmacy.avg_generic_cost
        specialty_cost = specialty_claims * pharmacy.avg_specialty_cost
        total_cost = brand_cost + generic_cost + specialty_cost

        # Calculate DIR fees by category
        by_category = defaultdict(float)
        by_drug_type = {"brand": 0.0, "generic": 0.0, "specialty": 0.0}

        for schedule in self.fee_schedules:
            # Brand DIR
            if schedule.applies_to_brand and brand_claims > 0:
                fee = schedule.calculate_fee(
                    pharmacy.avg_brand_cost * brand_claims,
                    brand_revenue,
                    brand_claims,
                    pharmacy.star_rating,
                )
                by_category[schedule.category.value] += fee
                by_drug_type["brand"] += fee

            # Generic DIR
            if schedule.applies_to_generic and generic_claims > 0:
                fee = schedule.calculate_fee(
                    pharmacy.avg_generic_cost * generic_claims,
                    generic_revenue,
                    generic_claims,
                    pharmacy.star_rating,
                )
                by_category[schedule.category.value] += fee
                by_drug_type["generic"] += fee

            # Specialty DIR
            if schedule.applies_to_specialty and specialty_claims > 0:
                fee = schedule.calculate_fee(
                    pharmacy.avg_specialty_cost * specialty_claims,
                    specialty_revenue,
                    specialty_claims,
                    pharmacy.star_rating,
                )
                by_category[schedule.category.value] += fee
                by_drug_type["specialty"] += fee

        # Apply CMS 2026 caps
        if self.regulation_phase == RegulationPhase.POS_2026:
            max_pos_dir = total_revenue * CMS_2026_POS_MAX_PCT
            total_dir = sum(by_category.values())
            if total_dir > max_pos_dir:
                # Scale down proportionally
                scale = max_pos_dir / total_dir
                by_category = {k: v * scale for k, v in by_category.items()}
                by_drug_type = {k: v * scale for k, v in by_drug_type.items()}

            # Remove prohibited clawbacks
            if CLAWBACK_PROHIBITED:
                by_category.pop("clawback", None)

        total_dir = sum(by_category.values())

        # Margins
        margin_before = total_revenue - total_cost
        margin_after = margin_before - total_dir
        margin_impact = ((margin_before - margin_after) / margin_before * 100) if margin_before > 0 else 0

        # Impact level
        if margin_impact > 15:
            impact = ImpactLevel.CRITICAL
        elif margin_impact > 10:
            impact = ImpactLevel.HIGH
        elif margin_impact > 5:
            impact = ImpactLevel.MODERATE
        else:
            impact = ImpactLevel.LOW

        # POS vs retrospective savings estimate
        retro_dir = total_dir * 1.15  # Retrospective typically 15% higher
        pos_savings = retro_dir - total_dir

        # Recommendations
        recommendations = []
        if pharmacy.star_rating < STAR_RATING_THRESHOLD:
            recommendations.append(
                f"⚠️ Star rating ({pharmacy.star_rating}) below {STAR_RATING_THRESHOLD}. "
                "Improving star rating would reduce performance-based DIR fees by ~20%."
            )
        if by_drug_type.get("generic", 0) > total_dir * 0.5:
            recommendations.append(
                "Generic DIR fees account for >50% of total DIR. Consider "
                "negotiating better GER terms or switching to lower-DIR networks."
            )
        if margin_after < 0:
            recommendations.append(
                "🚨 CRITICAL: Pharmacy is projected to operate at a LOSS after DIR fees. "
                "Immediate contract renegotiation required."
            )
        if impact == ImpactLevel.LOW:
            recommendations.append(
                "DIR impact is manageable. Continue monitoring and optimize "
                "star ratings for additional savings."
            )

        period = f"{datetime.utcnow().strftime('%Y')}-Q{((datetime.utcnow().month - 1) // 3) + 1}"

        projection = DIRProjection(
            projection_id=str(uuid.uuid4()),
            pharmacy_id=pharmacy_id,
            pharmacy_name=pharmacy.pharmacy_name,
            period=period,
            regulation_phase=self.regulation_phase,
            total_claims=total_claims,
            total_dir_fees=round(total_dir, 2),
            dir_per_claim=round(total_dir / total_claims, 2) if total_claims else 0,
            dir_as_pct_revenue=round(total_dir / total_revenue * 100, 2) if total_revenue else 0,
            margin_before_dir=round(margin_before, 2),
            margin_after_dir=round(margin_after, 2),
            margin_impact_pct=round(margin_impact, 1),
            impact_level=impact,
            by_category={k: round(v, 2) for k, v in by_category.items()},
            by_drug_type={k: round(v, 2) for k, v in by_drug_type.items()},
            pos_vs_retro_savings=round(pos_savings, 2),
            recommendations=recommendations,
        )

        self.projections.append(projection)
        return projection

    def analyze_ger(
        self,
        drug_name: str,
        ndc: str,
        cost_per_unit: float,
        reimbursement_per_unit: float,
        claims: int,
    ) -> GERAnalysis:
        """Analyze Generic Effective Rate with DIR fee adjustments."""
        # Calculate gross GER
        gross_ger = ((reimbursement_per_unit - cost_per_unit) / reimbursement_per_unit * 100
                     if reimbursement_per_unit > 0 else 0)

        # Estimate DIR per unit (average across all schedules for generics)
        total_dir = 0.0
        for schedule in self.fee_schedules:
            if schedule.applies_to_generic:
                fee = schedule.calculate_fee(
                    cost_per_unit * claims,
                    reimbursement_per_unit * claims,
                    claims,
                    4.0,  # assume average star rating
                )
                total_dir += fee

        dir_per_unit = total_dir / claims if claims > 0 else 0
        net_reimbursement = reimbursement_per_unit - dir_per_unit
        net_ger = ((net_reimbursement - cost_per_unit) / reimbursement_per_unit * 100
                   if reimbursement_per_unit > 0 else 0)
        effective_margin = net_reimbursement - cost_per_unit

        return GERAnalysis(
            drug_name=drug_name,
            ndc=ndc,
            claims_analyzed=claims,
            gross_ger=round(gross_ger, 2),
            net_ger=round(net_ger, 2),
            dir_impact_per_unit=round(dir_per_unit, 4),
            underwater_after_dir=effective_margin < 0,
            cost_per_unit=cost_per_unit,
            reimbursement_per_unit=reimbursement_per_unit,
            dir_per_unit=round(dir_per_unit, 4),
            effective_margin=round(effective_margin, 4),
        )

    def compare_regulation_phases(
        self, pharmacy_id: str
    ) -> Dict[str, Any]:
        """Compare DIR impact across regulation phases."""
        results = {}
        original_phase = self.regulation_phase

        for phase in [RegulationPhase.PRE_2024, RegulationPhase.POS_2026]:
            self.regulation_phase = phase
            projection = self.project_dir_impact(pharmacy_id, months=3)
            results[phase.value] = {
                "total_dir": projection.total_dir_fees,
                "dir_per_claim": projection.dir_per_claim,
                "margin_after_dir": projection.margin_after_dir,
                "impact_level": projection.impact_level.value,
            }

        self.regulation_phase = original_phase

        # Calculate savings from new rules
        pre_dir = results.get("pre_2024", {}).get("total_dir", 0)
        pos_dir = results.get("pos_2026", {}).get("total_dir", 0)
        savings = pre_dir - pos_dir

        results["regulatory_savings"] = round(savings, 2)
        results["savings_pct"] = round(savings / pre_dir * 100, 1) if pre_dir > 0 else 0

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall DIR forecaster statistics."""
        return {
            "registered_pharmacies": len(self.pharmacies),
            "fee_schedules": len(self.fee_schedules),
            "projections_generated": len(self.projections),
            "regulation_phase": self.regulation_phase.value,
            "avg_dir_per_claim": round(
                statistics.mean([p.dir_per_claim for p in self.projections]), 2
            ) if self.projections else None,
            "pharmacies_at_risk": sum(
                1 for p in self.projections
                if p.impact_level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH)
            ),
        }


if __name__ == "__main__":
    forecaster = DIRFeeForecaster()

    # Add DIR fee schedules
    forecaster.add_fee_schedule(
        payer_id="EXPRESS_SCRIPTS",
        payer_name="Express Scripts",
        pbm_name="Express Scripts",
        category=DIRCategory.PERFORMANCE,
        fee_structure=FeeStructure.STAR_RATING_BASED,
        percentage=0.03,
        star_adjustments={"3.0": 0.05, "3.5": 0.03, "4.0": 0.02, "5.0": 0.01},
    )

    forecaster.add_fee_schedule(
        payer_id="CVS_CAREMARK",
        payer_name="CVS Caremark",
        pbm_name="CVS Caremark",
        category=DIRCategory.NETWORK_FEE,
        fee_structure=FeeStructure.FLAT_PER_CLAIM,
        flat_fee=1.50,
    )

    # Register pharmacy
    pharmacy = forecaster.register_pharmacy(
        pharmacy_name="Community Pharmacy #1",
        npi="1234567890",
        star_rating=3.8,
        claim_volume_monthly=5000,
        brand_pct=0.20,
        generic_pct=0.75,
        specialty_pct=0.05,
    )

    # Project impact
    projection = forecaster.project_dir_impact(pharmacy.pharmacy_id)
    print(f"DIR Projection for {projection.pharmacy_name}:")
    print(f"  Total DIR Fees: ${projection.total_dir_fees:,.2f}")
    print(f"  DIR per Claim: ${projection.dir_per_claim:.2f}")
    print(f"  DIR as % Revenue: {projection.dir_as_pct_revenue}%")
    print(f"  Margin Impact: {projection.margin_impact_pct}%")
    print(f"  Impact Level: {projection.impact_level.value}")
    print(f"  POS vs Retro Savings: ${projection.pos_vs_retro_savings:,.2f}")

    # GER analysis
    ger = forecaster.analyze_ger("Atorvastatin 40mg", "0378-2277-05", 0.08, 0.45, 500)
    print(f"\nGER Analysis for {ger.drug_name}:")
    print(f"  Gross GER: {ger.gross_ger}%")
    print(f"  Net GER (after DIR): {ger.net_ger}%")
    print(f"  Underwater after DIR: {ger.underwater_after_dir}")

    # Stats
    stats = forecaster.get_statistics()
    print(f"\nStats: {json.dumps(stats, indent=2)}")
