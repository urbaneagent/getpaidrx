"""
Underpayment Pattern Detector
Machine learning-ready pattern detection for systematic underpayments
"""

from typing import Dict, List, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

class UnderpaymentPatternDetector:
    """
    Detect systematic underpayment patterns across payers, drugs, and time periods
    """
    
    def __init__(self):
        self.detected_patterns = []
        self.payer_profiles = {}
        
    def analyze_claims_batch(self, claims: List[Dict]) -> Dict:
        """
        Analyze a batch of claims for underpayment patterns
        
        Args:
            claims: List of claims with structure:
                {
                    'claim_id': str,
                    'payer': str,
                    'ndc': str,
                    'drug_name': str,
                    'quantity': int,
                    'amount_paid': float,
                    'nadac_expected': float,
                    'date_filled': str,
                    'pharmacy_id': str
                }
        
        Returns:
            Comprehensive pattern analysis report
        """
        if not claims:
            return {'error': 'No claims provided'}
        
        # Group claims by various dimensions
        by_payer = self._group_by_payer(claims)
        by_drug = self._group_by_drug(claims)
        by_date = self._group_by_date(claims)
        by_pharmacy = self._group_by_pharmacy(claims)
        
        # Detect patterns in each dimension
        payer_patterns = self._detect_payer_patterns(by_payer)
        drug_patterns = self._detect_drug_patterns(by_drug)
        temporal_patterns = self._detect_temporal_patterns(by_date)
        pharmacy_patterns = self._detect_pharmacy_patterns(by_pharmacy)
        
        # Calculate aggregate statistics
        total_underpaid = sum(
            max(0, c['nadac_expected'] - c['amount_paid'])
            for c in claims
        )
        
        underpaid_claims = [
            c for c in claims
            if c['nadac_expected'] > c['amount_paid']
        ]
        
        underpayment_rate = len(underpaid_claims) / len(claims) * 100
        
        # Identify high-priority targets
        recovery_targets = self._identify_recovery_targets(
            payer_patterns,
            drug_patterns,
            total_underpaid
        )
        
        return {
            'summary': {
                'total_claims_analyzed': len(claims),
                'underpaid_claims': len(underpaid_claims),
                'underpayment_rate': round(underpayment_rate, 2),
                'total_underpaid_amount': round(total_underpaid, 2),
                'avg_underpayment_per_claim': round(
                    total_underpaid / len(underpaid_claims), 2
                ) if underpaid_claims else 0
            },
            'payer_patterns': payer_patterns,
            'drug_patterns': drug_patterns,
            'temporal_patterns': temporal_patterns,
            'pharmacy_patterns': pharmacy_patterns,
            'recovery_targets': recovery_targets,
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
    
    def _group_by_payer(self, claims: List[Dict]) -> Dict[str, List[Dict]]:
        """Group claims by payer"""
        grouped = defaultdict(list)
        for claim in claims:
            grouped[claim['payer']].append(claim)
        return dict(grouped)
    
    def _group_by_drug(self, claims: List[Dict]) -> Dict[str, List[Dict]]:
        """Group claims by NDC"""
        grouped = defaultdict(list)
        for claim in claims:
            grouped[claim['ndc']].append(claim)
        return dict(grouped)
    
    def _group_by_date(self, claims: List[Dict]) -> Dict[str, List[Dict]]:
        """Group claims by month"""
        grouped = defaultdict(list)
        for claim in claims:
            # Extract YYYY-MM from date
            month = claim['date_filled'][:7]
            grouped[month].append(claim)
        return dict(grouped)
    
    def _group_by_pharmacy(self, claims: List[Dict]) -> Dict[str, List[Dict]]:
        """Group claims by pharmacy"""
        grouped = defaultdict(list)
        for claim in claims:
            grouped[claim['pharmacy_id']].append(claim)
        return dict(grouped)
    
    def _detect_payer_patterns(self, by_payer: Dict[str, List[Dict]]) -> List[Dict]:
        """Detect systematic underpayment patterns by payer"""
        patterns = []
        
        for payer, claims in by_payer.items():
            underpaid = [
                c for c in claims
                if c['nadac_expected'] > c['amount_paid']
            ]
            
            if not underpaid:
                continue
            
            underpayment_rate = len(underpaid) / len(claims) * 100
            
            total_underpaid = sum(
                c['nadac_expected'] - c['amount_paid']
                for c in underpaid
            )
            
            avg_underpayment = total_underpaid / len(underpaid)
            
            # Calculate underpayment percentages
            underpayment_pcts = [
                ((c['nadac_expected'] - c['amount_paid']) / c['nadac_expected'] * 100)
                for c in underpaid
                if c['nadac_expected'] > 0
            ]
            
            avg_underpayment_pct = statistics.mean(underpayment_pcts) if underpayment_pcts else 0
            
            # Detect if pattern is systematic (>50% of claims underpaid)
            is_systematic = underpayment_rate > 50
            
            # Severity assessment
            if underpayment_rate > 80 and avg_underpayment_pct > 10:
                severity = 'Critical'
            elif underpayment_rate > 50 and avg_underpayment_pct > 5:
                severity = 'High'
            elif underpayment_rate > 30:
                severity = 'Medium'
            else:
                severity = 'Low'
            
            pattern = {
                'payer': payer,
                'total_claims': len(claims),
                'underpaid_claims': len(underpaid),
                'underpayment_rate': round(underpayment_rate, 2),
                'total_underpaid_amount': round(total_underpaid, 2),
                'avg_underpayment_per_claim': round(avg_underpayment, 2),
                'avg_underpayment_percentage': round(avg_underpayment_pct, 2),
                'is_systematic': is_systematic,
                'severity': severity,
                'recommendation': self._generate_payer_recommendation(
                    payer,
                    severity,
                    underpayment_rate,
                    total_underpaid
                )
            }
            
            patterns.append(pattern)
            
            # Store payer profile
            self.payer_profiles[payer] = pattern
        
        # Sort by total underpaid amount (highest first)
        patterns.sort(key=lambda x: x['total_underpaid_amount'], reverse=True)
        
        return patterns
    
    def _detect_drug_patterns(self, by_drug: Dict[str, List[Dict]]) -> List[Dict]:
        """Detect drugs that are consistently underpaid"""
        patterns = []
        
        for ndc, claims in by_drug.items():
            if len(claims) < 3:  # Need at least 3 claims for pattern
                continue
            
            underpaid = [
                c for c in claims
                if c['nadac_expected'] > c['amount_paid']
            ]
            
            if not underpaid:
                continue
            
            underpayment_rate = len(underpaid) / len(claims) * 100
            
            if underpayment_rate < 60:  # Only flag if >60% underpaid
                continue
            
            total_underpaid = sum(
                c['nadac_expected'] - c['amount_paid']
                for c in underpaid
            )
            
            # Get drug name from first claim
            drug_name = claims[0].get('drug_name', 'Unknown')
            
            # Identify which payers underpay this drug
            payers_underpaying = set(c['payer'] for c in underpaid)
            
            pattern = {
                'ndc': ndc,
                'drug_name': drug_name,
                'total_claims': len(claims),
                'underpaid_claims': len(underpaid),
                'underpayment_rate': round(underpayment_rate, 2),
                'total_underpaid_amount': round(total_underpaid, 2),
                'payers_underpaying': list(payers_underpaying),
                'recommendation': f"Review pricing for {drug_name} across all payers"
            }
            
            patterns.append(pattern)
        
        # Sort by underpayment rate
        patterns.sort(key=lambda x: x['underpayment_rate'], reverse=True)
        
        return patterns[:20]  # Top 20 drugs
    
    def _detect_temporal_patterns(self, by_date: Dict[str, List[Dict]]) -> Dict:
        """Detect time-based underpayment patterns"""
        monthly_stats = []
        
        for month, claims in sorted(by_date.items()):
            underpaid = [
                c for c in claims
                if c['nadac_expected'] > c['amount_paid']
            ]
            
            total_underpaid = sum(
                c['nadac_expected'] - c['amount_paid']
                for c in underpaid
            )
            
            monthly_stats.append({
                'month': month,
                'total_claims': len(claims),
                'underpaid_claims': len(underpaid),
                'underpayment_rate': round(len(underpaid) / len(claims) * 100, 2) if claims else 0,
                'total_underpaid': round(total_underpaid, 2)
            })
        
        # Detect trend
        if len(monthly_stats) >= 3:
            recent_months = monthly_stats[-3:]
            rates = [m['underpayment_rate'] for m in recent_months]
            
            if all(rates[i] < rates[i+1] for i in range(len(rates)-1)):
                trend = 'worsening'
            elif all(rates[i] > rates[i+1] for i in range(len(rates)-1)):
                trend = 'improving'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'monthly_breakdown': monthly_stats,
            'trend': trend,
            'avg_monthly_underpayment': round(
                statistics.mean([m['total_underpaid'] for m in monthly_stats]), 2
            ) if monthly_stats else 0
        }
    
    def _detect_pharmacy_patterns(self, by_pharmacy: Dict[str, List[Dict]]) -> List[Dict]:
        """Detect if specific pharmacies are more affected"""
        patterns = []
        
        for pharmacy_id, claims in by_pharmacy.items():
            underpaid = [
                c for c in claims
                if c['nadac_expected'] > c['amount_paid']
            ]
            
            total_underpaid = sum(
                c['nadac_expected'] - c['amount_paid']
                for c in underpaid
            )
            
            patterns.append({
                'pharmacy_id': pharmacy_id,
                'total_claims': len(claims),
                'underpaid_claims': len(underpaid),
                'underpayment_rate': round(len(underpaid) / len(claims) * 100, 2),
                'total_underpaid': round(total_underpaid, 2)
            })
        
        # Sort by underpayment rate
        patterns.sort(key=lambda x: x['underpayment_rate'], reverse=True)
        
        return patterns
    
    def _identify_recovery_targets(
        self,
        payer_patterns: List[Dict],
        drug_patterns: List[Dict],
        total_underpaid: float
    ) -> List[Dict]:
        """Identify highest-priority recovery targets"""
        targets = []
        
        # Top 3 payers by underpayment amount
        for pattern in payer_patterns[:3]:
            targets.append({
                'type': 'payer',
                'target': pattern['payer'],
                'recovery_potential': pattern['total_underpaid_amount'],
                'priority': 'High' if pattern['severity'] in ['Critical', 'High'] else 'Medium',
                'action': f"File audit request with {pattern['payer']}"
            })
        
        # Top 3 drugs by underpayment rate
        for pattern in drug_patterns[:3]:
            targets.append({
                'type': 'drug',
                'target': pattern['drug_name'],
                'recovery_potential': pattern['total_underpaid_amount'],
                'priority': 'Medium',
                'action': f"Review pricing agreements for {pattern['drug_name']}"
            })
        
        # Sort by recovery potential
        targets.sort(key=lambda x: x['recovery_potential'], reverse=True)
        
        return targets[:5]  # Top 5 targets
    
    def _generate_payer_recommendation(
        self,
        payer: str,
        severity: str,
        rate: float,
        amount: float
    ) -> str:
        """Generate actionable recommendation for payer"""
        if severity == 'Critical':
            return (
                f"🚨 CRITICAL: {payer} underpays {rate:.0f}% of claims. "
                f"Total exposure: ${amount:,.2f}. "
                f"Immediate audit and contract renegotiation required."
            )
        elif severity == 'High':
            return (
                f"⚠️ HIGH: {payer} shows systematic underpayment pattern. "
                f"Recovery potential: ${amount:,.2f}. "
                f"Schedule meeting with payer contract manager."
            )
        elif severity == 'Medium':
            return (
                f"📊 MEDIUM: {payer} has moderate underpayment issues. "
                f"Monitor closely and document all discrepancies."
            )
        else:
            return f"✅ LOW: {payer} payment accuracy is acceptable."
    
    def export_for_audit(self, patterns: Dict) -> str:
        """Export patterns in audit-ready format"""
        lines = []
        lines.append("UNDERPAYMENT AUDIT REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")
        
        summary = patterns['summary']
        lines.append("EXECUTIVE SUMMARY")
        lines.append(f"Total Claims Analyzed: {summary['total_claims_analyzed']:,}")
        lines.append(f"Underpaid Claims: {summary['underpaid_claims']:,}")
        lines.append(f"Underpayment Rate: {summary['underpayment_rate']}%")
        lines.append(f"Total Recovery Potential: ${summary['total_underpaid_amount']:,.2f}")
        lines.append("")
        
        lines.append("TOP RECOVERY TARGETS")
        lines.append("-" * 60)
        for i, target in enumerate(patterns['recovery_targets'], 1):
            lines.append(f"{i}. {target['type'].upper()}: {target['target']}")
            lines.append(f"   Recovery: ${target['recovery_potential']:,.2f}")
            lines.append(f"   Action: {target['action']}")
            lines.append("")
        
        return "\n".join(lines)

