"""
Claim Pattern Detector - Advanced Pattern Recognition for Pharmacy Claims
Identifies underpayment patterns, denial trends, and reimbursement anomalies
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

class ClaimPatternDetector:
    def __init__(self):
        self.patterns = []
        self.detection_rules = self._load_detection_rules()
        self.pattern_history = defaultdict(list)
        self.thresholds = {
            "underpayment_percentage": 10.0,  # % below expected
            "denial_rate_threshold": 15.0,  # % denial rate
            "pattern_confidence_min": 0.75,
            "sample_size_min": 10
        }
    
    def _load_detection_rules(self) -> Dict:
        """Load pattern detection rules"""
        return {
            "underpayment_patterns": [
                {
                    "name": "systematic_mac_underpayment",
                    "description": "Claims consistently reimbursed below MAC pricing",
                    "severity": "high",
                    "indicators": ["mac_price", "reimbursed_amount"]
                },
                {
                    "name": "generic_substitution_shorting",
                    "description": "Generic substitutions reimbursed at lower rates than expected",
                    "severity": "high",
                    "indicators": ["is_generic", "awp_discount"]
                },
                {
                    "name": "dir_fee_escalation",
                    "description": "DIR fees increasing disproportionately",
                    "severity": "medium",
                    "indicators": ["dir_fee", "time_trend"]
                }
            ],
            "denial_patterns": [
                {
                    "name": "specific_drug_denials",
                    "description": "Specific drugs consistently denied",
                    "severity": "high",
                    "indicators": ["ndc", "denial_rate"]
                },
                {
                    "name": "time_based_denials",
                    "description": "Denials clustered at specific times",
                    "severity": "medium",
                    "indicators": ["submission_time", "denial_rate"]
                },
                {
                    "name": "payer_specific_denials",
                    "description": "One payer denying at abnormal rates",
                    "severity": "high",
                    "indicators": ["payer_id", "denial_rate"]
                }
            ],
            "reimbursement_anomalies": [
                {
                    "name": "sudden_rate_change",
                    "description": "Abrupt change in reimbursement rates",
                    "severity": "high",
                    "indicators": ["rate_volatility", "time_series"]
                },
                {
                    "name": "benchmark_deviation",
                    "description": "Reimbursement deviating from industry benchmarks",
                    "severity": "medium",
                    "indicators": ["benchmark_comparison"]
                }
            ]
        }
    
    def analyze_claims(self, claims: List[Dict], timeframe_days: int = 90) -> Dict:
        """Analyze claims for patterns"""
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        
        # Filter recent claims
        recent_claims = [c for c in claims 
                        if datetime.fromisoformat(c.get("date", datetime.now().isoformat())) >= cutoff_date]
        
        if len(recent_claims) < self.thresholds["sample_size_min"]:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {self.thresholds['sample_size_min']} claims"
            }
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "claims_analyzed": len(recent_claims),
            "timeframe_days": timeframe_days,
            "patterns_detected": [],
            "severity_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "financial_impact": 0.0,
            "recommendations": []
        }
        
        # Detect underpayment patterns
        underpayment_patterns = self._detect_underpayment_patterns(recent_claims)
        analysis["patterns_detected"].extend(underpayment_patterns)
        
        # Detect denial patterns
        denial_patterns = self._detect_denial_patterns(recent_claims)
        analysis["patterns_detected"].extend(denial_patterns)
        
        # Detect reimbursement anomalies
        anomalies = self._detect_reimbursement_anomalies(recent_claims)
        analysis["patterns_detected"].extend(anomalies)
        
        # Calculate severity summary
        for pattern in analysis["patterns_detected"]:
            severity = pattern.get("severity", "low")
            analysis["severity_summary"][severity] = analysis["severity_summary"].get(severity, 0) + 1
        
        # Calculate financial impact
        analysis["financial_impact"] = sum(p.get("estimated_loss", 0) 
                                          for p in analysis["patterns_detected"])
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis["patterns_detected"])
        
        return analysis
    
    def _detect_underpayment_patterns(self, claims: List[Dict]) -> List[Dict]:
        """Detect systematic underpayment patterns"""
        patterns = []
        
        # Group by NDC
        ndc_groups = defaultdict(list)
        for claim in claims:
            ndc = claim.get("ndc", "unknown")
            ndc_groups[ndc].append(claim)
        
        # Analyze each NDC for underpayment
        for ndc, ndc_claims in ndc_groups.items():
            if len(ndc_claims) < 5:
                continue
            
            underpaid_count = 0
            total_underpayment = 0.0
            
            for claim in ndc_claims:
                expected = claim.get("expected_reimbursement", 0)
                actual = claim.get("actual_reimbursement", 0)
                
                if expected > 0:
                    diff_pct = ((expected - actual) / expected) * 100
                    if diff_pct > self.thresholds["underpayment_percentage"]:
                        underpaid_count += 1
                        total_underpayment += (expected - actual)
            
            if underpaid_count >= len(ndc_claims) * 0.5:  # 50% or more underpaid
                patterns.append({
                    "type": "systematic_underpayment",
                    "pattern_id": f"under_{ndc}",
                    "ndc": ndc,
                    "severity": "high",
                    "confidence": underpaid_count / len(ndc_claims),
                    "affected_claims": underpaid_count,
                    "total_claims": len(ndc_claims),
                    "estimated_loss": total_underpayment,
                    "description": f"NDC {ndc} consistently underpaid ({underpaid_count}/{len(ndc_claims)} claims)",
                    "recommendation": "Submit reprocessing requests with MAC pricing documentation"
                })
        
        # Detect MAC-based underpayment
        mac_underpayment = self._detect_mac_underpayment(claims)
        if mac_underpayment:
            patterns.append(mac_underpayment)
        
        # Detect generic substitution issues
        generic_issues = self._detect_generic_substitution_issues(claims)
        if generic_issues:
            patterns.append(generic_issues)
        
        return patterns
    
    def _detect_mac_underpayment(self, claims: List[Dict]) -> Optional[Dict]:
        """Detect MAC pricing underpayment"""
        mac_claims = [c for c in claims if c.get("mac_price")]
        if len(mac_claims) < 10:
            return None
        
        underpaid_count = 0
        total_shortfall = 0.0
        
        for claim in mac_claims:
            mac_price = claim.get("mac_price", 0)
            actual = claim.get("actual_reimbursement", 0)
            
            # MAC should be the floor for reimbursement
            if actual < mac_price * 0.95:  # 5% tolerance
                underpaid_count += 1
                total_shortfall += (mac_price - actual)
        
        if underpaid_count >= len(mac_claims) * 0.3:  # 30% threshold
            return {
                "type": "mac_underpayment",
                "pattern_id": "mac_under_001",
                "severity": "high",
                "confidence": underpaid_count / len(mac_claims),
                "affected_claims": underpaid_count,
                "total_claims": len(mac_claims),
                "estimated_loss": total_shortfall,
                "description": f"Claims reimbursed below MAC pricing ({underpaid_count}/{len(mac_claims)})",
                "recommendation": "Challenge reimbursements below MAC with NADAC documentation"
            }
        
        return None
    
    def _detect_generic_substitution_issues(self, claims: List[Dict]) -> Optional[Dict]:
        """Detect generic substitution underpayment"""
        generic_claims = [c for c in claims if c.get("is_generic")]
        if len(generic_claims) < 10:
            return None
        
        # Compare generic reimbursement to brand baseline
        brand_claims = [c for c in claims if not c.get("is_generic")]
        if not brand_claims:
            return None
        
        avg_generic_margin = statistics.mean(
            c.get("profit_margin", 0) for c in generic_claims
        )
        avg_brand_margin = statistics.mean(
            c.get("profit_margin", 0) for c in brand_claims
        )
        
        # Generics should have better margins
        if avg_generic_margin < avg_brand_margin * 0.7:  # 30% worse
            total_loss = sum(
                (avg_brand_margin * 0.7 - c.get("profit_margin", 0)) 
                for c in generic_claims
            )
            
            return {
                "type": "generic_substitution_underpayment",
                "pattern_id": "gen_sub_001",
                "severity": "high",
                "confidence": 0.8,
                "affected_claims": len(generic_claims),
                "estimated_loss": total_loss,
                "description": f"Generic margins ({avg_generic_margin:.1f}%) lower than expected",
                "recommendation": "Review generic pricing agreements with payers"
            }
        
        return None
    
    def _detect_denial_patterns(self, claims: List[Dict]) -> List[Dict]:
        """Detect claim denial patterns"""
        patterns = []
        
        # Overall denial rate
        denied_claims = [c for c in claims if c.get("status") == "denied"]
        denial_rate = (len(denied_claims) / len(claims)) * 100 if claims else 0
        
        if denial_rate > self.thresholds["denial_rate_threshold"]:
            patterns.append({
                "type": "high_denial_rate",
                "pattern_id": "denial_rate_001",
                "severity": "high",
                "confidence": 0.95,
                "denial_rate": denial_rate,
                "affected_claims": len(denied_claims),
                "description": f"Overall denial rate ({denial_rate:.1f}%) exceeds threshold",
                "recommendation": "Conduct comprehensive denial audit"
            })
        
        # Payer-specific denials
        payer_denials = self._detect_payer_specific_denials(claims)
        patterns.extend(payer_denials)
        
        # Time-based denial patterns
        time_patterns = self._detect_time_based_denials(claims)
        patterns.extend(time_patterns)
        
        # Drug-specific denials
        drug_denials = self._detect_drug_specific_denials(claims)
        patterns.extend(drug_denials)
        
        return patterns
    
    def _detect_payer_specific_denials(self, claims: List[Dict]) -> List[Dict]:
        """Detect payer-specific denial patterns"""
        patterns = []
        
        # Group by payer
        payer_groups = defaultdict(list)
        for claim in claims:
            payer = claim.get("payer_id", "unknown")
            payer_groups[payer].append(claim)
        
        # Analyze each payer
        for payer, payer_claims in payer_groups.items():
            if len(payer_claims) < 10:
                continue
            
            denied = sum(1 for c in payer_claims if c.get("status") == "denied")
            denial_rate = (denied / len(payer_claims)) * 100
            
            if denial_rate > self.thresholds["denial_rate_threshold"] * 1.5:
                patterns.append({
                    "type": "payer_specific_denials",
                    "pattern_id": f"payer_denial_{payer}",
                    "payer_id": payer,
                    "severity": "high",
                    "confidence": 0.9,
                    "denial_rate": denial_rate,
                    "affected_claims": denied,
                    "total_claims": len(payer_claims),
                    "description": f"Payer {payer} has {denial_rate:.1f}% denial rate",
                    "recommendation": "Review payer contract and submission requirements"
                })
        
        return patterns
    
    def _detect_time_based_denials(self, claims: List[Dict]) -> List[Dict]:
        """Detect time-based denial patterns"""
        patterns = []
        
        # Group by hour of day
        hour_denials = defaultdict(lambda: {"total": 0, "denied": 0})
        
        for claim in claims:
            date_str = claim.get("submission_date", "")
            try:
                dt = datetime.fromisoformat(date_str)
                hour = dt.hour
                hour_denials[hour]["total"] += 1
                if claim.get("status") == "denied":
                    hour_denials[hour]["denied"] += 1
            except:
                continue
        
        # Find problematic hours
        for hour, stats in hour_denials.items():
            if stats["total"] < 5:
                continue
            
            denial_rate = (stats["denied"] / stats["total"]) * 100
            if denial_rate > self.thresholds["denial_rate_threshold"] * 2:
                patterns.append({
                    "type": "time_based_denials",
                    "pattern_id": f"time_denial_{hour}",
                    "hour": hour,
                    "severity": "medium",
                    "confidence": 0.7,
                    "denial_rate": denial_rate,
                    "affected_claims": stats["denied"],
                    "description": f"High denial rate ({denial_rate:.1f}%) during hour {hour}:00",
                    "recommendation": "Investigate system issues or payer processing windows"
                })
        
        return patterns
    
    def _detect_drug_specific_denials(self, claims: List[Dict]) -> List[Dict]:
        """Detect drug-specific denial patterns"""
        patterns = []
        
        # Group by NDC
        ndc_groups = defaultdict(list)
        for claim in claims:
            ndc = claim.get("ndc", "unknown")
            ndc_groups[ndc].append(claim)
        
        for ndc, ndc_claims in ndc_groups.items():
            if len(ndc_claims) < 5:
                continue
            
            denied = sum(1 for c in ndc_claims if c.get("status") == "denied")
            denial_rate = (denied / len(ndc_claims)) * 100
            
            if denial_rate > 50:  # More than half denied
                patterns.append({
                    "type": "drug_specific_denials",
                    "pattern_id": f"drug_denial_{ndc}",
                    "ndc": ndc,
                    "severity": "high",
                    "confidence": 0.85,
                    "denial_rate": denial_rate,
                    "affected_claims": denied,
                    "description": f"NDC {ndc} has {denial_rate:.1f}% denial rate",
                    "recommendation": "Check formulary status and prior authorization requirements"
                })
        
        return patterns
    
    def _detect_reimbursement_anomalies(self, claims: List[Dict]) -> List[Dict]:
        """Detect reimbursement anomalies"""
        patterns = []
        
        # Sort claims by date
        sorted_claims = sorted(claims, 
                              key=lambda c: c.get("date", ""),
                              reverse=False)
        
        if len(sorted_claims) < 30:
            return patterns
        
        # Calculate moving average of reimbursement rates
        window_size = 10
        rates = [c.get("reimbursement_rate", 0) for c in sorted_claims]
        
        for i in range(window_size, len(rates)):
            window = rates[i-window_size:i]
            avg = statistics.mean(window)
            current = rates[i]
            
            # Detect sudden drops
            if current < avg * 0.85:  # 15% drop
                patterns.append({
                    "type": "sudden_rate_drop",
                    "pattern_id": f"rate_drop_{i}",
                    "severity": "medium",
                    "confidence": 0.75,
                    "drop_percentage": ((avg - current) / avg) * 100,
                    "description": f"Sudden {((avg - current) / avg) * 100:.1f}% drop in reimbursement rate",
                    "recommendation": "Investigate payer rate changes or claim submission issues"
                })
                break  # Only report first major drop
        
        return patterns
    
    def _generate_recommendations(self, patterns: List[Dict]) -> List[Dict]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Prioritize by severity and financial impact
        sorted_patterns = sorted(patterns, 
                                key=lambda p: (
                                    {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(p.get("severity", "low"), 0),
                                    p.get("estimated_loss", 0)
                                ),
                                reverse=True)
        
        for i, pattern in enumerate(sorted_patterns[:5], 1):  # Top 5
            recommendations.append({
                "priority": i,
                "pattern_type": pattern["type"],
                "action": pattern.get("recommendation", "Review pattern details"),
                "estimated_recovery": pattern.get("estimated_loss", 0),
                "urgency": pattern.get("severity", "medium")
            })
        
        return recommendations

# Example usage
if __name__ == "__main__":
    detector = ClaimPatternDetector()
    
    # Sample claims
    sample_claims = [
        {
            "ndc": "12345-678-90",
            "expected_reimbursement": 100.0,
            "actual_reimbursement": 85.0,
            "mac_price": 95.0,
            "status": "paid",
            "date": "2024-03-01T10:00:00"
        }
    ] * 20
    
    analysis = detector.analyze_claims(sample_claims)
    print(json.dumps(analysis, indent=2))
