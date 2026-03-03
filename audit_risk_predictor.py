"""
Audit Risk Predictor for GetPaidRx
Predicts likelihood of pharmacy audits and identifies high-risk claim patterns
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics


@dataclass
class ClaimRecord:
    """Individual claim record"""
    claim_id: str
    rx_number: str
    ndc: str
    drug_name: str
    prescriber_npi: str
    patient_id: str
    quantity: float
    days_supply: int
    fill_date: str
    payer: str
    paid_amount: float
    is_controlled: bool = False
    is_early_refill: bool = False
    is_high_dose: bool = False


@dataclass
class AuditRiskFactor:
    """Individual risk factor"""
    factor_type: str
    description: str
    severity: str  # low, medium, high, critical
    risk_score: int  # 0-100
    evidence: List[str]


class AuditRiskPredictor:
    """
    Predicts audit risk based on:
    - Controlled substance patterns
    - Early refill frequency
    - High-dose prescriptions
    - Prescriber patterns
    - Patient patterns
    - Billing anomalies
    """
    
    def __init__(self):
        self.claims: List[ClaimRecord] = []
        self.risk_thresholds = {
            "early_refill_rate": 15.0,  # % of prescriptions
            "controlled_volume": 20.0,   # % of total claims
            "high_dose_rate": 10.0,      # % of claims
            "single_prescriber_concentration": 30.0,  # % from one prescriber
        }
    
    def add_claim(self, claim: ClaimRecord):
        """Add a claim to analysis dataset"""
        self.claims.append(claim)
    
    def assess_overall_risk(self, days: int = 90) -> Dict[str, Any]:
        """
        Comprehensive audit risk assessment
        
        Args:
            days: Analysis period in days
        
        Returns:
            Overall risk profile and score
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_claims = [
            c for c in self.claims
            if datetime.fromisoformat(c.fill_date) > cutoff
        ]
        
        if not recent_claims:
            return {"message": "No claims in analysis period"}
        
        # Collect all risk factors
        risk_factors = []
        
        # Factor 1: Controlled substance volume
        controlled_claims = [c for c in recent_claims if c.is_controlled]
        controlled_rate = (len(controlled_claims) / len(recent_claims)) * 100
        
        if controlled_rate > self.risk_thresholds["controlled_volume"]:
            risk_factors.append(AuditRiskFactor(
                factor_type="controlled_substance_volume",
                description=f"High controlled substance volume: {controlled_rate:.1f}%",
                severity="high" if controlled_rate > 30 else "medium",
                risk_score=int(min(100, controlled_rate * 2)),
                evidence=[f"{len(controlled_claims)} controlled substance claims out of {len(recent_claims)} total"]
            ))
        
        # Factor 2: Early refill rate
        early_refills = [c for c in recent_claims if c.is_early_refill]
        early_refill_rate = (len(early_refills) / len(recent_claims)) * 100
        
        if early_refill_rate > self.risk_thresholds["early_refill_rate"]:
            risk_factors.append(AuditRiskFactor(
                factor_type="early_refill_pattern",
                description=f"Excessive early refills: {early_refill_rate:.1f}%",
                severity="high",
                risk_score=int(min(100, early_refill_rate * 3)),
                evidence=[f"{len(early_refills)} early refills detected"]
            ))
        
        # Factor 3: High-dose prescriptions
        high_dose_claims = [c for c in recent_claims if c.is_high_dose]
        high_dose_rate = (len(high_dose_claims) / len(recent_claims)) * 100
        
        if high_dose_rate > self.risk_thresholds["high_dose_rate"]:
            risk_factors.append(AuditRiskFactor(
                factor_type="high_dose_pattern",
                description=f"High rate of high-dose prescriptions: {high_dose_rate:.1f}%",
                severity="medium",
                risk_score=int(min(100, high_dose_rate * 4)),
                evidence=[f"{len(high_dose_claims)} high-dose prescriptions"]
            ))
        
        # Factor 4: Prescriber concentration
        prescriber_counts = {}
        for claim in recent_claims:
            prescriber_counts[claim.prescriber_npi] = prescriber_counts.get(claim.prescriber_npi, 0) + 1
        
        if prescriber_counts:
            max_prescriber_count = max(prescriber_counts.values())
            max_prescriber_pct = (max_prescriber_count / len(recent_claims)) * 100
            
            if max_prescriber_pct > self.risk_thresholds["single_prescriber_concentration"]:
                risk_factors.append(AuditRiskFactor(
                    factor_type="prescriber_concentration",
                    description=f"High concentration from single prescriber: {max_prescriber_pct:.1f}%",
                    severity="medium",
                    risk_score=int(min(100, max_prescriber_pct * 2)),
                    evidence=[f"{max_prescriber_count} claims from single prescriber"]
                ))
        
        # Factor 5: Patient concentration (pill mill pattern)
        patient_counts = {}
        for claim in recent_claims:
            if claim.is_controlled:
                patient_counts[claim.patient_id] = patient_counts.get(claim.patient_id, 0) + 1
        
        high_volume_patients = {pid: count for pid, count in patient_counts.items() if count > 5}
        
        if high_volume_patients:
            risk_factors.append(AuditRiskFactor(
                factor_type="patient_pattern",
                description=f"{len(high_volume_patients)} patients with >5 controlled substance fills",
                severity="high",
                risk_score=len(high_volume_patients) * 10,
                evidence=[f"Patient {pid}: {count} controlled fills" for pid, count in list(high_volume_patients.items())[:5]]
            ))
        
        # Calculate overall risk score (0-100)
        if risk_factors:
            overall_score = min(100, sum(rf.risk_score for rf in risk_factors) // len(risk_factors))
        else:
            overall_score = 0
        
        # Determine risk level
        if overall_score >= 75:
            risk_level = "CRITICAL"
        elif overall_score >= 50:
            risk_level = "HIGH"
        elif overall_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "analysis_period_days": days,
            "total_claims": len(recent_claims),
            "overall_risk_score": overall_score,
            "risk_level": risk_level,
            "total_risk_factors": len(risk_factors),
            "risk_factors": [
                {
                    "type": rf.factor_type,
                    "description": rf.description,
                    "severity": rf.severity,
                    "score": rf.risk_score,
                    "evidence": rf.evidence
                }
                for rf in sorted(risk_factors, key=lambda x: x.risk_score, reverse=True)
            ],
            "recommendations": self._generate_recommendations(risk_factors),
            "generated_at": datetime.now().isoformat()
        }
    
    def identify_high_risk_claims(self) -> Dict[str, Any]:
        """
        Identify individual high-risk claims
        
        Returns:
            List of claims flagged as high audit risk
        """
        high_risk_claims = []
        
        for claim in self.claims:
            risk_flags = []
            risk_score = 0
            
            # Check various risk factors
            if claim.is_controlled:
                risk_flags.append("controlled_substance")
                risk_score += 20
            
            if claim.is_early_refill:
                risk_flags.append("early_refill")
                risk_score += 30
            
            if claim.is_high_dose:
                risk_flags.append("high_dose")
                risk_score += 25
            
            if claim.quantity > 100:
                risk_flags.append("high_quantity")
                risk_score += 15
            
            if claim.paid_amount > 1000:
                risk_flags.append("high_cost")
                risk_score += 10
            
            # Flag if risk score is significant
            if risk_score >= 40:
                high_risk_claims.append({
                    "claim_id": claim.claim_id,
                    "rx_number": claim.rx_number,
                    "drug_name": claim.drug_name,
                    "fill_date": claim.fill_date,
                    "prescriber_npi": claim.prescriber_npi,
                    "patient_id": claim.patient_id,
                    "risk_score": risk_score,
                    "risk_flags": risk_flags,
                    "paid_amount": round(claim.paid_amount, 2)
                })
        
        high_risk_claims.sort(key=lambda x: x["risk_score"], reverse=True)
        
        return {
            "total_high_risk_claims": len(high_risk_claims),
            "claims": high_risk_claims[:100],  # Top 100 highest risk
            "generated_at": datetime.now().isoformat()
        }
    
    def analyze_prescriber_risk(self) -> Dict[str, Any]:
        """
        Analyze risk by prescriber
        
        Returns:
            Prescriber risk profiles
        """
        prescriber_data = {}
        
        for claim in self.claims:
            npi = claim.prescriber_npi
            
            if npi not in prescriber_data:
                prescriber_data[npi] = {
                    "total_claims": 0,
                    "controlled_claims": 0,
                    "early_refills": 0,
                    "high_dose_claims": 0,
                    "total_paid": 0,
                    "unique_patients": set()
                }
            
            prescriber_data[npi]["total_claims"] += 1
            prescriber_data[npi]["total_paid"] += claim.paid_amount
            prescriber_data[npi]["unique_patients"].add(claim.patient_id)
            
            if claim.is_controlled:
                prescriber_data[npi]["controlled_claims"] += 1
            if claim.is_early_refill:
                prescriber_data[npi]["early_refills"] += 1
            if claim.is_high_dose:
                prescriber_data[npi]["high_dose_claims"] += 1
        
        # Calculate risk scores
        prescriber_risks = []
        
        for npi, data in prescriber_data.items():
            if data["total_claims"] < 5:  # Minimum sample size
                continue
            
            controlled_rate = (data["controlled_claims"] / data["total_claims"]) * 100
            early_refill_rate = (data["early_refills"] / data["total_claims"]) * 100
            high_dose_rate = (data["high_dose_claims"] / data["total_claims"]) * 100
            
            # Calculate risk score
            risk_score = (
                (controlled_rate * 0.4) +
                (early_refill_rate * 0.4) +
                (high_dose_rate * 0.2)
            )
            
            risk_level = "HIGH" if risk_score > 30 else "MEDIUM" if risk_score > 15 else "LOW"
            
            prescriber_risks.append({
                "prescriber_npi": npi,
                "total_claims": data["total_claims"],
                "unique_patients": len(data["unique_patients"]),
                "controlled_rate_pct": round(controlled_rate, 2),
                "early_refill_rate_pct": round(early_refill_rate, 2),
                "high_dose_rate_pct": round(high_dose_rate, 2),
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "total_paid": round(data["total_paid"], 2)
            })
        
        prescriber_risks.sort(key=lambda x: x["risk_score"], reverse=True)
        
        return {
            "total_prescribers": len(prescriber_risks),
            "high_risk_prescribers": len([p for p in prescriber_risks if p["risk_level"] == "HIGH"]),
            "prescribers": prescriber_risks[:50],  # Top 50 highest risk
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_recommendations(self, risk_factors: List[AuditRiskFactor]) -> List[str]:
        """Generate actionable recommendations based on risk factors"""
        recommendations = []
        
        factor_types = {rf.factor_type for rf in risk_factors}
        
        if "controlled_substance_volume" in factor_types:
            recommendations.append("Implement enhanced controlled substance dispensing protocols")
            recommendations.append("Review all controlled substance prescriptions for medical necessity")
        
        if "early_refill_pattern" in factor_types:
            recommendations.append("Strengthen early refill verification process")
            recommendations.append("Document all early refill justifications in patient profiles")
        
        if "prescriber_concentration" in factor_types:
            recommendations.append("Review prescriber relationships and referral patterns")
            recommendations.append("Diversify prescriber network to reduce concentration risk")
        
        if "patient_pattern" in factor_types:
            recommendations.append("Implement patient profile monitoring for high-volume controlled substance users")
            recommendations.append("Consider enrolling high-risk patients in adherence monitoring programs")
        
        if not recommendations:
            recommendations.append("Continue current compliance practices")
            recommendations.append("Maintain regular audits of dispensing patterns")
        
        return recommendations


# Example usage:
# predictor = AuditRiskPredictor()
# predictor.add_claim(ClaimRecord(...))
# risk = predictor.assess_overall_risk(days=90)
# high_risk = predictor.identify_high_risk_claims()
# prescriber_risk = predictor.analyze_prescriber_risk()
