"""
Automated Claim Reconciliation
Real-time claim validation and discrepancy detection
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

class DiscrepancyType(Enum):
    UNDERPAYMENT = "underpayment"
    OVERPAYMENT = "overpayment"
    MISSING_PAYMENT = "missing_payment"
    INCORRECT_QUANTITY = "incorrect_quantity"
    WRONG_NDC = "wrong_ndc"
    DENIED_CLAIM = "denied_claim"
    PARTIAL_PAYMENT = "partial_payment"

class AutomatedClaimReconciliation:
    """
    Automated reconciliation between submitted claims and received payments
    """
    
    TOLERANCE_CENTS = 5  # Allow 5 cent tolerance for rounding
    
    def __init__(self):
        self.reconciliation_history = []
        self.unmatched_claims = []
        self.unmatched_payments = []
        
    def reconcile_batch(
        self,
        submitted_claims: List[Dict],
        received_payments: List[Dict]
    ) -> Dict:
        """
        Reconcile submitted claims against received payments
        
        Args:
            submitted_claims: Claims submitted to payers
                {
                    'claim_id': str,
                    'rx_number': str,
                    'patient_id': str,
                    'payer': str,
                    'ndc': str,
                    'quantity': int,
                    'submitted_amount': float,
                    'expected_payment': float,
                    'submission_date': str,
                    'pharmacy_id': str
                }
            
            received_payments: Payments received from payers
                {
                    'payment_id': str,
                    'claim_id': Optional[str],
                    'rx_number': Optional[str],
                    'payer': str,
                    'amount_paid': float,
                    'payment_date': str,
                    'adjustment_code': Optional[str],
                    'denial_reason': Optional[str]
                }
        
        Returns:
            Complete reconciliation report with discrepancies
        """
        # Initialize tracking
        matched_pairs = []
        discrepancies = []
        self.unmatched_claims = []
        self.unmatched_payments = []
        
        # Create lookups
        claims_by_id = {c['claim_id']: c for c in submitted_claims}
        claims_by_rx = {c['rx_number']: c for c in submitted_claims}
        
        payments_processed = set()
        
        # Match payments to claims
        for payment in received_payments:
            claim = None
            
            # Try matching by claim_id first
            if payment.get('claim_id') and payment['claim_id'] in claims_by_id:
                claim = claims_by_id[payment['claim_id']]
            # Fallback to rx_number
            elif payment.get('rx_number') and payment['rx_number'] in claims_by_rx:
                claim = claims_by_rx[payment['rx_number']]
            
            if claim:
                # Matched - validate payment
                validation = self._validate_payment(claim, payment)
                
                matched_pairs.append({
                    'claim': claim,
                    'payment': payment,
                    'validation': validation
                })
                
                if validation['has_discrepancy']:
                    discrepancies.append({
                        'claim_id': claim['claim_id'],
                        'rx_number': claim['rx_number'],
                        'discrepancy_type': validation['discrepancy_type'],
                        'expected': validation['expected_amount'],
                        'actual': validation['actual_amount'],
                        'variance': validation['variance'],
                        'severity': validation['severity'],
                        'recommendation': validation['recommendation']
                    })
                
                payments_processed.add(payment['payment_id'])
            else:
                # Unmatched payment
                self.unmatched_payments.append(payment)
        
        # Find unmatched claims
        matched_claim_ids = {pair['claim']['claim_id'] for pair in matched_pairs}
        self.unmatched_claims = [
            c for c in submitted_claims
            if c['claim_id'] not in matched_claim_ids
        ]
        
        # Analyze unmatched claims (potentially missing payments)
        for claim in self.unmatched_claims:
            # Check if payment is overdue (>14 days)
            submission_date = datetime.fromisoformat(claim['submission_date'])
            days_since_submission = (datetime.now() - submission_date).days
            
            if days_since_submission > 14:
                discrepancies.append({
                    'claim_id': claim['claim_id'],
                    'rx_number': claim['rx_number'],
                    'discrepancy_type': DiscrepancyType.MISSING_PAYMENT.value,
                    'expected': claim['expected_payment'],
                    'actual': 0,
                    'variance': claim['expected_payment'],
                    'severity': 'High' if days_since_submission > 30 else 'Medium',
                    'recommendation': f"Contact {claim['payer']} - payment overdue by {days_since_submission} days"
                })
        
        # Calculate summary statistics
        total_expected = sum(c['expected_payment'] for c in submitted_claims)
        total_received = sum(p['amount_paid'] for p in received_payments)
        total_variance = total_expected - total_received
        
        reconciliation_rate = len(matched_pairs) / len(submitted_claims) * 100 if submitted_claims else 0
        
        # Categorize discrepancies by type
        discrepancy_breakdown = {}
        for disc in discrepancies:
            dtype = disc['discrepancy_type']
            if dtype not in discrepancy_breakdown:
                discrepancy_breakdown[dtype] = {
                    'count': 0,
                    'total_variance': 0
                }
            discrepancy_breakdown[dtype]['count'] += 1
            discrepancy_breakdown[dtype]['total_variance'] += abs(disc['variance'])
        
        report = {
            'summary': {
                'total_claims_submitted': len(submitted_claims),
                'total_payments_received': len(received_payments),
                'matched_pairs': len(matched_pairs),
                'reconciliation_rate': round(reconciliation_rate, 2),
                'total_expected': round(total_expected, 2),
                'total_received': round(total_received, 2),
                'total_variance': round(total_variance, 2),
                'discrepancies_found': len(discrepancies),
                'unmatched_claims': len(self.unmatched_claims),
                'unmatched_payments': len(self.unmatched_payments)
            },
            'discrepancies': discrepancies,
            'discrepancy_breakdown': discrepancy_breakdown,
            'unmatched_claims': self.unmatched_claims[:10],  # Top 10
            'unmatched_payments': self.unmatched_payments[:10],
            'priority_actions': self._generate_priority_actions(discrepancies),
            'reconciliation_timestamp': datetime.utcnow().isoformat()
        }
        
        # Store in history
        self.reconciliation_history.append({
            'timestamp': report['reconciliation_timestamp'],
            'claims': len(submitted_claims),
            'payments': len(received_payments),
            'discrepancies': len(discrepancies),
            'variance': total_variance
        })
        
        return report
    
    def _validate_payment(self, claim: Dict, payment: Dict) -> Dict:
        """Validate a payment against expected claim amount"""
        expected = claim['expected_payment']
        actual = payment['amount_paid']
        variance = expected - actual
        
        has_discrepancy = abs(variance) > (self.TOLERANCE_CENTS / 100)
        
        # Determine discrepancy type
        if not has_discrepancy:
            discrepancy_type = None
            severity = None
            recommendation = "Payment matches expected amount"
        elif actual == 0 and payment.get('denial_reason'):
            discrepancy_type = DiscrepancyType.DENIED_CLAIM.value
            severity = 'High'
            recommendation = f"Appeal denial: {payment['denial_reason']}"
        elif variance > 0:
            # Underpaid
            discrepancy_type = DiscrepancyType.UNDERPAYMENT.value
            
            underpayment_pct = (variance / expected * 100) if expected > 0 else 0
            
            if underpayment_pct > 20:
                severity = 'Critical'
                recommendation = "File immediate audit request"
            elif underpayment_pct > 10:
                severity = 'High'
                recommendation = "Request payment adjustment"
            else:
                severity = 'Medium'
                recommendation = "Monitor for pattern"
        else:
            # Overpaid (rare but possible)
            discrepancy_type = DiscrepancyType.OVERPAYMENT.value
            severity = 'Low'
            recommendation = "Document overpayment for future reconciliation"
        
        return {
            'has_discrepancy': has_discrepancy,
            'discrepancy_type': discrepancy_type,
            'expected_amount': round(expected, 2),
            'actual_amount': round(actual, 2),
            'variance': round(variance, 2),
            'variance_percentage': round((variance / expected * 100), 2) if expected > 0 else 0,
            'severity': severity,
            'recommendation': recommendation
        }
    
    def _generate_priority_actions(self, discrepancies: List[Dict]) -> List[Dict]:
        """Generate prioritized action items from discrepancies"""
        actions = []
        
        # Group by payer and discrepancy type
        by_payer = {}
        for disc in discrepancies:
            # Note: payer would need to be passed through from claim
            # For now, group by discrepancy type
            dtype = disc['discrepancy_type']
            severity = disc['severity']
            
            key = f"{dtype}_{severity}"
            if key not in by_payer:
                by_payer[key] = {
                    'type': dtype,
                    'severity': severity,
                    'count': 0,
                    'total_variance': 0,
                    'claim_ids': []
                }
            
            by_payer[key]['count'] += 1
            by_payer[key]['total_variance'] += abs(disc['variance'])
            by_payer[key]['claim_ids'].append(disc['claim_id'])
        
        # Generate actions
        for key, data in by_payer.items():
            if data['severity'] == 'Critical':
                action_priority = 'Immediate'
                action_type = 'Escalate'
            elif data['severity'] == 'High':
                action_priority = 'Urgent'
                action_type = 'Investigate'
            else:
                action_priority = 'Standard'
                action_type = 'Review'
            
            actions.append({
                'priority': action_priority,
                'action': action_type,
                'discrepancy_type': data['type'],
                'count': data['count'],
                'total_variance': round(data['total_variance'], 2),
                'affected_claims': len(data['claim_ids']),
                'description': f"{action_type} {data['count']} claims with {data['type']}"
            })
        
        # Sort by priority and variance
        priority_order = {'Immediate': 0, 'Urgent': 1, 'Standard': 2}
        actions.sort(key=lambda x: (priority_order[x['priority']], -x['total_variance']))
        
        return actions[:10]  # Top 10 actions
    
    def generate_follow_up_report(self, days_back: int = 30) -> Dict:
        """Generate follow-up report on outstanding discrepancies"""
        if not self.reconciliation_history:
            return {'message': 'No reconciliation history available'}
        
        recent_history = [
            h for h in self.reconciliation_history
            if (datetime.utcnow() - datetime.fromisoformat(h['timestamp'])).days <= days_back
        ]
        
        total_discrepancies = sum(h['discrepancies'] for h in recent_history)
        total_variance = sum(h['variance'] for h in recent_history)
        
        return {
            'period': f"Last {days_back} days",
            'reconciliations_performed': len(recent_history),
            'total_claims_processed': sum(h['claims'] for h in recent_history),
            'total_discrepancies': total_discrepancies,
            'total_variance': round(total_variance, 2),
            'avg_variance_per_reconciliation': round(
                total_variance / len(recent_history), 2
            ) if recent_history else 0,
            'outstanding_unmatched_claims': len(self.unmatched_claims),
            'outstanding_unmatched_payments': len(self.unmatched_payments),
            'recommendation': self._generate_follow_up_recommendation(
                total_discrepancies,
                total_variance
            )
        }
    
    def _generate_follow_up_recommendation(
        self,
        total_discrepancies: int,
        total_variance: float
    ) -> str:
        """Generate follow-up recommendation based on trends"""
        if total_variance > 10000:
            return (
                "🚨 CRITICAL: Significant payment discrepancies detected. "
                "Schedule immediate meeting with top payers to resolve."
            )
        elif total_variance > 5000:
            return (
                "⚠️ HIGH: Notable payment variances require attention. "
                "Prioritize audit requests for high-variance payers."
            )
        elif total_discrepancies > 50:
            return (
                "📊 MODERATE: Frequent discrepancies detected. "
                "Review claim submission process for accuracy."
            )
        else:
            return (
                "✅ ACCEPTABLE: Reconciliation within normal parameters. "
                "Continue monitoring."
            )
    
    def export_discrepancy_report(self, reconciliation_report: Dict) -> str:
        """Export reconciliation report in CSV-ready format"""
        lines = []
        lines.append("Claim ID,RX Number,Discrepancy Type,Expected,Actual,Variance,Severity,Recommendation")
        
        for disc in reconciliation_report['discrepancies']:
            lines.append(
                f"{disc['claim_id']},"
                f"{disc['rx_number']},"
                f"{disc['discrepancy_type']},"
                f"{disc['expected']:.2f},"
                f"{disc['actual']:.2f},"
                f"{disc['variance']:.2f},"
                f"{disc['severity']},"
                f"\"{disc['recommendation']}\""
            )
        
        return "\n".join(lines)

