"""
GetPaidRx — NADAC Pricing Engine
National Average Drug Acquisition Cost (NADAC) integration for 
underpayment detection, cost benchmarking, and reimbursement analysis.

NADAC is CMS's weekly-updated survey of actual pharmacy acquisition
costs. This engine uses NADAC data to:
  - Compare actual reimbursement vs NADAC benchmark
  - Identify underwater claims (paid below acquisition cost)
  - Calculate pharmacy spread (reimbursement - acquisition cost)
  - Track NADAC rate changes over time with volatility scoring
  - Generate payer-level NADAC compliance reports
  - Flag claims where PBMs reimburse below NADAC (MAC pricing abuse)
  - Produce NADAC-based appeal letters for underpaid claims
"""

import json
import uuid
import math
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from enum import Enum


# ============================================================
# Enums & Constants
# ============================================================

class NDCClassification(str, Enum):
    BRAND = "brand"
    GENERIC = "generic"
    OTC = "otc"
    SPECIALTY = "specialty"
    COMPOUND = "compound"


class ReimbursementStatus(str, Enum):
    ADEQUATE = "adequate"       # Reimbursement >= NADAC + reasonable spread
    MARGINAL = "marginal"       # Reimbursement covers NADAC but spread < $1
    UNDERWATER = "underwater"   # Reimbursement < NADAC (loss per fill)
    SEVERELY_UNDERWATER = "severely_underwater"  # Loss > $10 per fill


class AppealPriority(str, Enum):
    CRITICAL = "critical"    # High volume + high loss per fill
    HIGH = "high"           # High volume OR high loss
    MEDIUM = "medium"       # Moderate impact
    LOW = "low"             # Low volume, small loss


# Reasonable dispensing fee and spread targets
DISPENSING_FEE_BENCHMARK = 10.50  # CMS recommended dispensing fee
MIN_ACCEPTABLE_SPREAD = 1.00  # Minimum acceptable spread above NADAC
UNDERWATER_THRESHOLD = 0.0  # At or below NADAC = underwater
SEVERE_UNDERWATER_THRESHOLD = -10.0  # Loss > $10

# Drug category cost multipliers (specialty drugs cost more to handle)
CATEGORY_HANDLING_COST = {
    NDCClassification.BRAND: 2.50,
    NDCClassification.GENERIC: 1.00,
    NDCClassification.OTC: 0.50,
    NDCClassification.SPECIALTY: 15.00,
    NDCClassification.COMPOUND: 8.00,
}


# ============================================================
# Data Models
# ============================================================

class NADACRate:
    """A NADAC rate entry for a specific NDC on a specific date."""

    def __init__(
        self,
        ndc: str,
        drug_name: str,
        nadac_per_unit: float,
        effective_date: str,
        classification: NDCClassification = NDCClassification.GENERIC,
        package_size: int = 1,
        otc_flag: bool = False,
        pharmacy_type_indicator: str = "C/I",  # Community/Institutional
    ):
        self.ndc = ndc
        self.drug_name = drug_name
        self.nadac_per_unit = nadac_per_unit
        self.effective_date = effective_date
        self.classification = classification
        self.package_size = package_size
        self.otc_flag = otc_flag
        self.pharmacy_type_indicator = pharmacy_type_indicator

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ndc": self.ndc,
            "drug_name": self.drug_name,
            "nadac_per_unit": self.nadac_per_unit,
            "effective_date": self.effective_date,
            "classification": self.classification.value,
            "package_size": self.package_size,
            "otc_flag": self.otc_flag,
        }


class ClaimAnalysis:
    """NADAC analysis result for a single claim."""

    def __init__(
        self,
        claim_id: str,
        ndc: str,
        drug_name: str,
        quantity: float,
        days_supply: int,
        payer_name: str,
        reimbursement_amount: float,
        dispensing_fee_paid: float,
        patient_copay: float,
        nadac_per_unit: float,
        classification: NDCClassification,
        fill_date: str,
    ):
        self.claim_id = claim_id
        self.ndc = ndc
        self.drug_name = drug_name
        self.quantity = quantity
        self.days_supply = days_supply
        self.payer_name = payer_name
        self.reimbursement_amount = reimbursement_amount
        self.dispensing_fee_paid = dispensing_fee_paid
        self.patient_copay = patient_copay
        self.nadac_per_unit = nadac_per_unit
        self.classification = classification
        self.fill_date = fill_date

        # Calculated fields
        self.nadac_total = round(nadac_per_unit * quantity, 2)
        self.total_received = round(reimbursement_amount + dispensing_fee_paid + patient_copay, 2)
        self.spread = round(self.total_received - self.nadac_total, 2)
        self.spread_per_unit = round(self.spread / max(quantity, 1), 4)
        self.margin_pct = round(self.spread / max(self.nadac_total, 0.01) * 100, 2)
        self.handling_cost = CATEGORY_HANDLING_COST.get(classification, 1.00)
        self.net_profit = round(self.spread - self.handling_cost - DISPENSING_FEE_BENCHMARK, 2)

        # Status classification
        if self.spread >= MIN_ACCEPTABLE_SPREAD:
            self.status = ReimbursementStatus.ADEQUATE
        elif self.spread >= UNDERWATER_THRESHOLD:
            self.status = ReimbursementStatus.MARGINAL
        elif self.spread >= SEVERE_UNDERWATER_THRESHOLD:
            self.status = ReimbursementStatus.UNDERWATER
        else:
            self.status = ReimbursementStatus.SEVERELY_UNDERWATER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "ndc": self.ndc,
            "drug_name": self.drug_name,
            "quantity": self.quantity,
            "days_supply": self.days_supply,
            "payer_name": self.payer_name,
            "reimbursement_amount": self.reimbursement_amount,
            "dispensing_fee_paid": self.dispensing_fee_paid,
            "patient_copay": self.patient_copay,
            "nadac_per_unit": self.nadac_per_unit,
            "nadac_total": self.nadac_total,
            "total_received": self.total_received,
            "spread": self.spread,
            "spread_per_unit": self.spread_per_unit,
            "margin_pct": self.margin_pct,
            "handling_cost": self.handling_cost,
            "net_profit": self.net_profit,
            "status": self.status.value,
            "classification": self.classification.value,
            "fill_date": self.fill_date,
        }


# ============================================================
# NADAC Pricing Engine
# ============================================================

class NADACPricingEngine:
    """
    Core engine for NADAC-based reimbursement analysis.
    Maintains a NADAC rate database and analyzes claims against it.
    """

    def __init__(self):
        # NDC → list of NADACRate (sorted by effective_date)
        self.nadac_rates: Dict[str, List[NADACRate]] = defaultdict(list)
        self.claim_analyses: List[ClaimAnalysis] = []
        self.last_update: Optional[str] = None

    # ----------------------------------------------------------
    # NADAC Rate Management
    # ----------------------------------------------------------

    def load_nadac_rates(self, rates: List[Dict[str, Any]]) -> int:
        """Load NADAC rates from a list of dictionaries."""
        count = 0
        for r in rates:
            rate = NADACRate(
                ndc=r["ndc"],
                drug_name=r["drug_name"],
                nadac_per_unit=float(r["nadac_per_unit"]),
                effective_date=r.get("effective_date", datetime.utcnow().strftime("%Y-%m-%d")),
                classification=NDCClassification(r.get("classification", "generic")),
                package_size=int(r.get("package_size", 1)),
                otc_flag=r.get("otc_flag", False),
            )
            self.nadac_rates[rate.ndc].append(rate)
            count += 1

        # Sort each NDC's rates by date
        for ndc in self.nadac_rates:
            self.nadac_rates[ndc].sort(key=lambda x: x.effective_date, reverse=True)

        self.last_update = datetime.utcnow().isoformat()
        return count

    def get_nadac_rate(self, ndc: str, as_of_date: Optional[str] = None) -> Optional[NADACRate]:
        """Get the applicable NADAC rate for an NDC as of a given date."""
        rates = self.nadac_rates.get(ndc, [])
        if not rates:
            return None

        if as_of_date is None:
            return rates[0]  # Most recent

        for rate in rates:
            if rate.effective_date <= as_of_date:
                return rate
        return rates[-1]  # Oldest if no match

    def get_rate_history(self, ndc: str) -> List[Dict[str, Any]]:
        """Get price history for an NDC."""
        rates = self.nadac_rates.get(ndc, [])
        if len(rates) < 2:
            return [r.to_dict() for r in rates]

        history = []
        for i, rate in enumerate(rates):
            entry = rate.to_dict()
            if i < len(rates) - 1:
                prev = rates[i + 1]
                change = rate.nadac_per_unit - prev.nadac_per_unit
                change_pct = round(change / max(prev.nadac_per_unit, 0.01) * 100, 2)
                entry["change_from_prev"] = round(change, 4)
                entry["change_pct"] = change_pct
            history.append(entry)
        return history

    def get_volatile_ndcs(self, min_changes: int = 3, min_volatility_pct: float = 15.0) -> List[Dict[str, Any]]:
        """Identify NDCs with high price volatility."""
        volatile = []
        for ndc, rates in self.nadac_rates.items():
            if len(rates) < min_changes:
                continue
            prices = [r.nadac_per_unit for r in rates]
            avg_price = statistics.mean(prices)
            if avg_price == 0:
                continue
            std_dev = statistics.stdev(prices)
            cv = round(std_dev / avg_price * 100, 2)  # Coefficient of variation

            if cv >= min_volatility_pct:
                volatile.append({
                    "ndc": ndc,
                    "drug_name": rates[0].drug_name,
                    "rate_count": len(rates),
                    "current_rate": rates[0].nadac_per_unit,
                    "avg_rate": round(avg_price, 4),
                    "min_rate": min(prices),
                    "max_rate": max(prices),
                    "std_dev": round(std_dev, 4),
                    "volatility_cv_pct": cv,
                })

        volatile.sort(key=lambda v: v["volatility_cv_pct"], reverse=True)
        return volatile

    # ----------------------------------------------------------
    # Claim Analysis
    # ----------------------------------------------------------

    def analyze_claim(self, claim: Dict[str, Any]) -> ClaimAnalysis:
        """Analyze a single claim against NADAC benchmark."""
        ndc = claim["ndc"]
        fill_date = claim.get("fill_date", datetime.utcnow().strftime("%Y-%m-%d"))
        nadac_rate = self.get_nadac_rate(ndc, fill_date)

        nadac_per_unit = nadac_rate.nadac_per_unit if nadac_rate else 0
        classification = nadac_rate.classification if nadac_rate else NDCClassification.GENERIC

        analysis = ClaimAnalysis(
            claim_id=claim.get("claim_id", str(uuid.uuid4())[:10]),
            ndc=ndc,
            drug_name=claim.get("drug_name", nadac_rate.drug_name if nadac_rate else "Unknown"),
            quantity=float(claim.get("quantity", 30)),
            days_supply=int(claim.get("days_supply", 30)),
            payer_name=claim.get("payer_name", "Unknown"),
            reimbursement_amount=float(claim.get("reimbursement_amount", 0)),
            dispensing_fee_paid=float(claim.get("dispensing_fee_paid", 0)),
            patient_copay=float(claim.get("patient_copay", 0)),
            nadac_per_unit=nadac_per_unit,
            classification=classification,
            fill_date=fill_date,
        )
        self.claim_analyses.append(analysis)
        return analysis

    def analyze_batch(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a batch of claims and return summary."""
        results = [self.analyze_claim(c) for c in claims]

        total_spread = sum(r.spread for r in results)
        underwater = [r for r in results if r.status in (ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER)]
        underwater_loss = sum(abs(r.spread) for r in underwater)

        status_counts = defaultdict(int)
        payer_losses = defaultdict(float)
        drug_losses = defaultdict(lambda: {"count": 0, "total_loss": 0, "drug_name": ""})

        for r in results:
            status_counts[r.status.value] += 1
            if r.status in (ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER):
                payer_losses[r.payer_name] += abs(r.spread)
                d = drug_losses[r.ndc]
                d["count"] += 1
                d["total_loss"] += abs(r.spread)
                d["drug_name"] = r.drug_name

        # Top offending payers
        top_payers = sorted(payer_losses.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top underwater drugs
        top_drugs = sorted(
            drug_losses.items(),
            key=lambda x: x[1]["total_loss"],
            reverse=True
        )[:10]

        return {
            "total_claims": len(results),
            "total_spread": round(total_spread, 2),
            "avg_spread_per_claim": round(total_spread / max(len(results), 1), 2),
            "underwater_count": len(underwater),
            "underwater_pct": round(len(underwater) / max(len(results), 1) * 100, 1),
            "total_underwater_loss": round(underwater_loss, 2),
            "status_distribution": dict(status_counts),
            "top_offending_payers": [{"payer": p, "total_loss": round(l, 2)} for p, l in top_payers],
            "top_underwater_drugs": [
                {"ndc": ndc, "drug_name": d["drug_name"], "claim_count": d["count"], "total_loss": round(d["total_loss"], 2)}
                for ndc, d in top_drugs
            ],
        }

    # ----------------------------------------------------------
    # Payer NADAC Compliance Report
    # ----------------------------------------------------------

    def payer_nadac_compliance(self) -> List[Dict[str, Any]]:
        """
        Generate payer-level NADAC compliance report.
        Shows how each PBM/payer reimburses relative to NADAC.
        """
        payer_data = defaultdict(lambda: {
            "claims": 0,
            "total_reimbursement": 0,
            "total_nadac": 0,
            "underwater_count": 0,
            "underwater_loss": 0,
            "spreads": [],
        })

        for analysis in self.claim_analyses:
            p = payer_data[analysis.payer_name]
            p["claims"] += 1
            p["total_reimbursement"] += analysis.total_received
            p["total_nadac"] += analysis.nadac_total
            p["spreads"].append(analysis.spread)
            if analysis.status in (ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER):
                p["underwater_count"] += 1
                p["underwater_loss"] += abs(analysis.spread)

        results = []
        for payer_name, data in payer_data.items():
            avg_spread = statistics.mean(data["spreads"]) if data["spreads"] else 0
            median_spread = statistics.median(data["spreads"]) if data["spreads"] else 0
            total_spread = sum(data["spreads"])
            nadac_compliance_pct = round(
                data["total_reimbursement"] / max(data["total_nadac"], 1) * 100, 2
            )

            # Grade: A (>110%), B (105-110%), C (100-105%), D (95-100%), F (<95%)
            if nadac_compliance_pct >= 110:
                grade = "A"
            elif nadac_compliance_pct >= 105:
                grade = "B"
            elif nadac_compliance_pct >= 100:
                grade = "C"
            elif nadac_compliance_pct >= 95:
                grade = "D"
            else:
                grade = "F"

            results.append({
                "payer_name": payer_name,
                "total_claims": data["claims"],
                "total_reimbursement": round(data["total_reimbursement"], 2),
                "total_nadac_cost": round(data["total_nadac"], 2),
                "total_spread": round(total_spread, 2),
                "avg_spread_per_claim": round(avg_spread, 2),
                "median_spread": round(median_spread, 2),
                "nadac_compliance_pct": nadac_compliance_pct,
                "grade": grade,
                "underwater_claims": data["underwater_count"],
                "underwater_pct": round(data["underwater_count"] / max(data["claims"], 1) * 100, 1),
                "total_underwater_loss": round(data["underwater_loss"], 2),
                "annualized_impact": round(total_spread * (365 / 30), 2),
            })

        results.sort(key=lambda r: r["total_underwater_loss"], reverse=True)
        return results

    # ----------------------------------------------------------
    # Appeal Letter Generator
    # ----------------------------------------------------------

    def generate_appeal_letter(
        self,
        payer_name: str,
        pharmacy_name: str = "Your Pharmacy",
        pharmacy_npi: str = "",
        contact_name: str = "Pharmacy Manager",
    ) -> Dict[str, Any]:
        """
        Generate a NADAC-based appeal letter for underpaid claims from a payer.
        Includes specific claim data, NADAC benchmarks, and CMS citation.
        """
        payer_claims = [
            a for a in self.claim_analyses
            if a.payer_name == payer_name and a.status in (
                ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER
            )
        ]

        if not payer_claims:
            return {"error": f"No underwater claims found for {payer_name}"}

        total_loss = sum(abs(c.spread) for c in payer_claims)
        annualized_loss = total_loss * (365 / 30)

        # Priority based on volume and loss
        if total_loss > 5000 or len(payer_claims) > 50:
            priority = AppealPriority.CRITICAL
        elif total_loss > 1000 or len(payer_claims) > 20:
            priority = AppealPriority.HIGH
        elif total_loss > 250:
            priority = AppealPriority.MEDIUM
        else:
            priority = AppealPriority.LOW

        # Top 5 worst offending NDCs
        drug_losses = defaultdict(lambda: {"count": 0, "loss": 0, "name": "", "nadac": 0, "reimb": 0})
        for c in payer_claims:
            d = drug_losses[c.ndc]
            d["count"] += 1
            d["loss"] += abs(c.spread)
            d["name"] = c.drug_name
            d["nadac"] = c.nadac_per_unit
            d["reimb"] = c.reimbursement_amount / max(c.quantity, 1)

        top_drugs = sorted(drug_losses.items(), key=lambda x: x[1]["loss"], reverse=True)[:5]

        # Build letter
        letter_lines = [
            f"Date: {datetime.utcnow().strftime('%B %d, %Y')}",
            f"From: {pharmacy_name}" + (f" (NPI: {pharmacy_npi})" if pharmacy_npi else ""),
            f"To: {payer_name} — Provider Relations / Pharmacy Network Department",
            f"Re: NADAC Reimbursement Deficiency — {len(payer_claims)} Claims Below Acquisition Cost",
            "",
            "Dear Provider Relations Team,",
            "",
            f"This letter formally requests a review of {len(payer_claims)} pharmacy claims adjudicated "
            f"by {payer_name} that were reimbursed below the National Average Drug Acquisition Cost (NADAC) "
            f"as published by the Centers for Medicare & Medicaid Services (CMS).",
            "",
            f"SUMMARY OF UNDERPAYMENT:",
            f"  • Claims Below NADAC: {len(payer_claims)}",
            f"  • Total Underpayment (30-day period): ${total_loss:,.2f}",
            f"  • Projected Annual Impact: ${annualized_loss:,.2f}",
            "",
            "TOP AFFECTED MEDICATIONS:",
        ]

        for ndc, data in top_drugs:
            letter_lines.append(
                f"  • {data['name']} (NDC: {ndc}): "
                f"NADAC=${data['nadac']:.4f}/unit, "
                f"Reimbursed=${data['reimb']:.4f}/unit, "
                f"Loss=${data['loss']:,.2f} across {data['count']} fills"
            )

        letter_lines.extend([
            "",
            "LEGAL BASIS:",
            "CMS publishes NADAC weekly as a benchmark for actual pharmacy acquisition costs. ",
            "Reimbursement below NADAC violates the principle that pharmacies should not be required ",
            "to dispense medications at a financial loss. Many state pharmacy practice acts require ",
            "reimbursement at or above acquisition cost plus a reasonable dispensing fee.",
            "",
            "REQUESTED ACTION:",
            "1. Retroactive adjustment of identified claims to NADAC + reasonable dispensing fee",
            "2. Prospective MAC list update to ensure future reimbursements meet NADAC benchmarks",
            "3. Written response within 30 business days per network agreement terms",
            "",
            f"A detailed claim-level spreadsheet is available upon request.",
            "",
            f"Respectfully,",
            f"{contact_name}",
            f"{pharmacy_name}",
        ])

        return {
            "priority": priority.value,
            "payer_name": payer_name,
            "claim_count": len(payer_claims),
            "total_loss": round(total_loss, 2),
            "annualized_loss": round(annualized_loss, 2),
            "top_drugs": [
                {"ndc": ndc, "drug_name": d["name"], "loss": round(d["loss"], 2), "fills": d["count"]}
                for ndc, d in top_drugs
            ],
            "letter_text": "\n".join(letter_lines),
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ----------------------------------------------------------
    # Executive NADAC Report
    # ----------------------------------------------------------

    def executive_summary(self) -> Dict[str, Any]:
        """Generate executive-level NADAC analysis summary."""
        if not self.claim_analyses:
            return {"message": "No claims analyzed yet"}

        total_claims = len(self.claim_analyses)
        total_revenue = sum(a.total_received for a in self.claim_analyses)
        total_nadac = sum(a.nadac_total for a in self.claim_analyses)
        total_spread = sum(a.spread for a in self.claim_analyses)

        underwater = [a for a in self.claim_analyses
                      if a.status in (ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER)]
        underwater_loss = sum(abs(a.spread) for a in underwater)

        # Classification breakdown
        class_data = defaultdict(lambda: {"count": 0, "spread": 0, "underwater": 0})
        for a in self.claim_analyses:
            c = class_data[a.classification.value]
            c["count"] += 1
            c["spread"] += a.spread
            if a.status in (ReimbursementStatus.UNDERWATER, ReimbursementStatus.SEVERELY_UNDERWATER):
                c["underwater"] += 1

        return {
            "report_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_claims_analyzed": total_claims,
            "total_revenue": round(total_revenue, 2),
            "total_nadac_cost": round(total_nadac, 2),
            "total_spread": round(total_spread, 2),
            "overall_margin_pct": round(total_spread / max(total_nadac, 1) * 100, 2),
            "underwater_claims": len(underwater),
            "underwater_pct": round(len(underwater) / max(total_claims, 1) * 100, 1),
            "total_underwater_loss": round(underwater_loss, 2),
            "annualized_underwater_loss": round(underwater_loss * (365 / 30), 2),
            "classification_breakdown": {k: dict(v) for k, v in class_data.items()},
            "payer_compliance": self.payer_nadac_compliance()[:5],
            "volatile_ndcs": self.get_volatile_ndcs()[:5],
            "nadac_rate_count": sum(len(r) for r in self.nadac_rates.values()),
            "last_nadac_update": self.last_update,
        }


# ============================================================
# FastAPI Route Registration
# ============================================================

def register_nadac_routes(app, engine: Optional[NADACPricingEngine] = None):
    """Register NADAC pricing API routes."""
    from fastapi import Body

    if engine is None:
        engine = NADACPricingEngine()

    @app.post("/api/v1/nadac/load-rates")
    async def load_rates(payload: Dict[str, Any] = Body(...)):
        count = engine.load_nadac_rates(payload["rates"])
        return {"loaded": count, "updated_at": engine.last_update}

    @app.get("/api/v1/nadac/rate/{ndc}")
    async def get_rate(ndc: str, as_of: Optional[str] = None):
        rate = engine.get_nadac_rate(ndc, as_of)
        return rate.to_dict() if rate else {"error": "Rate not found"}

    @app.get("/api/v1/nadac/history/{ndc}")
    async def get_history(ndc: str):
        return engine.get_rate_history(ndc)

    @app.get("/api/v1/nadac/volatile")
    async def get_volatile():
        return engine.get_volatile_ndcs()

    @app.post("/api/v1/nadac/analyze")
    async def analyze_claim(payload: Dict[str, Any] = Body(...)):
        result = engine.analyze_claim(payload)
        return result.to_dict()

    @app.post("/api/v1/nadac/analyze-batch")
    async def analyze_batch(payload: Dict[str, Any] = Body(...)):
        return engine.analyze_batch(payload["claims"])

    @app.get("/api/v1/nadac/payer-compliance")
    async def payer_compliance():
        return engine.payer_nadac_compliance()

    @app.post("/api/v1/nadac/appeal-letter")
    async def appeal_letter(payload: Dict[str, Any] = Body(...)):
        return engine.generate_appeal_letter(
            payer_name=payload["payer_name"],
            pharmacy_name=payload.get("pharmacy_name", "Your Pharmacy"),
            pharmacy_npi=payload.get("pharmacy_npi", ""),
            contact_name=payload.get("contact_name", "Pharmacy Manager"),
        )

    @app.get("/api/v1/nadac/executive-summary")
    async def executive_summary():
        return engine.executive_summary()

    return engine
