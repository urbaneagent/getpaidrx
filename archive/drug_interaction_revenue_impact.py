"""
GetPaidRx - Drug Interaction Revenue Impact Analyzer
=====================================================
Analyzes how drug-drug interactions (DDIs) affect pharmacy revenue through
therapeutic substitutions, monitoring requirements, and claim modifications.
Maps clinical DDI severity to financial impact on reimbursement, identifies
revenue opportunities from interaction management services, and tracks
payer-specific DDI policies.

Features:
- DDI severity classification with revenue impact mapping
- Therapeutic substitution revenue modeling
- MTM (Medication Therapy Management) billing opportunity identification
- Payer DDI policy tracking and compliance scoring
- Revenue loss prevention from rejected DDI claims
- Clinical intervention documentation for billing
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import re


class DDISeverity(Enum):
    """Drug-Drug Interaction severity levels."""
    CONTRAINDICATED = "contraindicated"   # Never use together
    MAJOR = "major"                       # Serious clinical risk
    MODERATE = "moderate"                 # May need monitoring/adjustment
    MINOR = "minor"                       # Minimal clinical significance
    UNKNOWN = "unknown"


class InterventionType(Enum):
    """Types of pharmacist interventions for DDIs."""
    THERAPEUTIC_SUBSTITUTION = "therapeutic_substitution"
    DOSE_ADJUSTMENT = "dose_adjustment"
    MONITORING_ADDED = "monitoring_added"
    TIMING_SEPARATION = "timing_separation"
    PRESCRIBER_CONSULT = "prescriber_consult"
    PATIENT_COUNSELING = "patient_counseling"
    DRUG_DISCONTINUED = "drug_discontinued"
    NO_ACTION_CLINICAL_OVERRIDE = "no_action_override"


class BillingOpportunity(Enum):
    """Revenue opportunities from DDI management."""
    MTM_COMPREHENSIVE = "mtm_comprehensive"      # CPT 99605/99606
    MTM_FOLLOWUP = "mtm_followup"                # CPT 99607
    CLINICAL_CONSULT = "clinical_consult"         # State-dependent
    IMMUNIZATION_RELATED = "immunization"         # If DDI affects vaccine
    POINT_OF_CARE_TEST = "poc_test"               # Monitoring service
    MEDICATION_SYNC = "med_sync"                  # Synchronization service
    ADHERENCE_PACKAGING = "adherence_package"     # Compliance packaging


@dataclass
class DrugInteraction:
    """A specific drug-drug interaction."""
    interaction_id: str
    drug_a_ndc: str
    drug_a_name: str
    drug_b_ndc: str
    drug_b_name: str
    severity: DDISeverity
    clinical_effect: str
    mechanism: str
    management_recommendation: str
    evidence_level: str  # "established", "probable", "suspected", "possible"
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['severity'] = self.severity.value
        return result


@dataclass
class DDIClaimEvent:
    """A claim event involving a DDI."""
    claim_id: str
    patient_id: str
    interaction: DrugInteraction
    claim_date: str
    payer_id: str
    payer_name: str
    original_amount: float
    adjudicated_amount: float
    claim_status: str  # "paid", "rejected", "reversed", "pending"
    rejection_code: Optional[str] = None
    intervention_type: Optional[InterventionType] = None
    intervention_documented: bool = False
    pharmacist_id: Optional[str] = None
    revenue_impact: float = 0.0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['interaction'] = self.interaction.to_dict()
        if self.intervention_type:
            result['intervention_type'] = self.intervention_type.value
        return result


@dataclass
class RevenueOpportunity:
    """An identified revenue opportunity from DDI management."""
    opportunity_id: str
    patient_id: str
    interaction_id: str
    billing_type: BillingOpportunity
    estimated_revenue: float
    clinical_justification: str
    billing_codes: List[str]
    documentation_requirements: List[str]
    expiration_date: str
    captured: bool = False
    captured_amount: float = 0.0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['billing_type'] = self.billing_type.value
        return result


class DDIRevenueClassifier:
    """Classifies DDIs by their revenue impact potential."""
    
    # Average revenue impact by severity
    SEVERITY_REVENUE_MAP = {
        DDISeverity.CONTRAINDICATED: {
            'avg_claim_value': 185.00,
            'rejection_rate': 0.85,
            'substitution_opportunity': 0.95,
            'mtm_eligible': True,
            'monitoring_revenue': 0.0,
        },
        DDISeverity.MAJOR: {
            'avg_claim_value': 142.00,
            'rejection_rate': 0.45,
            'substitution_opportunity': 0.60,
            'mtm_eligible': True,
            'monitoring_revenue': 25.00,
        },
        DDISeverity.MODERATE: {
            'avg_claim_value': 98.00,
            'rejection_rate': 0.15,
            'substitution_opportunity': 0.30,
            'mtm_eligible': True,
            'monitoring_revenue': 15.00,
        },
        DDISeverity.MINOR: {
            'avg_claim_value': 65.00,
            'rejection_rate': 0.03,
            'substitution_opportunity': 0.05,
            'mtm_eligible': False,
            'monitoring_revenue': 0.0,
        },
    }
    
    # MTM billing rates (2026 estimates)
    MTM_RATES = {
        BillingOpportunity.MTM_COMPREHENSIVE: {
            'cpt_codes': ['99605', '99606'],
            'rate_range': (45.00, 85.00),
            'avg_rate': 65.00,
            'time_minutes': 30,
        },
        BillingOpportunity.MTM_FOLLOWUP: {
            'cpt_codes': ['99607'],
            'rate_range': (25.00, 45.00),
            'avg_rate': 35.00,
            'time_minutes': 15,
        },
        BillingOpportunity.CLINICAL_CONSULT: {
            'cpt_codes': ['99211', '99212'],
            'rate_range': (20.00, 60.00),
            'avg_rate': 40.00,
            'time_minutes': 10,
        },
        BillingOpportunity.POINT_OF_CARE_TEST: {
            'cpt_codes': ['81002', '81003', '85018'],
            'rate_range': (10.00, 35.00),
            'avg_rate': 22.00,
            'time_minutes': 5,
        },
    }
    
    def classify_revenue_impact(self, interaction: DrugInteraction,
                                 claim_value: float) -> Dict:
        """Classify the revenue impact of a DDI."""
        severity_data = self.SEVERITY_REVENUE_MAP.get(
            interaction.severity,
            self.SEVERITY_REVENUE_MAP[DDISeverity.MINOR]
        )
        
        # Calculate potential revenue loss from rejection
        rejection_loss = claim_value * severity_data['rejection_rate']
        
        # Calculate substitution revenue potential
        substitution_value = (
            claim_value * severity_data['substitution_opportunity'] * 0.85
        )
        
        # Calculate service revenue opportunities
        service_revenue = 0.0
        opportunities = []
        
        if severity_data['mtm_eligible']:
            mtm_rate = self.MTM_RATES[BillingOpportunity.MTM_COMPREHENSIVE]
            service_revenue += mtm_rate['avg_rate']
            opportunities.append({
                'type': BillingOpportunity.MTM_COMPREHENSIVE.value,
                'revenue': mtm_rate['avg_rate'],
                'codes': mtm_rate['cpt_codes'],
            })
        
        if severity_data['monitoring_revenue'] > 0:
            service_revenue += severity_data['monitoring_revenue']
            opportunities.append({
                'type': BillingOpportunity.POINT_OF_CARE_TEST.value,
                'revenue': severity_data['monitoring_revenue'],
                'codes': self.MTM_RATES[BillingOpportunity.POINT_OF_CARE_TEST]['cpt_codes'],
            })
        
        return {
            'severity': interaction.severity.value,
            'potential_rejection_loss': round(rejection_loss, 2),
            'substitution_revenue': round(substitution_value, 2),
            'service_revenue': round(service_revenue, 2),
            'net_revenue_impact': round(
                substitution_value + service_revenue - rejection_loss, 2
            ),
            'billing_opportunities': opportunities,
            'risk_level': 'high' if rejection_loss > 100 else (
                'medium' if rejection_loss > 25 else 'low'
            ),
        }


class PayerDDIPolicy:
    """Tracks payer-specific DDI handling policies."""
    
    def __init__(self):
        self.policies: Dict[str, Dict] = {}
        self.rejection_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def add_policy(self, payer_id: str, policy: Dict):
        """Add or update a payer's DDI policy."""
        self.policies[payer_id] = {
            **policy,
            'updated_at': datetime.now().isoformat(),
        }
    
    def record_rejection(self, payer_id: str, severity: DDISeverity,
                         rejection_code: str, claim_amount: float):
        """Record a DDI-related claim rejection."""
        self.rejection_history[payer_id].append({
            'severity': severity.value,
            'rejection_code': rejection_code,
            'claim_amount': claim_amount,
            'date': datetime.now().isoformat(),
        })
    
    def get_payer_rejection_rate(self, payer_id: str,
                                 severity: DDISeverity = None) -> float:
        """Calculate rejection rate for a payer, optionally by severity."""
        history = self.rejection_history.get(payer_id, [])
        if not history:
            return 0.0
        
        if severity:
            relevant = [h for h in history if h['severity'] == severity.value]
        else:
            relevant = history
        
        if not relevant:
            return 0.0
        
        return len(relevant) / max(len(history), 1)
    
    def get_payer_scorecard(self, payer_id: str) -> Dict:
        """Generate a DDI policy scorecard for a payer."""
        policy = self.policies.get(payer_id, {})
        history = self.rejection_history.get(payer_id, [])
        
        total_rejections = len(history)
        total_loss = sum(h['claim_amount'] for h in history)
        
        severity_breakdown = defaultdict(lambda: {'count': 0, 'amount': 0.0})
        for h in history:
            sev = h['severity']
            severity_breakdown[sev]['count'] += 1
            severity_breakdown[sev]['amount'] += h['claim_amount']
        
        return {
            'payer_id': payer_id,
            'policy': policy,
            'total_rejections': total_rejections,
            'total_revenue_loss': round(total_loss, 2),
            'severity_breakdown': dict(severity_breakdown),
            'avg_rejection_amount': round(
                total_loss / max(total_rejections, 1), 2
            ),
            'generated_at': datetime.now().isoformat(),
        }


class InterventionTracker:
    """Tracks pharmacist interventions for DDIs and their billing status."""
    
    def __init__(self):
        self.interventions: List[Dict] = []
        self.billing_queue: List[Dict] = []
    
    def record_intervention(self, claim_id: str, patient_id: str,
                            interaction_id: str,
                            intervention_type: InterventionType,
                            pharmacist_id: str,
                            clinical_notes: str,
                            time_spent_minutes: int) -> str:
        """Record a pharmacist intervention for a DDI."""
        intervention_id = f"INT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.interventions):04d}"
        
        record = {
            'intervention_id': intervention_id,
            'claim_id': claim_id,
            'patient_id': patient_id,
            'interaction_id': interaction_id,
            'intervention_type': intervention_type.value,
            'pharmacist_id': pharmacist_id,
            'clinical_notes': clinical_notes,
            'time_spent_minutes': time_spent_minutes,
            'documented_at': datetime.now().isoformat(),
            'billed': False,
            'billing_code': None,
            'billing_amount': None,
        }
        
        self.interventions.append(record)
        
        # Check if billable
        if intervention_type in (
            InterventionType.THERAPEUTIC_SUBSTITUTION,
            InterventionType.PRESCRIBER_CONSULT,
            InterventionType.PATIENT_COUNSELING,
        ) and time_spent_minutes >= 10:
            self.billing_queue.append({
                'intervention_id': intervention_id,
                'patient_id': patient_id,
                'suggested_code': self._suggest_billing_code(
                    intervention_type, time_spent_minutes
                ),
                'priority': 'high' if time_spent_minutes >= 30 else 'normal',
            })
        
        return intervention_id
    
    def _suggest_billing_code(self, intervention_type: InterventionType,
                               time_minutes: int) -> str:
        """Suggest appropriate billing code for intervention."""
        if time_minutes >= 30:
            return "99605"  # MTM comprehensive, initial 15 min
        elif time_minutes >= 15:
            return "99606"  # MTM comprehensive, additional 15 min
        else:
            return "99607"  # MTM targeted
    
    def get_unbilled_interventions(self) -> List[Dict]:
        """Get all interventions that haven't been billed yet."""
        return [i for i in self.interventions if not i['billed']]
    
    def get_intervention_summary(self, 
                                  start_date: str = None,
                                  end_date: str = None) -> Dict:
        """Get summary of interventions within date range."""
        filtered = self.interventions
        
        if start_date:
            filtered = [
                i for i in filtered 
                if i['documented_at'] >= start_date
            ]
        if end_date:
            filtered = [
                i for i in filtered 
                if i['documented_at'] <= end_date
            ]
        
        type_counts = defaultdict(int)
        total_time = 0
        billed_count = 0
        billed_amount = 0.0
        
        for intervention in filtered:
            type_counts[intervention['intervention_type']] += 1
            total_time += intervention['time_spent_minutes']
            if intervention['billed']:
                billed_count += 1
                billed_amount += intervention.get('billing_amount', 0) or 0
        
        return {
            'total_interventions': len(filtered),
            'by_type': dict(type_counts),
            'total_time_minutes': total_time,
            'total_time_hours': round(total_time / 60, 1),
            'billed_count': billed_count,
            'unbilled_count': len(filtered) - billed_count,
            'billed_revenue': round(billed_amount, 2),
            'capture_rate': round(
                billed_count / max(len(filtered), 1) * 100, 1
            ),
        }


class DrugInteractionRevenueAnalyzer:
    """
    Main orchestrator for Drug Interaction Revenue Impact Analysis.
    
    Combines DDI classification, payer policy tracking, intervention
    documentation, and revenue opportunity identification.
    """
    
    def __init__(self):
        self.classifier = DDIRevenueClassifier()
        self.payer_policies = PayerDDIPolicy()
        self.intervention_tracker = InterventionTracker()
        
        self.interactions_db: Dict[str, DrugInteraction] = {}
        self.claim_events: List[DDIClaimEvent] = []
        self.opportunities: List[RevenueOpportunity] = []
        self._opp_counter = 0
    
    def register_interaction(self, interaction: DrugInteraction):
        """Register a known drug interaction."""
        self.interactions_db[interaction.interaction_id] = interaction
    
    def process_ddi_claim(self, event: DDIClaimEvent) -> Dict:
        """Process a claim event involving a DDI."""
        self.claim_events.append(event)
        
        # Classify revenue impact
        impact = self.classifier.classify_revenue_impact(
            event.interaction, event.original_amount
        )
        
        # Track rejection if applicable
        if event.claim_status == 'rejected' and event.rejection_code:
            self.payer_policies.record_rejection(
                event.payer_id,
                event.interaction.severity,
                event.rejection_code,
                event.original_amount,
            )
        
        # Identify billing opportunities
        billing_opps = self._identify_billing_opportunities(event)
        
        # Calculate total revenue at risk
        event.revenue_impact = impact['net_revenue_impact']
        
        return {
            'claim_id': event.claim_id,
            'revenue_impact': impact,
            'billing_opportunities': [o.to_dict() for o in billing_opps],
            'payer_rejection_rate': self.payer_policies.get_payer_rejection_rate(
                event.payer_id, event.interaction.severity
            ),
            'recommended_action': self._recommend_action(event, impact),
        }
    
    def _identify_billing_opportunities(
        self, event: DDIClaimEvent
    ) -> List[RevenueOpportunity]:
        """Identify billable opportunities from a DDI claim event."""
        opps = []
        
        # MTM opportunity for major/contraindicated
        if event.interaction.severity in (
            DDISeverity.CONTRAINDICATED, DDISeverity.MAJOR
        ):
            self._opp_counter += 1
            opp = RevenueOpportunity(
                opportunity_id=f"OPP-{self._opp_counter:06d}",
                patient_id=event.patient_id,
                interaction_id=event.interaction.interaction_id,
                billing_type=BillingOpportunity.MTM_COMPREHENSIVE,
                estimated_revenue=65.00,
                clinical_justification=(
                    f"DDI detected: {event.interaction.drug_a_name} + "
                    f"{event.interaction.drug_b_name} "
                    f"({event.interaction.severity.value}). "
                    f"Comprehensive medication review indicated."
                ),
                billing_codes=['99605', '99606'],
                documentation_requirements=[
                    "Complete medication list review",
                    "Drug interaction assessment documented",
                    "Action plan with patient/prescriber",
                    "Follow-up scheduled",
                ],
                expiration_date=(
                    datetime.now() + timedelta(days=30)
                ).strftime("%Y-%m-%d"),
            )
            opps.append(opp)
            self.opportunities.append(opp)
        
        # Monitoring opportunity for moderate+
        if event.interaction.severity in (
            DDISeverity.CONTRAINDICATED, DDISeverity.MAJOR, 
            DDISeverity.MODERATE
        ):
            self._opp_counter += 1
            opp = RevenueOpportunity(
                opportunity_id=f"OPP-{self._opp_counter:06d}",
                patient_id=event.patient_id,
                interaction_id=event.interaction.interaction_id,
                billing_type=BillingOpportunity.POINT_OF_CARE_TEST,
                estimated_revenue=22.00,
                clinical_justification=(
                    f"Monitoring required for {event.interaction.clinical_effect}"
                ),
                billing_codes=['81002', '85018'],
                documentation_requirements=[
                    "Clinical indication documented",
                    "Test results recorded",
                    "Prescriber notification if abnormal",
                ],
                expiration_date=(
                    datetime.now() + timedelta(days=14)
                ).strftime("%Y-%m-%d"),
            )
            opps.append(opp)
            self.opportunities.append(opp)
        
        return opps
    
    def _recommend_action(self, event: DDIClaimEvent, 
                          impact: Dict) -> Dict:
        """Generate recommended action for a DDI claim."""
        severity = event.interaction.severity
        
        if severity == DDISeverity.CONTRAINDICATED:
            return {
                'urgency': 'immediate',
                'action': 'Contact prescriber for therapeutic alternative',
                'billing_action': 'Document MTM intervention for billing',
                'estimated_time': '15-30 minutes',
            }
        elif severity == DDISeverity.MAJOR:
            return {
                'urgency': 'high',
                'action': 'Evaluate clinical significance, consider prescriber consult',
                'billing_action': 'Assess MTM eligibility, document intervention',
                'estimated_time': '10-20 minutes',
            }
        elif severity == DDISeverity.MODERATE:
            return {
                'urgency': 'standard',
                'action': 'Monitor patient, counsel on potential effects',
                'billing_action': 'Document counseling time for potential MTM',
                'estimated_time': '5-10 minutes',
            }
        else:
            return {
                'urgency': 'low',
                'action': 'Inform patient of minor interaction',
                'billing_action': 'No additional billing typically warranted',
                'estimated_time': '2-5 minutes',
            }
    
    def get_revenue_dashboard(self) -> Dict:
        """Generate comprehensive DDI revenue impact dashboard."""
        total_claims = len(self.claim_events)
        rejected_claims = [
            c for c in self.claim_events if c.claim_status == 'rejected'
        ]
        
        # Revenue metrics
        total_original = sum(c.original_amount for c in self.claim_events)
        total_adjudicated = sum(c.adjudicated_amount for c in self.claim_events)
        total_rejected_value = sum(c.original_amount for c in rejected_claims)
        
        # Opportunity metrics
        total_opportunities = len(self.opportunities)
        captured_opportunities = [o for o in self.opportunities if o.captured]
        captured_revenue = sum(o.captured_amount for o in captured_opportunities)
        uncaptured_revenue = sum(
            o.estimated_revenue for o in self.opportunities if not o.captured
        )
        
        # Severity distribution
        severity_dist = defaultdict(int)
        for event in self.claim_events:
            severity_dist[event.interaction.severity.value] += 1
        
        # Intervention summary
        intervention_summary = self.intervention_tracker.get_intervention_summary()
        
        return {
            'claim_metrics': {
                'total_ddi_claims': total_claims,
                'rejected_claims': len(rejected_claims),
                'rejection_rate': round(
                    len(rejected_claims) / max(total_claims, 1) * 100, 1
                ),
                'total_original_value': round(total_original, 2),
                'total_adjudicated_value': round(total_adjudicated, 2),
                'total_rejected_value': round(total_rejected_value, 2),
                'net_revenue_loss': round(
                    total_original - total_adjudicated, 2
                ),
            },
            'opportunity_metrics': {
                'total_opportunities': total_opportunities,
                'captured': len(captured_opportunities),
                'uncaptured': total_opportunities - len(captured_opportunities),
                'captured_revenue': round(captured_revenue, 2),
                'uncaptured_revenue': round(uncaptured_revenue, 2),
                'capture_rate': round(
                    len(captured_opportunities) / max(total_opportunities, 1) * 100, 1
                ),
            },
            'severity_distribution': dict(severity_dist),
            'intervention_summary': intervention_summary,
            'generated_at': datetime.now().isoformat(),
        }
    
    def get_top_revenue_leaks(self, limit: int = 10) -> List[Dict]:
        """Identify top revenue leaks from DDI-related claim issues."""
        payer_losses: Dict[str, float] = defaultdict(float)
        drug_pair_losses: Dict[str, float] = defaultdict(float)
        
        for event in self.claim_events:
            if event.claim_status == 'rejected':
                payer_losses[event.payer_name] += event.original_amount
                pair_key = (
                    f"{event.interaction.drug_a_name} + "
                    f"{event.interaction.drug_b_name}"
                )
                drug_pair_losses[pair_key] += event.original_amount
        
        top_payer_leaks = sorted(
            payer_losses.items(), key=lambda x: x[1], reverse=True
        )[:limit]
        
        top_drug_leaks = sorted(
            drug_pair_losses.items(), key=lambda x: x[1], reverse=True
        )[:limit]
        
        return {
            'top_payer_revenue_leaks': [
                {'payer': p, 'total_loss': round(v, 2)}
                for p, v in top_payer_leaks
            ],
            'top_drug_pair_revenue_leaks': [
                {'drug_pair': p, 'total_loss': round(v, 2)}
                for p, v in top_drug_leaks
            ],
        }
    
    def export_report(self) -> Dict:
        """Export full DDI revenue impact report."""
        return {
            'report_type': 'drug_interaction_revenue_impact',
            'generated_at': datetime.now().isoformat(),
            'dashboard': self.get_revenue_dashboard(),
            'revenue_leaks': self.get_top_revenue_leaks(),
            'payer_scorecards': {
                pid: self.payer_policies.get_payer_scorecard(pid)
                for pid in self.payer_policies.policies
            },
            'total_interactions_tracked': len(self.interactions_db),
        }


def create_analyzer() -> DrugInteractionRevenueAnalyzer:
    """Create and return a configured analyzer instance."""
    return DrugInteractionRevenueAnalyzer()
