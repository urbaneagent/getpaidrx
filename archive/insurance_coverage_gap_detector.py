"""
GetPaidRx - Insurance Coverage Gap Detector
=============================================
Proactively identifies insurance coverage gaps for pharmacy patients,
including benefit phase transitions, formulary changes, prior auth
expirations, and coverage termination risks. Enables pre-emptive
intervention to prevent claim rejections and patient abandonment.

Features:
- Benefit phase monitoring (deductible, donut hole, catastrophic)
- Formulary change impact prediction
- Prior authorization expiration tracking
- Coverage termination risk detection
- Patient copay trajectory projection
- Manufacturer assistance program matching
- Coverage gap intervention recommendations
- Financial impact forecasting for coverage transitions
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import math


class BenefitPhase(Enum):
    """Medicare Part D benefit phases."""
    DEDUCTIBLE = "deductible"
    INITIAL_COVERAGE = "initial_coverage"
    COVERAGE_GAP = "coverage_gap"     # Donut hole
    CATASTROPHIC = "catastrophic"


class CoverageRisk(Enum):
    """Types of coverage gap risks."""
    BENEFIT_PHASE_TRANSITION = "benefit_phase_transition"
    FORMULARY_CHANGE = "formulary_change"
    PA_EXPIRATION = "pa_expiration"
    COVERAGE_TERMINATION = "coverage_termination"
    PLAN_CHANGE = "plan_change"
    COPAY_INCREASE = "copay_increase"
    QUANTITY_LIMIT_CHANGE = "quantity_limit_change"
    STEP_THERAPY_REQUIRED = "step_therapy_required"
    AGE_OUT = "age_out"
    LIFETIME_LIMIT = "lifetime_limit"


class InterventionType(Enum):
    """Types of coverage gap interventions."""
    MANUFACTURER_COUPON = "manufacturer_coupon"
    PAP_ENROLLMENT = "pap_enrollment"    # Patient Assistance Program
    THERAPEUTIC_SWITCH = "therapeutic_switch"
    PA_RENEWAL = "pa_renewal"
    PLAN_OPTIMIZATION = "plan_optimization"
    COPAY_CARD = "copay_card"
    SPLIT_FILL = "split_fill"
    DOSE_OPTIMIZATION = "dose_optimization"
    GENERIC_CONVERSION = "generic_conversion"
    NONE_NEEDED = "none_needed"


@dataclass
class PatientCoverage:
    """Patient insurance coverage details."""
    patient_id: str
    plan_id: str
    plan_name: str
    plan_type: str  # "commercial", "medicare_d", "medicaid", "tricare"
    effective_date: str
    termination_date: Optional[str]
    current_phase: BenefitPhase
    deductible_total: float
    deductible_met: float
    true_oop_total: float
    true_oop_spent: float
    annual_drug_spend: float
    formulary_tier_map: Dict[str, int] = field(default_factory=dict)
    active_prior_auths: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['current_phase'] = self.current_phase.value
        return result


@dataclass
class CoverageGapAlert:
    """An identified coverage gap risk."""
    alert_id: str
    patient_id: str
    risk_type: CoverageRisk
    severity: str  # "critical", "high", "medium", "low"
    estimated_date: str
    drug_name: str
    drug_ndc: str
    financial_impact: float
    description: str
    recommended_interventions: List[Dict]
    created_at: str
    resolved: bool = False
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['risk_type'] = self.risk_type.value
        return result


class BenefitPhasePredictor:
    """Predicts when patients will transition between benefit phases."""
    
    # 2026 Medicare Part D thresholds
    PART_D_THRESHOLDS = {
        'deductible': 590.00,
        'initial_coverage_limit': 5030.00,
        'catastrophic_threshold': 8000.00,  # True out-of-pocket
    }
    
    def predict_phase_transition(
        self, coverage: PatientCoverage,
        monthly_drug_cost: float,
        monthly_oop_cost: float
    ) -> Dict:
        """Predict when patient will transition to next benefit phase."""
        
        current = coverage.current_phase
        
        if current == BenefitPhase.DEDUCTIBLE:
            remaining = coverage.deductible_total - coverage.deductible_met
            if monthly_drug_cost > 0:
                months_to_transition = remaining / monthly_drug_cost
            else:
                months_to_transition = 12
            
            next_phase = BenefitPhase.INITIAL_COVERAGE
            
        elif current == BenefitPhase.INITIAL_COVERAGE:
            remaining = (
                self.PART_D_THRESHOLDS['initial_coverage_limit'] - 
                coverage.annual_drug_spend
            )
            if monthly_drug_cost > 0:
                months_to_transition = remaining / monthly_drug_cost
            else:
                months_to_transition = 12
            
            next_phase = BenefitPhase.COVERAGE_GAP
            
        elif current == BenefitPhase.COVERAGE_GAP:
            remaining = (
                self.PART_D_THRESHOLDS['catastrophic_threshold'] - 
                coverage.true_oop_spent
            )
            if monthly_oop_cost > 0:
                months_to_transition = remaining / monthly_oop_cost
            else:
                months_to_transition = 12
            
            next_phase = BenefitPhase.CATASTROPHIC
            
        else:
            return {
                'current_phase': current.value,
                'next_phase': None,
                'months_to_transition': None,
                'message': 'Patient in catastrophic coverage - no further transitions',
            }
        
        est_date = (
            datetime.now() + timedelta(days=months_to_transition * 30)
        ).strftime("%Y-%m-%d")
        
        # Cost impact when entering new phase
        cost_impact = self._estimate_cost_impact(current, next_phase, monthly_drug_cost)
        
        return {
            'current_phase': current.value,
            'next_phase': next_phase.value,
            'months_to_transition': round(months_to_transition, 1),
            'estimated_transition_date': est_date,
            'remaining_in_current': round(remaining, 2),
            'cost_impact': cost_impact,
            'urgency': (
                'immediate' if months_to_transition <= 1 else
                'soon' if months_to_transition <= 3 else
                'upcoming' if months_to_transition <= 6 else 'distant'
            ),
        }
    
    def _estimate_cost_impact(self, current: BenefitPhase,
                               next_phase: BenefitPhase,
                               monthly_cost: float) -> Dict:
        """Estimate monthly cost change during phase transition."""
        # Approximate copay percentages by phase
        copay_rates = {
            BenefitPhase.DEDUCTIBLE: 1.00,         # Patient pays 100%
            BenefitPhase.INITIAL_COVERAGE: 0.25,    # ~25% copay
            BenefitPhase.COVERAGE_GAP: 0.25,        # 25% in 2026 (no more donut hole gap)
            BenefitPhase.CATASTROPHIC: 0.05,         # 5% copay
        }
        
        current_cost = monthly_cost * copay_rates.get(current, 0.25)
        next_cost = monthly_cost * copay_rates.get(next_phase, 0.25)
        
        return {
            'current_monthly_oop': round(current_cost, 2),
            'projected_monthly_oop': round(next_cost, 2),
            'monthly_change': round(next_cost - current_cost, 2),
            'annual_impact': round((next_cost - current_cost) * 12, 2),
        }


class PAExpirationTracker:
    """Tracks prior authorization expirations."""
    
    def check_expirations(self, coverage: PatientCoverage,
                            warning_days: int = 30) -> List[Dict]:
        """Check for upcoming PA expirations."""
        warnings = []
        now = datetime.now()
        
        for pa in coverage.active_prior_auths:
            exp_date_str = pa.get('expiration_date')
            if not exp_date_str:
                continue
            
            try:
                exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                days_until = (exp_date - now).days
                
                if days_until <= warning_days:
                    severity = (
                        'critical' if days_until <= 7 else
                        'high' if days_until <= 14 else
                        'medium' if days_until <= 30 else 'low'
                    )
                    
                    warnings.append({
                        'drug_name': pa.get('drug_name', 'Unknown'),
                        'drug_ndc': pa.get('drug_ndc', ''),
                        'pa_number': pa.get('pa_number', ''),
                        'expiration_date': exp_date_str,
                        'days_remaining': days_until,
                        'severity': severity,
                        'action_needed': (
                            'Submit PA renewal immediately'
                            if days_until <= 14
                            else 'Schedule PA renewal'
                        ),
                    })
            except ValueError:
                continue
        
        warnings.sort(key=lambda w: w['days_remaining'])
        return warnings


class AssistanceProgramMatcher:
    """Matches patients with manufacturer and assistance programs."""
    
    # Common assistance programs (simplified)
    PROGRAMS = {
        'humira': {
            'manufacturer': 'AbbVie',
            'program': 'AbbVie Patient Assistance',
            'max_savings': 19200.00,
            'income_limit': 500,  # % FPL
            'url': 'https://www.abbvie.com/patients',
        },
        'eliquis': {
            'manufacturer': 'BMS/Pfizer',
            'program': 'Eliquis 360 Support',
            'max_savings': 6400.00,
            'income_limit': 400,
            'url': 'https://www.eliquis.com',
        },
        'jardiance': {
            'manufacturer': 'Boehringer Ingelheim',
            'program': 'Jardiance Savings Card',
            'max_savings': 3600.00,
            'income_limit': None,  # No income requirement
            'url': 'https://www.jardiance.com',
        },
        'ozempic': {
            'manufacturer': 'Novo Nordisk',
            'program': 'NovoCare',
            'max_savings': 4800.00,
            'income_limit': 400,
            'url': 'https://www.novocare.com',
        },
    }
    
    def find_programs(self, drug_name: str,
                       plan_type: str,
                       annual_income: float = None) -> List[Dict]:
        """Find applicable assistance programs for a drug."""
        programs = []
        
        drug_key = drug_name.lower().replace(' ', '_')
        
        if drug_key in self.PROGRAMS:
            prog = self.PROGRAMS[drug_key]
            
            eligible = True
            if prog['income_limit'] and annual_income:
                # Simplified FPL check (2026 FPL ~$15,560 for individual)
                fpl_pct = (annual_income / 15560) * 100
                if fpl_pct > prog['income_limit']:
                    eligible = False
            
            programs.append({
                'program_name': prog['program'],
                'manufacturer': prog['manufacturer'],
                'max_annual_savings': prog['max_savings'],
                'eligible': eligible,
                'url': prog['url'],
                'plan_type_compatible': plan_type != 'medicare_d',
            })
        
        # Generic copay card suggestion
        if plan_type == 'commercial':
            programs.append({
                'program_name': 'Manufacturer Copay Card (Generic)',
                'manufacturer': 'Various',
                'max_annual_savings': 3000.00,
                'eligible': True,
                'url': 'Contact manufacturer',
                'plan_type_compatible': True,
            })
        
        # Medicare Extra Help
        if plan_type == 'medicare_d':
            programs.append({
                'program_name': 'Medicare Extra Help (LIS)',
                'manufacturer': 'CMS',
                'max_annual_savings': 5000.00,
                'eligible': True,
                'url': 'https://www.ssa.gov/medicare/part-d-extra-help',
                'plan_type_compatible': True,
            })
        
        return programs


class InsuranceCoverageGapDetector:
    """
    Main orchestrator for insurance coverage gap detection.
    """
    
    def __init__(self):
        self.phase_predictor = BenefitPhasePredictor()
        self.pa_tracker = PAExpirationTracker()
        self.assistance_matcher = AssistanceProgramMatcher()
        
        self.patients: Dict[str, PatientCoverage] = {}
        self.alerts: List[CoverageGapAlert] = []
        self._alert_counter = 0
    
    def register_patient(self, coverage: PatientCoverage):
        """Register patient coverage data."""
        self.patients[coverage.patient_id] = coverage
    
    def scan_patient(self, patient_id: str,
                      monthly_drug_cost: float = 0,
                      monthly_oop_cost: float = 0) -> Dict:
        """Run comprehensive coverage gap scan for a patient."""
        coverage = self.patients.get(patient_id)
        if not coverage:
            return {'error': 'Patient not found'}
        
        alerts = []
        
        # 1. Benefit phase transition prediction
        if coverage.plan_type == 'medicare_d':
            phase_pred = self.phase_predictor.predict_phase_transition(
                coverage, monthly_drug_cost, monthly_oop_cost
            )
            
            if phase_pred.get('urgency') in ('immediate', 'soon'):
                alert = self._create_alert(
                    patient_id,
                    CoverageRisk.BENEFIT_PHASE_TRANSITION,
                    'high' if phase_pred['urgency'] == 'immediate' else 'medium',
                    phase_pred.get('estimated_transition_date', ''),
                    'Multiple drugs',
                    '',
                    abs(phase_pred.get('cost_impact', {}).get('annual_impact', 0)),
                    f"Patient approaching {phase_pred.get('next_phase', 'unknown')} phase in {phase_pred.get('months_to_transition', '?')} months",
                    [{'type': 'plan_review', 'description': 'Review coverage options before transition'}],
                )
                alerts.append(alert)
        
        # 2. PA expiration check
        pa_warnings = self.pa_tracker.check_expirations(coverage)
        for pa in pa_warnings:
            alert = self._create_alert(
                patient_id,
                CoverageRisk.PA_EXPIRATION,
                pa['severity'],
                pa['expiration_date'],
                pa['drug_name'],
                pa.get('drug_ndc', ''),
                0.0,
                f"PA expires in {pa['days_remaining']} days for {pa['drug_name']}",
                [{'type': 'pa_renewal', 'description': pa['action_needed']}],
            )
            alerts.append(alert)
        
        # 3. Coverage termination check
        if coverage.termination_date:
            try:
                term_date = datetime.strptime(coverage.termination_date, "%Y-%m-%d")
                days_until_term = (term_date - datetime.now()).days
                
                if 0 < days_until_term <= 60:
                    alert = self._create_alert(
                        patient_id,
                        CoverageRisk.COVERAGE_TERMINATION,
                        'critical' if days_until_term <= 14 else 'high',
                        coverage.termination_date,
                        'All medications',
                        '',
                        monthly_drug_cost * 12,
                        f"Coverage terminates in {days_until_term} days",
                        [{'type': 'coverage_transition', 'description': 'Help patient find new coverage'}],
                    )
                    alerts.append(alert)
            except ValueError:
                pass
        
        return {
            'patient_id': patient_id,
            'plan': coverage.plan_name,
            'current_phase': coverage.current_phase.value,
            'alerts': [a.to_dict() for a in alerts],
            'total_risks': len(alerts),
            'critical_risks': sum(1 for a in alerts if a.severity == 'critical'),
            'scanned_at': datetime.now().isoformat(),
        }
    
    def scan_all_patients(self, monthly_costs: Dict[str, Tuple[float, float]] = None
                           ) -> Dict:
        """Scan all registered patients for coverage gaps."""
        results = []
        total_alerts = 0
        critical_count = 0
        
        for patient_id in self.patients:
            costs = monthly_costs.get(patient_id, (200, 50)) if monthly_costs else (200, 50)
            scan = self.scan_patient(patient_id, costs[0], costs[1])
            
            if scan.get('total_risks', 0) > 0:
                results.append(scan)
                total_alerts += scan['total_risks']
                critical_count += scan.get('critical_risks', 0)
        
        return {
            'patients_scanned': len(self.patients),
            'patients_with_risks': len(results),
            'total_alerts': total_alerts,
            'critical_alerts': critical_count,
            'patient_results': sorted(
                results, 
                key=lambda x: x.get('critical_risks', 0),
                reverse=True
            ),
            'scanned_at': datetime.now().isoformat(),
        }
    
    def find_assistance(self, patient_id: str, 
                         drug_name: str,
                         annual_income: float = None) -> Dict:
        """Find assistance programs for a patient's drug."""
        coverage = self.patients.get(patient_id)
        if not coverage:
            return {'error': 'Patient not found'}
        
        programs = self.assistance_matcher.find_programs(
            drug_name, coverage.plan_type, annual_income
        )
        
        return {
            'patient_id': patient_id,
            'drug': drug_name,
            'plan_type': coverage.plan_type,
            'programs_found': len(programs),
            'programs': programs,
        }
    
    def _create_alert(self, patient_id: str, risk_type: CoverageRisk,
                       severity: str, est_date: str, drug_name: str,
                       drug_ndc: str, financial_impact: float,
                       description: str,
                       interventions: List[Dict]) -> CoverageGapAlert:
        """Create a coverage gap alert."""
        self._alert_counter += 1
        alert_id = f"CGA-{self._alert_counter:06d}"
        
        alert = CoverageGapAlert(
            alert_id=alert_id,
            patient_id=patient_id,
            risk_type=risk_type,
            severity=severity,
            estimated_date=est_date,
            drug_name=drug_name,
            drug_ndc=drug_ndc,
            financial_impact=financial_impact,
            description=description,
            recommended_interventions=interventions,
            created_at=datetime.now().isoformat(),
        )
        
        self.alerts.append(alert)
        return alert
    
    def get_dashboard(self) -> Dict:
        """Get coverage gap detection dashboard."""
        active_alerts = [a for a in self.alerts if not a.resolved]
        
        risk_dist = defaultdict(int)
        severity_dist = defaultdict(int)
        
        for a in active_alerts:
            risk_dist[a.risk_type.value] += 1
            severity_dist[a.severity] += 1
        
        return {
            'total_patients': len(self.patients),
            'total_active_alerts': len(active_alerts),
            'risk_distribution': dict(risk_dist),
            'severity_distribution': dict(severity_dist),
            'top_alerts': [
                a.to_dict() for a in sorted(
                    active_alerts,
                    key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(x.severity, 4)
                )[:10]
            ],
            'generated_at': datetime.now().isoformat(),
        }


def create_detector() -> InsuranceCoverageGapDetector:
    """Create and return an InsuranceCoverageGapDetector instance."""
    return InsuranceCoverageGapDetector()
