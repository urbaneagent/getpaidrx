"""
GetPaidRx - Pharmacy Staff Productivity Tracker
=================================================
Tracks and analyzes pharmacy staff productivity metrics including
prescriptions per hour, clinical interventions, verification times,
and revenue-per-FTE. Enables workload balancing, performance benchmarking,
and staffing optimization.

Features:
- Real-time productivity metrics per pharmacist/technician
- Prescription throughput tracking (fill, verify, dispense)
- Clinical intervention documentation and value tracking
- Revenue attribution per staff member
- Workload distribution analysis and balancing
- Shift efficiency scoring and trend analysis
- Staffing recommendation engine
- Performance benchmarking against industry standards
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import math


class StaffRole(Enum):
    """Pharmacy staff roles."""
    PHARMACIST = "pharmacist"
    PHARMACY_TECH = "pharmacy_tech"
    PHARMACY_INTERN = "pharmacy_intern"
    PHARMACY_MANAGER = "pharmacy_manager"
    CLERK = "clerk"


class ActivityType(Enum):
    """Types of pharmacy activities."""
    RX_FILL = "rx_fill"
    RX_VERIFY = "rx_verify"
    RX_DISPENSE = "rx_dispense"
    CLINICAL_INTERVENTION = "clinical_intervention"
    IMMUNIZATION = "immunization"
    MTM_SESSION = "mtm_session"
    PATIENT_COUNSELING = "patient_counseling"
    INVENTORY = "inventory"
    PHONE_CALL = "phone_call"
    INSURANCE_RESOLUTION = "insurance_resolution"
    PRIOR_AUTH = "prior_auth"
    COMPOUND_PREP = "compound_prep"
    TRANSFER = "transfer"
    ADMIN = "admin"


class ShiftType(Enum):
    """Shift classifications."""
    MORNING = "morning"       # 6am-2pm
    AFTERNOON = "afternoon"   # 2pm-10pm
    EVENING = "evening"       # 10pm-6am
    SPLIT = "split"
    WEEKEND = "weekend"


@dataclass
class StaffMember:
    """A pharmacy staff member."""
    staff_id: str
    name: str
    role: StaffRole
    hourly_rate: float
    hire_date: str
    certifications: List[str] = field(default_factory=list)
    max_rx_per_hour: int = 0  # Benchmark capacity
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['role'] = self.role.value
        return result


@dataclass
class ActivityRecord:
    """A single productivity event."""
    record_id: str
    staff_id: str
    activity_type: ActivityType
    timestamp: str
    duration_minutes: float
    rx_count: int = 0
    revenue_impact: float = 0.0
    patient_id: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['activity_type'] = self.activity_type.value
        return result


@dataclass
class ShiftSummary:
    """Summary metrics for a staff member's shift."""
    staff_id: str
    shift_date: str
    shift_type: ShiftType
    hours_worked: float
    activities: Dict[str, int]  # activity_type -> count
    total_rx_processed: int
    rx_per_hour: float
    clinical_interventions: int
    revenue_generated: float
    revenue_per_hour: float
    efficiency_score: float  # 0-100
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['shift_type'] = self.shift_type.value
        return result


class ProductivityCalculator:
    """Calculates productivity metrics for staff members."""
    
    # Industry benchmarks (2026)
    BENCHMARKS = {
        StaffRole.PHARMACIST: {
            'rx_verify_per_hour': 15,
            'clinical_interventions_per_shift': 5,
            'counseling_per_shift': 8,
            'revenue_per_hour': 120.00,
        },
        StaffRole.PHARMACY_TECH: {
            'rx_fill_per_hour': 12,
            'phone_calls_per_shift': 20,
            'insurance_resolutions_per_shift': 8,
            'revenue_per_hour': 45.00,
        },
        StaffRole.PHARMACY_INTERN: {
            'rx_verify_per_hour': 8,
            'counseling_per_shift': 4,
            'revenue_per_hour': 60.00,
        },
    }
    
    # Revenue attribution by activity
    ACTIVITY_REVENUE = {
        ActivityType.RX_FILL: 2.50,          # Per script
        ActivityType.RX_VERIFY: 5.00,         # Per script
        ActivityType.RX_DISPENSE: 1.50,       # Per script
        ActivityType.CLINICAL_INTERVENTION: 25.00,
        ActivityType.IMMUNIZATION: 35.00,
        ActivityType.MTM_SESSION: 65.00,
        ActivityType.PATIENT_COUNSELING: 10.00,
        ActivityType.PRIOR_AUTH: 15.00,
        ActivityType.COMPOUND_PREP: 20.00,
        ActivityType.INSURANCE_RESOLUTION: 8.00,
        ActivityType.TRANSFER: 3.00,
    }
    
    def calculate_shift_summary(self, staff: StaffMember,
                                  activities: List[ActivityRecord],
                                  shift_hours: float,
                                  shift_type: ShiftType) -> ShiftSummary:
        """Calculate shift productivity summary."""
        activity_counts: Dict[str, int] = defaultdict(int)
        total_rx = 0
        total_revenue = 0.0
        clinical_count = 0
        
        for act in activities:
            activity_counts[act.activity_type.value] += 1
            total_rx += act.rx_count
            
            # Calculate revenue
            base_revenue = self.ACTIVITY_REVENUE.get(act.activity_type, 0)
            if act.rx_count > 0:
                revenue = base_revenue * act.rx_count
            else:
                revenue = base_revenue
            
            if act.revenue_impact > 0:
                revenue = act.revenue_impact  # Override with actual
            
            total_revenue += revenue
            
            if act.activity_type == ActivityType.CLINICAL_INTERVENTION:
                clinical_count += 1
        
        rx_per_hour = total_rx / max(shift_hours, 0.5)
        revenue_per_hour = total_revenue / max(shift_hours, 0.5)
        
        # Efficiency score
        efficiency = self._calculate_efficiency(
            staff.role, rx_per_hour, clinical_count,
            total_revenue, shift_hours
        )
        
        return ShiftSummary(
            staff_id=staff.staff_id,
            shift_date=datetime.now().strftime("%Y-%m-%d"),
            shift_type=shift_type,
            hours_worked=shift_hours,
            activities=dict(activity_counts),
            total_rx_processed=total_rx,
            rx_per_hour=round(rx_per_hour, 1),
            clinical_interventions=clinical_count,
            revenue_generated=round(total_revenue, 2),
            revenue_per_hour=round(revenue_per_hour, 2),
            efficiency_score=round(efficiency, 1),
        )
    
    def _calculate_efficiency(self, role: StaffRole, rx_per_hour: float,
                               clinical_count: int, revenue: float,
                               hours: float) -> float:
        """Calculate efficiency score 0-100."""
        benchmarks = self.BENCHMARKS.get(role, {})
        
        scores = []
        
        # RX throughput score
        if role == StaffRole.PHARMACIST:
            bench = benchmarks.get('rx_verify_per_hour', 15)
            scores.append(min(rx_per_hour / bench * 100, 120))
        elif role == StaffRole.PHARMACY_TECH:
            bench = benchmarks.get('rx_fill_per_hour', 12)
            scores.append(min(rx_per_hour / bench * 100, 120))
        
        # Revenue score
        bench_rev = benchmarks.get('revenue_per_hour', 80)
        rev_per_hour = revenue / max(hours, 0.5)
        scores.append(min(rev_per_hour / bench_rev * 100, 120))
        
        # Clinical score (for pharmacists)
        if role == StaffRole.PHARMACIST:
            bench_clinical = benchmarks.get('clinical_interventions_per_shift', 5)
            scores.append(min(clinical_count / bench_clinical * 100, 120))
        
        if not scores:
            return 50.0
        
        return min(sum(scores) / len(scores), 100.0)


class WorkloadBalancer:
    """Analyzes and recommends workload distribution."""
    
    def analyze_distribution(self, shift_summaries: List[ShiftSummary],
                               staff_registry: Dict[str, StaffMember]) -> Dict:
        """Analyze workload distribution across staff."""
        if not shift_summaries:
            return {'status': 'no_data'}
        
        # Group by staff
        staff_loads: Dict[str, Dict] = defaultdict(
            lambda: {'rx': 0, 'hours': 0.0, 'revenue': 0.0, 'efficiency': []}
        )
        
        for summary in shift_summaries:
            sl = staff_loads[summary.staff_id]
            sl['rx'] += summary.total_rx_processed
            sl['hours'] += summary.hours_worked
            sl['revenue'] += summary.revenue_generated
            sl['efficiency'].append(summary.efficiency_score)
        
        # Calculate fairness metrics
        rx_loads = [sl['rx'] for sl in staff_loads.values()]
        avg_rx = sum(rx_loads) / max(len(rx_loads), 1)
        
        # Standard deviation
        if len(rx_loads) > 1:
            variance = sum((x - avg_rx) ** 2 for x in rx_loads) / len(rx_loads)
            std_dev = math.sqrt(variance)
            coefficient_variation = std_dev / max(avg_rx, 1)
        else:
            coefficient_variation = 0.0
        
        # Identify overloaded/underloaded staff
        overloaded = []
        underloaded = []
        
        for staff_id, load in staff_loads.items():
            rx_ratio = load['rx'] / max(avg_rx, 1)
            staff = staff_registry.get(staff_id)
            
            if rx_ratio > 1.3:
                overloaded.append({
                    'staff_id': staff_id,
                    'name': staff.name if staff else 'Unknown',
                    'rx_load': load['rx'],
                    'load_ratio': round(rx_ratio, 2),
                })
            elif rx_ratio < 0.7:
                underloaded.append({
                    'staff_id': staff_id,
                    'name': staff.name if staff else 'Unknown',
                    'rx_load': load['rx'],
                    'load_ratio': round(rx_ratio, 2),
                })
        
        balance_score = max(0, 100 - (coefficient_variation * 100))
        
        return {
            'balance_score': round(balance_score, 1),
            'avg_rx_per_staff': round(avg_rx, 1),
            'workload_variation': round(coefficient_variation, 3),
            'overloaded_staff': overloaded,
            'underloaded_staff': underloaded,
            'recommendation': self._generate_recommendation(
                balance_score, overloaded, underloaded
            ),
        }
    
    def _generate_recommendation(self, score: float,
                                   overloaded: List, 
                                   underloaded: List) -> str:
        """Generate workload balancing recommendation."""
        if score >= 80:
            return "Workload well-balanced. No immediate action needed."
        elif score >= 60:
            if overloaded:
                names = ', '.join(s['name'] for s in overloaded[:3])
                return f"Moderate imbalance. Redistribute from: {names}"
            return "Minor imbalance detected. Monitor trends."
        else:
            return (
                "Significant workload imbalance! "
                f"{len(overloaded)} staff overloaded, "
                f"{len(underloaded)} underutilized. "
                "Immediate rebalancing recommended."
            )


class StaffingOptimizer:
    """Recommends optimal staffing levels based on historical data."""
    
    def recommend_staffing(self, 
                           historical_summaries: List[ShiftSummary],
                           target_rx_per_hour: float = 12.0,
                           target_efficiency: float = 75.0) -> Dict:
        """Recommend staffing levels based on historical patterns."""
        if not historical_summaries:
            return {'status': 'insufficient_data'}
        
        # Group by shift type
        shift_data: Dict[str, Dict] = defaultdict(
            lambda: {'rx': [], 'hours': [], 'staff_count': set()}
        )
        
        for s in historical_summaries:
            st = s.shift_type.value
            shift_data[st]['rx'].append(s.total_rx_processed)
            shift_data[st]['hours'].append(s.hours_worked)
            shift_data[st]['staff_count'].add(s.staff_id)
        
        recommendations = {}
        
        for shift_type, data in shift_data.items():
            avg_rx = sum(data['rx']) / max(len(data['rx']), 1)
            avg_hours = sum(data['hours']) / max(len(data['hours']), 1)
            current_staff = len(data['staff_count'])
            
            # Optimal staff = expected rx / (target_rx_per_hour * shift_hours)
            optimal_staff = math.ceil(
                avg_rx / (target_rx_per_hour * max(avg_hours, 1))
            )
            
            recommendations[shift_type] = {
                'current_staff_count': current_staff,
                'recommended_staff_count': optimal_staff,
                'avg_rx_volume': round(avg_rx, 1),
                'avg_shift_hours': round(avg_hours, 1),
                'staffing_gap': optimal_staff - current_staff,
                'status': (
                    'understaffed' if optimal_staff > current_staff else
                    'overstaffed' if optimal_staff < current_staff else
                    'optimal'
                ),
            }
        
        return {
            'recommendations': recommendations,
            'target_rx_per_hour': target_rx_per_hour,
            'target_efficiency': target_efficiency,
            'analyzed_shifts': len(historical_summaries),
        }


class PharmacyStaffProductivityTracker:
    """
    Main orchestrator for pharmacy staff productivity tracking.
    """
    
    def __init__(self):
        self.calculator = ProductivityCalculator()
        self.balancer = WorkloadBalancer()
        self.optimizer = StaffingOptimizer()
        
        self.staff: Dict[str, StaffMember] = {}
        self.activities: List[ActivityRecord] = []
        self.shift_summaries: List[ShiftSummary] = []
        self._record_counter = 0
    
    def register_staff(self, staff: StaffMember):
        """Register a staff member."""
        self.staff[staff.staff_id] = staff
    
    def record_activity(self, staff_id: str, activity_type: ActivityType,
                         duration_minutes: float, rx_count: int = 0,
                         revenue_impact: float = 0.0,
                         patient_id: str = None,
                         notes: str = "") -> str:
        """Record a productivity activity."""
        self._record_counter += 1
        record_id = f"ACT-{self._record_counter:08d}"
        
        record = ActivityRecord(
            record_id=record_id,
            staff_id=staff_id,
            activity_type=activity_type,
            timestamp=datetime.now().isoformat(),
            duration_minutes=duration_minutes,
            rx_count=rx_count,
            revenue_impact=revenue_impact,
            patient_id=patient_id,
            notes=notes,
        )
        
        self.activities.append(record)
        return record_id
    
    def close_shift(self, staff_id: str, shift_hours: float,
                      shift_type: ShiftType) -> ShiftSummary:
        """Close a shift and generate summary."""
        staff = self.staff.get(staff_id)
        if not staff:
            raise ValueError(f"Staff {staff_id} not found")
        
        # Get today's activities for this staff member
        today = datetime.now().strftime("%Y-%m-%d")
        shift_activities = [
            a for a in self.activities
            if a.staff_id == staff_id and a.timestamp.startswith(today)
        ]
        
        summary = self.calculator.calculate_shift_summary(
            staff, shift_activities, shift_hours, shift_type
        )
        
        self.shift_summaries.append(summary)
        return summary
    
    def get_staff_performance(self, staff_id: str, 
                               days: int = 30) -> Dict:
        """Get performance report for a staff member."""
        staff = self.staff.get(staff_id)
        if not staff:
            return {'error': 'Staff not found'}
        
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        relevant = [
            s for s in self.shift_summaries
            if s.staff_id == staff_id and s.shift_date >= cutoff
        ]
        
        if not relevant:
            return {'staff_id': staff_id, 'status': 'no_data_in_period'}
        
        total_rx = sum(s.total_rx_processed for s in relevant)
        total_hours = sum(s.hours_worked for s in relevant)
        total_revenue = sum(s.revenue_generated for s in relevant)
        avg_efficiency = sum(s.efficiency_score for s in relevant) / len(relevant)
        
        return {
            'staff_id': staff_id,
            'name': staff.name,
            'role': staff.role.value,
            'period_days': days,
            'shifts_worked': len(relevant),
            'total_hours': round(total_hours, 1),
            'total_rx_processed': total_rx,
            'avg_rx_per_hour': round(total_rx / max(total_hours, 1), 1),
            'total_revenue_generated': round(total_revenue, 2),
            'avg_revenue_per_hour': round(total_revenue / max(total_hours, 1), 2),
            'avg_efficiency_score': round(avg_efficiency, 1),
            'total_clinical_interventions': sum(
                s.clinical_interventions for s in relevant
            ),
            'cost_to_serve': round(staff.hourly_rate * total_hours, 2),
            'roi': round(
                (total_revenue - staff.hourly_rate * total_hours) / 
                max(staff.hourly_rate * total_hours, 1) * 100, 1
            ),
        }
    
    def get_team_dashboard(self) -> Dict:
        """Get team-wide productivity dashboard."""
        if not self.shift_summaries:
            return {'status': 'no_data'}
        
        # Last 7 days
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent = [s for s in self.shift_summaries if s.shift_date >= cutoff]
        
        if not recent:
            return {'status': 'no_recent_data'}
        
        total_rx = sum(s.total_rx_processed for s in recent)
        total_revenue = sum(s.revenue_generated for s in recent)
        total_hours = sum(s.hours_worked for s in recent)
        avg_efficiency = sum(s.efficiency_score for s in recent) / len(recent)
        
        # Top performers
        staff_perf: Dict[str, Dict] = defaultdict(
            lambda: {'rx': 0, 'revenue': 0.0, 'hours': 0.0}
        )
        for s in recent:
            staff_perf[s.staff_id]['rx'] += s.total_rx_processed
            staff_perf[s.staff_id]['revenue'] += s.revenue_generated
            staff_perf[s.staff_id]['hours'] += s.hours_worked
        
        top_by_rx = sorted(
            staff_perf.items(), 
            key=lambda x: x[1]['rx'] / max(x[1]['hours'], 1),
            reverse=True
        )[:5]
        
        workload = self.balancer.analyze_distribution(recent, self.staff)
        staffing = self.optimizer.recommend_staffing(recent)
        
        return {
            'period': 'last_7_days',
            'total_staff': len(self.staff),
            'total_shifts': len(recent),
            'total_rx_processed': total_rx,
            'total_revenue': round(total_revenue, 2),
            'total_hours': round(total_hours, 1),
            'avg_rx_per_hour': round(total_rx / max(total_hours, 1), 1),
            'avg_revenue_per_hour': round(total_revenue / max(total_hours, 1), 2),
            'avg_efficiency': round(avg_efficiency, 1),
            'top_performers': [
                {
                    'staff_id': sid,
                    'name': self.staff[sid].name if sid in self.staff else 'Unknown',
                    'rx_per_hour': round(
                        data['rx'] / max(data['hours'], 1), 1
                    ),
                }
                for sid, data in top_by_rx
            ],
            'workload_analysis': workload,
            'staffing_recommendations': staffing,
            'generated_at': datetime.now().isoformat(),
        }
    
    def export_report(self) -> Dict:
        """Export comprehensive productivity report."""
        return {
            'report_type': 'pharmacy_staff_productivity',
            'generated_at': datetime.now().isoformat(),
            'staff_count': len(self.staff),
            'total_activities': len(self.activities),
            'total_shifts': len(self.shift_summaries),
            'dashboard': self.get_team_dashboard(),
            'individual_reports': {
                sid: self.get_staff_performance(sid)
                for sid in self.staff
            },
        }


def create_tracker() -> PharmacyStaffProductivityTracker:
    """Create and return a PharmacyStaffProductivityTracker instance."""
    return PharmacyStaffProductivityTracker()
