"""
NADAC Price Variance Alerting System
========================================
Monitors National Average Drug Acquisition Cost (NADAC) price changes
in real-time, detects significant variances against reimbursement rates,
generates margin alerts, and identifies cost optimization opportunities.

Features:
- NADAC price change monitoring with configurable thresholds
- Reimbursement vs acquisition cost variance tracking
- Underwater claim detection (cost > reimbursement)
- Price spike alerts with severity classification
- Generic vs brand cost flip detection
- Therapeutic alternative cost comparison
- Historical price trend analysis with anomaly detection
- Margin erosion forecasting
- Automated alert routing by severity and drug class
- Weekly/monthly NADAC change summary reports

Author: GetPaidRx Engineering
Version: 1.0.0
"""

import json
import uuid
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, Counter
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    CRITICAL = "critical"    # Immediate margin loss
    HIGH = "high"            # Significant cost increase
    MEDIUM = "medium"        # Notable variance
    LOW = "low"              # Minor change
    INFO = "info"            # Tracking only


class DrugSchedule(Enum):
    NON_CONTROLLED = "non_controlled"
    SCHEDULE_II = "schedule_II"
    SCHEDULE_III = "schedule_III"
    SCHEDULE_IV = "schedule_IV"
    SCHEDULE_V = "schedule_V"


class PriceDirection(Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    STABLE = "stable"


@dataclass
class DrugProduct:
    """A drug product tracked in the system."""
    ndc: str
    drug_name: str
    generic_name: str
    strength: str
    dosage_form: str
    package_size: str
    manufacturer: str
    is_brand: bool = False
    is_specialty: bool = False
    schedule: DrugSchedule = DrugSchedule.NON_CONTROLLED
    therapeutic_class: str = ""
    gpi_code: str = ""  # Generic Product Identifier
    awp: float = 0.0
    wac: float = 0.0


@dataclass
class NADACPrice:
    """A NADAC price record."""
    ndc: str
    effective_date: str
    nadac_per_unit: float
    previous_nadac: float = 0.0
    pricing_unit: str = "EA"
    classification: str = "G"  # G=Generic, B=Brand, I=Innovator
    as_of_date: str = ""

    @property
    def change_amount(self) -> float:
        return self.nadac_per_unit - self.previous_nadac

    @property
    def change_percent(self) -> float:
        if self.previous_nadac > 0:
            return ((self.nadac_per_unit - self.previous_nadac) / self.previous_nadac) * 100
        return 0.0

    @property
    def direction(self) -> PriceDirection:
        if self.change_percent > 1:
            return PriceDirection.INCREASE
        elif self.change_percent < -1:
            return PriceDirection.DECREASE
        return PriceDirection.STABLE


@dataclass
class ReimbursementRate:
    """Payer reimbursement rate for a drug."""
    ndc: str
    payer_id: str
    payer_name: str
    rate_per_unit: float
    rate_type: str = "NADAC+"  # NADAC+, AWP-, MAC, FUL
    rate_formula: str = ""
    dispensing_fee: float = 0.0
    effective_date: str = ""
    expiration_date: str = ""


@dataclass
class VarianceAlert:
    """A price variance alert."""
    alert_id: str
    ndc: str
    drug_name: str
    severity: AlertSeverity
    alert_type: str
    message: str
    nadac_price: float
    reimbursement_rate: float = 0.0
    variance_amount: float = 0.0
    variance_percent: float = 0.0
    margin_impact: float = 0.0
    monthly_volume: int = 0
    monthly_impact: float = 0.0
    created_at: str = ""
    acknowledged: bool = False
    action_taken: str = ""

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = str(uuid.uuid4())[:10]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class NADACVarianceAlertSystem:
    """
    Monitors NADAC prices and generates alerts when significant
    variances are detected against reimbursement rates.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.products: Dict[str, DrugProduct] = {}
        self.nadac_history: Dict[str, List[NADACPrice]] = defaultdict(list)
        self.reimbursement_rates: Dict[str, List[ReimbursementRate]] = defaultdict(list)
        self.dispensing_volume: Dict[str, int] = defaultdict(int)  # Monthly units by NDC
        self.alerts: List[VarianceAlert] = []
        self.alert_rules: Dict[str, Dict[str, float]] = {}

        # Default thresholds
        self.config = config or {}
        self.thresholds = {
            "critical_margin_loss": -2.00,     # Per unit loss threshold
            "high_price_increase_pct": 20.0,   # % increase for HIGH alert
            "medium_price_increase_pct": 10.0, # % increase for MEDIUM alert
            "low_price_increase_pct": 5.0,     # % increase for LOW alert
            "underwater_threshold": 0.0,        # Reimbursement - cost < 0
            "spike_lookback_days": 90,          # Days to look back for spike detection
            "spike_std_multiplier": 2.0,        # Standard deviations for spike
            "min_monthly_volume": 10,           # Minimum volume to alert
        }
        self.thresholds.update(self.config.get("thresholds", {}))

    def register_product(self, product: DrugProduct) -> str:
        """Register a drug product for monitoring."""
        self.products[product.ndc] = product
        return product.ndc

    def update_nadac_price(self, price: NADACPrice) -> List[VarianceAlert]:
        """Process a new NADAC price update and check for alerts."""
        # Store history
        history = self.nadac_history[price.ndc]
        if history:
            price.previous_nadac = history[-1].nadac_per_unit
        history.append(price)

        alerts = []

        # Check price change alerts
        if price.previous_nadac > 0:
            change_alerts = self._check_price_change_alerts(price)
            alerts.extend(change_alerts)

        # Check margin alerts against all reimbursement rates
        margin_alerts = self._check_margin_alerts(price)
        alerts.extend(margin_alerts)

        # Check for price spike (anomaly)
        spike_alerts = self._check_price_spike(price)
        alerts.extend(spike_alerts)

        self.alerts.extend(alerts)
        return alerts

    def set_reimbursement_rate(self, rate: ReimbursementRate):
        """Set or update a reimbursement rate for an NDC-payer combination."""
        rates = self.reimbursement_rates[rate.ndc]
        # Replace existing rate for same payer
        rates = [r for r in rates if r.payer_id != rate.payer_id]
        rates.append(rate)
        self.reimbursement_rates[rate.ndc] = rates

    def set_dispensing_volume(self, ndc: str, monthly_units: int):
        """Set monthly dispensing volume for an NDC."""
        self.dispensing_volume[ndc] = monthly_units

    def _check_price_change_alerts(self, price: NADACPrice) -> List[VarianceAlert]:
        """Check for significant price change alerts."""
        alerts = []
        product = self.products.get(price.ndc)
        drug_name = product.drug_name if product else price.ndc
        change_pct = price.change_percent

        if change_pct >= self.thresholds["high_price_increase_pct"]:
            severity = AlertSeverity.HIGH
            if change_pct >= 50:
                severity = AlertSeverity.CRITICAL
            volume = self.dispensing_volume.get(price.ndc, 0)
            monthly_impact = price.change_amount * volume

            alerts.append(VarianceAlert(
                alert_id="",
                ndc=price.ndc,
                drug_name=drug_name,
                severity=severity,
                alert_type="price_increase",
                message=f"NADAC price increased {change_pct:.1f}% "
                       f"(${price.previous_nadac:.4f} → ${price.nadac_per_unit:.4f})",
                nadac_price=price.nadac_per_unit,
                variance_amount=price.change_amount,
                variance_percent=change_pct,
                monthly_volume=volume,
                monthly_impact=round(monthly_impact, 2)
            ))
        elif change_pct >= self.thresholds["medium_price_increase_pct"]:
            alerts.append(VarianceAlert(
                alert_id="",
                ndc=price.ndc,
                drug_name=drug_name,
                severity=AlertSeverity.MEDIUM,
                alert_type="price_increase",
                message=f"NADAC price increased {change_pct:.1f}%",
                nadac_price=price.nadac_per_unit,
                variance_percent=change_pct
            ))
        elif change_pct >= self.thresholds["low_price_increase_pct"]:
            alerts.append(VarianceAlert(
                alert_id="",
                ndc=price.ndc,
                drug_name=drug_name,
                severity=AlertSeverity.LOW,
                alert_type="price_increase",
                message=f"NADAC price increased {change_pct:.1f}%",
                nadac_price=price.nadac_per_unit,
                variance_percent=change_pct
            ))

        # Also alert on significant decreases (opportunity)
        if change_pct <= -15:
            alerts.append(VarianceAlert(
                alert_id="",
                ndc=price.ndc,
                drug_name=drug_name,
                severity=AlertSeverity.INFO,
                alert_type="price_decrease_opportunity",
                message=f"NADAC price decreased {abs(change_pct):.1f}% — margin improvement opportunity",
                nadac_price=price.nadac_per_unit,
                variance_percent=change_pct
            ))

        return alerts

    def _check_margin_alerts(self, price: NADACPrice) -> List[VarianceAlert]:
        """Check margins against reimbursement rates."""
        alerts = []
        product = self.products.get(price.ndc)
        drug_name = product.drug_name if product else price.ndc
        rates = self.reimbursement_rates.get(price.ndc, [])
        volume = self.dispensing_volume.get(price.ndc, 0)

        for rate in rates:
            margin = rate.rate_per_unit + rate.dispensing_fee - price.nadac_per_unit
            margin_pct = (margin / max(price.nadac_per_unit, 0.0001)) * 100

            if margin < self.thresholds["underwater_threshold"]:
                monthly_loss = abs(margin) * volume
                alerts.append(VarianceAlert(
                    alert_id="",
                    ndc=price.ndc,
                    drug_name=drug_name,
                    severity=AlertSeverity.CRITICAL if monthly_loss > 500 else AlertSeverity.HIGH,
                    alert_type="underwater_claim",
                    message=f"UNDERWATER: {rate.payer_name} reimburses ${rate.rate_per_unit:.4f} "
                           f"(+${rate.dispensing_fee:.2f} fee) but NADAC is ${price.nadac_per_unit:.4f}. "
                           f"Loss: ${abs(margin):.4f}/unit",
                    nadac_price=price.nadac_per_unit,
                    reimbursement_rate=rate.rate_per_unit,
                    variance_amount=round(margin, 4),
                    variance_percent=round(margin_pct, 2),
                    margin_impact=round(margin, 4),
                    monthly_volume=volume,
                    monthly_impact=round(-monthly_loss, 2)
                ))
            elif margin < self.thresholds["critical_margin_loss"]:
                alerts.append(VarianceAlert(
                    alert_id="",
                    ndc=price.ndc,
                    drug_name=drug_name,
                    severity=AlertSeverity.HIGH,
                    alert_type="margin_erosion",
                    message=f"Low margin: {rate.payer_name} margin is ${margin:.4f}/unit ({margin_pct:.1f}%)",
                    nadac_price=price.nadac_per_unit,
                    reimbursement_rate=rate.rate_per_unit,
                    margin_impact=round(margin, 4)
                ))

        return alerts

    def _check_price_spike(self, price: NADACPrice) -> List[VarianceAlert]:
        """Detect price anomalies using statistical analysis."""
        alerts = []
        history = self.nadac_history.get(price.ndc, [])

        if len(history) < 5:
            return alerts  # Not enough history

        # Calculate stats from history (excluding current)
        prior_prices = [h.nadac_per_unit for h in history[:-1]]
        mean_price = sum(prior_prices) / len(prior_prices)
        variance = sum((p - mean_price) ** 2 for p in prior_prices) / len(prior_prices)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev > 0:
            z_score = (price.nadac_per_unit - mean_price) / std_dev
            if abs(z_score) > self.thresholds["spike_std_multiplier"]:
                product = self.products.get(price.ndc)
                drug_name = product.drug_name if product else price.ndc
                direction = "spike" if z_score > 0 else "drop"

                alerts.append(VarianceAlert(
                    alert_id="",
                    ndc=price.ndc,
                    drug_name=drug_name,
                    severity=AlertSeverity.HIGH if abs(z_score) > 3 else AlertSeverity.MEDIUM,
                    alert_type=f"price_{direction}_anomaly",
                    message=f"Anomalous price {direction}: ${price.nadac_per_unit:.4f} "
                           f"(z-score: {z_score:.2f}, mean: ${mean_price:.4f}, std: ${std_dev:.4f})",
                    nadac_price=price.nadac_per_unit,
                    variance_amount=round(price.nadac_per_unit - mean_price, 4)
                ))

        return alerts

    def find_generic_brand_flips(self) -> List[Dict[str, Any]]:
        """Detect cases where generic cost exceeds or approaches brand cost."""
        flips = []
        # Group products by generic name
        by_generic: Dict[str, List[DrugProduct]] = defaultdict(list)
        for ndc, product in self.products.items():
            by_generic[product.generic_name.lower()].append(product)

        for generic_name, products in by_generic.items():
            brands = [p for p in products if p.is_brand]
            generics = [p for p in products if not p.is_brand]

            if not brands or not generics:
                continue

            for generic in generics:
                g_history = self.nadac_history.get(generic.ndc, [])
                if not g_history:
                    continue
                g_price = g_history[-1].nadac_per_unit

                for brand in brands:
                    b_history = self.nadac_history.get(brand.ndc, [])
                    if not b_history:
                        continue
                    b_price = b_history[-1].nadac_per_unit

                    if g_price >= b_price * 0.85:  # Generic is 85%+ of brand
                        ratio = (g_price / max(b_price, 0.0001)) * 100
                        flips.append({
                            "generic_ndc": generic.ndc,
                            "generic_name": generic.drug_name,
                            "generic_price": round(g_price, 4),
                            "brand_ndc": brand.ndc,
                            "brand_name": brand.drug_name,
                            "brand_price": round(b_price, 4),
                            "generic_to_brand_ratio": round(ratio, 1),
                            "is_flipped": g_price >= b_price,
                            "alert": "FLIPPED" if g_price >= b_price else "APPROACHING"
                        })

        return flips

    def generate_weekly_summary(self) -> Dict[str, Any]:
        """Generate weekly NADAC change summary."""
        cutoff = datetime.now() - timedelta(days=7)
        cutoff_str = cutoff.isoformat()

        recent_alerts = [a for a in self.alerts if a.created_at >= cutoff_str]

        severity_counts = Counter(a.severity.value for a in recent_alerts)
        type_counts = Counter(a.alert_type for a in recent_alerts)

        total_monthly_impact = sum(a.monthly_impact for a in recent_alerts if a.monthly_impact)
        underwater_count = sum(1 for a in recent_alerts if a.alert_type == "underwater_claim")

        # Top impactful NDCs
        ndc_impacts: Dict[str, float] = defaultdict(float)
        for a in recent_alerts:
            if a.monthly_impact:
                ndc_impacts[a.ndc] += a.monthly_impact

        top_negative = sorted(ndc_impacts.items(), key=lambda x: x[1])[:5]

        return {
            "report_period": f"{cutoff.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
            "total_alerts": len(recent_alerts),
            "severity_breakdown": dict(severity_counts),
            "alert_type_breakdown": dict(type_counts),
            "underwater_claims": underwater_count,
            "total_projected_monthly_impact": round(total_monthly_impact, 2),
            "top_negative_impact_ndcs": [
                {"ndc": ndc, "monthly_impact": round(impact, 2),
                 "drug_name": self.products.get(ndc, DrugProduct(ndc, ndc, "", "", "", "", "")).drug_name}
                for ndc, impact in top_negative
            ],
            "recommendations": self._generate_weekly_recommendations(recent_alerts)
        }

    def _generate_weekly_recommendations(self, alerts: List[VarianceAlert]) -> List[str]:
        """Generate actionable recommendations from weekly alerts."""
        recs = []
        underwater = [a for a in alerts if a.alert_type == "underwater_claim"]
        if underwater:
            total_loss = sum(abs(a.monthly_impact) for a in underwater if a.monthly_impact)
            recs.append(f"Review {len(underwater)} underwater claims totaling ${total_loss:.2f}/month in projected losses")

        high_increases = [a for a in alerts if a.alert_type == "price_increase" and a.severity in (AlertSeverity.HIGH, AlertSeverity.CRITICAL)]
        if high_increases:
            recs.append(f"Evaluate {len(high_increases)} significant price increases for therapeutic alternatives")

        decreases = [a for a in alerts if a.alert_type == "price_decrease_opportunity"]
        if decreases:
            recs.append(f"Capitalize on {len(decreases)} price decrease opportunities to improve margins")

        return recs


if __name__ == "__main__":
    system = NADACVarianceAlertSystem()

    # Register products
    metformin = DrugProduct(
        ndc="00093-7214-01", drug_name="Metformin HCl 500mg Tab",
        generic_name="metformin", strength="500mg", dosage_form="tablet",
        package_size="1000", manufacturer="Teva", therapeutic_class="Antidiabetic"
    )
    lisinopril = DrugProduct(
        ndc="00185-0145-01", drug_name="Lisinopril 10mg Tab",
        generic_name="lisinopril", strength="10mg", dosage_form="tablet",
        package_size="1000", manufacturer="Sandoz", therapeutic_class="ACE Inhibitor"
    )
    system.register_product(metformin)
    system.register_product(lisinopril)

    # Set volumes
    system.set_dispensing_volume("00093-7214-01", 5000)
    system.set_dispensing_volume("00185-0145-01", 3000)

    # Set reimbursement rates
    system.set_reimbursement_rate(ReimbursementRate(
        ndc="00093-7214-01", payer_id="BCBS", payer_name="Blue Cross Blue Shield",
        rate_per_unit=0.0350, dispensing_fee=1.75, rate_type="NADAC+"
    ))

    # Simulate NADAC price history + spike
    for i, price in enumerate([0.0280, 0.0285, 0.0290, 0.0295, 0.0300, 0.0500]):
        nadac = NADACPrice(
            ndc="00093-7214-01",
            effective_date=f"2026-0{i+1}-01",
            nadac_per_unit=price
        )
        alerts = system.update_nadac_price(nadac)
        if alerts:
            for a in alerts:
                print(f"  ALERT [{a.severity.value}]: {a.message}")

    # Summary
    print("\n--- Weekly Summary ---")
    summary = system.generate_weekly_summary()
    print(json.dumps(summary, indent=2))
