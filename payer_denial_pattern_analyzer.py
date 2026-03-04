"""
GetPaidRx - Payer Denial Pattern Analyzer
===========================================
Advanced analytics engine that identifies patterns in pharmacy claim denials
across payers, drugs, and time periods. Uses statistical analysis to detect
systematic underpayment or denial behaviors, predict future denials, and
generate actionable appeal strategies.

Features:
- Denial pattern clustering by payer, drug class, rejection code
- Temporal trend analysis (weekly, monthly, seasonal)
- Payer behavior scoring and anomaly detection
- Appeal success rate tracking and optimization
- Root cause classification for denials
- Predictive denial probability scoring
- Automated appeal template generation
- Financial impact quantification per denial pattern
"""

import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


class DenialCategory(Enum):
    """High-level denial categories."""
    PRIOR_AUTH = "prior_authorization"
    FORMULARY = "formulary_exclusion"
    QUANTITY_LIMIT = "quantity_limit"
    STEP_THERAPY = "step_therapy"
    DUPLICATE = "duplicate_claim"
    NDC_ISSUE = "ndc_mismatch"
    ELIGIBILITY = "eligibility"
    DAW = "dispense_as_written"
    PRICING = "pricing_override"
    COVERAGE_GAP = "coverage_gap"
    TIMING = "timing_too_early_late"
    COMPOUND = "compound_exclusion"
    SPECIALTY = "specialty_restriction"
    OTHER = "other"


class DenialTrend(Enum):
    """Trend direction for denial patterns."""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    SEASONAL = "seasonal"
    SPIKE = "spike"


class AppealOutcome(Enum):
    """Outcome of an appeal."""
    WON = "won"
    LOST = "lost"
    PARTIAL = "partial"
    PENDING = "pending"
    NOT_APPEALED = "not_appealed"


@dataclass
class DenialRecord:
    """Individual claim denial record."""
    denial_id: str
    claim_id: str
    patient_id: str
    payer_id: str
    payer_name: str
    drug_ndc: str
    drug_name: str
    drug_class: str
    rejection_code: str
    rejection_message: str
    denial_category: DenialCategory
    claim_amount: float
    denial_date: str
    prescriber_npi: str
    pharmacy_npi: str
    appeal_outcome: AppealOutcome = AppealOutcome.NOT_APPEALED
    appeal_amount_recovered: float = 0.0
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['denial_category'] = self.denial_category.value
        result['appeal_outcome'] = self.appeal_outcome.value
        return result


@dataclass
class DenialPattern:
    """An identified denial pattern."""
    pattern_id: str
    description: str
    payer_ids: List[str]
    drug_classes: List[str]
    rejection_codes: List[str]
    denial_category: DenialCategory
    occurrence_count: int
    total_denied_amount: float
    avg_claim_amount: float
    trend: DenialTrend
    appeal_win_rate: float
    first_seen: str
    last_seen: str
    predicted_frequency: float  # Expected denials per week
    recommended_action: str
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['denial_category'] = self.denial_category.value
        result['trend'] = self.trend.value
        return result


class DenialClusterer:
    """Clusters denials into patterns based on similarity."""
    
    def cluster_denials(self, denials: List[DenialRecord]) -> List[DenialPattern]:
        """Group denials into patterns based on common attributes."""
        # Group by (payer, category, drug_class)
        groups: Dict[Tuple, List[DenialRecord]] = defaultdict(list)
        
        for denial in denials:
            key = (denial.payer_id, denial.denial_category.value, denial.drug_class)
            groups[key].append(denial)
        
        patterns = []
        pattern_counter = 0
        
        for (payer_id, category, drug_class), group_denials in groups.items():
            if len(group_denials) < 3:  # Min 3 occurrences for a pattern
                continue
            
            pattern_counter += 1
            
            # Calculate metrics
            total_amount = sum(d.claim_amount for d in group_denials)
            avg_amount = total_amount / len(group_denials)
            
            # Rejection codes in this group
            rejection_codes = list(set(d.rejection_code for d in group_denials))
            
            # Date range
            dates = sorted(d.denial_date for d in group_denials)
            
            # Appeal metrics
            appealed = [
                d for d in group_denials 
                if d.appeal_outcome != AppealOutcome.NOT_APPEALED
            ]
            won = [
                d for d in appealed 
                if d.appeal_outcome in (AppealOutcome.WON, AppealOutcome.PARTIAL)
            ]
            appeal_win_rate = len(won) / max(len(appealed), 1)
            
            # Trend analysis
            trend = self._analyze_trend(group_denials)
            
            # Predicted frequency
            if len(dates) >= 2:
                date_range = (
                    datetime.strptime(dates[-1], "%Y-%m-%d") - 
                    datetime.strptime(dates[0], "%Y-%m-%d")
                ).days
                if date_range > 0:
                    freq_per_week = len(group_denials) / (date_range / 7)
                else:
                    freq_per_week = len(group_denials)
            else:
                freq_per_week = 0.0
            
            # Payer name from first record
            payer_name = group_denials[0].payer_name
            
            pattern = DenialPattern(
                pattern_id=f"PAT-{pattern_counter:05d}",
                description=(
                    f"{payer_name} {category} denials for {drug_class} drugs"
                ),
                payer_ids=[payer_id],
                drug_classes=[drug_class],
                rejection_codes=rejection_codes,
                denial_category=DenialCategory(category),
                occurrence_count=len(group_denials),
                total_denied_amount=round(total_amount, 2),
                avg_claim_amount=round(avg_amount, 2),
                trend=trend,
                appeal_win_rate=round(appeal_win_rate, 3),
                first_seen=dates[0],
                last_seen=dates[-1],
                predicted_frequency=round(freq_per_week, 2),
                recommended_action=self._generate_recommendation(
                    DenialCategory(category), appeal_win_rate, trend
                ),
            )
            patterns.append(pattern)
        
        # Sort by total denied amount descending
        patterns.sort(key=lambda p: p.total_denied_amount, reverse=True)
        return patterns
    
    def _analyze_trend(self, denials: List[DenialRecord]) -> DenialTrend:
        """Analyze temporal trend of denial occurrences."""
        if len(denials) < 5:
            return DenialTrend.STABLE
        
        # Group by week
        weekly: Dict[str, int] = defaultdict(int)
        for d in denials:
            try:
                dt = datetime.strptime(d.denial_date, "%Y-%m-%d")
                week_key = dt.strftime("%Y-W%V")
                weekly[week_key] += 1
            except ValueError:
                continue
        
        if len(weekly) < 3:
            return DenialTrend.STABLE
        
        weeks = sorted(weekly.keys())
        counts = [weekly[w] for w in weeks]
        
        # Simple linear trend
        n = len(counts)
        x_mean = (n - 1) / 2
        y_mean = sum(counts) / n
        
        numerator = sum((i - x_mean) * (counts[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return DenialTrend.STABLE
        
        slope = numerator / denominator
        relative_slope = slope / max(y_mean, 1)
        
        # Check for spike (recent sudden increase)
        if len(counts) >= 3:
            recent_avg = sum(counts[-2:]) / 2
            historical_avg = sum(counts[:-2]) / max(len(counts) - 2, 1)
            if recent_avg > historical_avg * 2:
                return DenialTrend.SPIKE
        
        if relative_slope > 0.15:
            return DenialTrend.INCREASING
        elif relative_slope < -0.15:
            return DenialTrend.DECREASING
        else:
            return DenialTrend.STABLE
    
    def _generate_recommendation(self, category: DenialCategory,
                                   win_rate: float,
                                   trend: DenialTrend) -> str:
        """Generate actionable recommendation for a denial pattern."""
        recommendations = {
            DenialCategory.PRIOR_AUTH: (
                "Implement prospective PA checking. "
                "Submit electronic PA before dispensing."
            ),
            DenialCategory.FORMULARY: (
                "Verify formulary status before dispensing. "
                "Contact prescriber for therapeutic alternatives."
            ),
            DenialCategory.QUANTITY_LIMIT: (
                "Check quantity limits in payer portal. "
                "Request quantity limit override with clinical justification."
            ),
            DenialCategory.STEP_THERAPY: (
                "Document prior therapy failures. "
                "Submit step therapy exception request."
            ),
            DenialCategory.PRICING: (
                "Review usual & customary pricing. "
                "Consider MAC appeal with acquisition cost documentation."
            ),
            DenialCategory.COVERAGE_GAP: (
                "Check patient's benefit phase. "
                "Explore manufacturer copay assistance programs."
            ),
        }
        
        base = recommendations.get(
            category, 
            "Review denial details and consult payer documentation."
        )
        
        if win_rate > 0.6:
            base += f" Appeal recommended (historical win rate: {win_rate:.0%})."
        elif win_rate < 0.2 and win_rate > 0:
            base += " Appeal unlikely to succeed. Focus on prevention."
        
        if trend == DenialTrend.INCREASING:
            base += " ⚠️ TREND: Denials increasing - prioritize intervention."
        elif trend == DenialTrend.SPIKE:
            base += " 🚨 SPIKE: Sudden increase detected - investigate immediately."
        
        return base


class AppealOptimizer:
    """Optimizes appeal strategy based on historical outcomes."""
    
    def __init__(self):
        self.appeal_history: List[Dict] = []
    
    def record_appeal(self, denial_id: str, payer_id: str,
                       category: DenialCategory, outcome: AppealOutcome,
                       amount_claimed: float, amount_recovered: float,
                       appeal_method: str, days_to_resolution: int):
        """Record an appeal outcome for learning."""
        self.appeal_history.append({
            'denial_id': denial_id,
            'payer_id': payer_id,
            'category': category.value,
            'outcome': outcome.value,
            'amount_claimed': amount_claimed,
            'amount_recovered': amount_recovered,
            'method': appeal_method,
            'days_to_resolution': days_to_resolution,
            'recorded_at': datetime.now().isoformat(),
        })
    
    def get_appeal_strategy(self, payer_id: str,
                            category: DenialCategory) -> Dict:
        """Recommend appeal strategy for a specific payer/category combo."""
        relevant = [
            a for a in self.appeal_history
            if a['payer_id'] == payer_id and a['category'] == category.value
        ]
        
        if not relevant:
            return {
                'recommendation': 'insufficient_data',
                'suggested_method': 'standard_written_appeal',
                'historical_win_rate': None,
                'avg_recovery': None,
            }
        
        # Analyze by method
        method_stats: Dict[str, Dict] = defaultdict(
            lambda: {'wins': 0, 'total': 0, 'recovered': 0.0, 'days': []}
        )
        
        for appeal in relevant:
            method = appeal['method']
            method_stats[method]['total'] += 1
            method_stats[method]['days'].append(appeal['days_to_resolution'])
            if appeal['outcome'] in ('won', 'partial'):
                method_stats[method]['wins'] += 1
                method_stats[method]['recovered'] += appeal['amount_recovered']
        
        # Find best method
        best_method = None
        best_rate = 0.0
        
        for method, stats in method_stats.items():
            win_rate = stats['wins'] / max(stats['total'], 1)
            if win_rate > best_rate and stats['total'] >= 3:
                best_rate = win_rate
                best_method = method
        
        if not best_method:
            best_method = max(
                method_stats, 
                key=lambda m: method_stats[m]['wins'] / max(method_stats[m]['total'], 1)
            )
        
        best_stats = method_stats[best_method]
        
        return {
            'recommendation': 'appeal' if best_rate > 0.3 else 'review_first',
            'suggested_method': best_method,
            'historical_win_rate': round(
                best_stats['wins'] / max(best_stats['total'], 1), 3
            ),
            'avg_recovery': round(
                best_stats['recovered'] / max(best_stats['wins'], 1), 2
            ),
            'avg_days_to_resolution': round(
                sum(best_stats['days']) / max(len(best_stats['days']), 1)
            ),
            'total_appeals_analyzed': len(relevant),
            'methods_compared': {
                m: {
                    'win_rate': round(s['wins'] / max(s['total'], 1), 3),
                    'count': s['total'],
                }
                for m, s in method_stats.items()
            },
        }


class DenialProbabilityScorer:
    """Predicts probability of denial for upcoming claims."""
    
    def __init__(self):
        self.denial_rates: Dict[Tuple, float] = {}
    
    def train(self, denials: List[DenialRecord], 
              total_claims_by_payer: Dict[str, int]):
        """Train denial probability model from historical data."""
        # Calculate denial rates by (payer, category)
        denial_counts: Dict[Tuple, int] = defaultdict(int)
        
        for d in denials:
            key = (d.payer_id, d.denial_category.value)
            denial_counts[key] += 1
        
        for (payer_id, category), count in denial_counts.items():
            total = total_claims_by_payer.get(payer_id, count * 10)
            self.denial_rates[(payer_id, category)] = count / max(total, 1)
    
    def predict_denial_probability(self, payer_id: str,
                                    drug_class: str,
                                    has_prior_auth: bool = False,
                                    is_formulary: bool = True,
                                    days_since_last_fill: int = 30) -> Dict:
        """Predict denial probability for a prospective claim."""
        # Base rates by category
        probs = {}
        
        for category in DenialCategory:
            key = (payer_id, category.value)
            base_rate = self.denial_rates.get(key, 0.02)
            probs[category.value] = base_rate
        
        # Adjustments
        if has_prior_auth:
            probs[DenialCategory.PRIOR_AUTH.value] *= 0.1
        else:
            probs[DenialCategory.PRIOR_AUTH.value] *= 2.0
        
        if not is_formulary:
            probs[DenialCategory.FORMULARY.value] *= 5.0
        
        if days_since_last_fill < 25:
            probs[DenialCategory.TIMING.value] *= 3.0
        
        # Overall denial probability
        overall = 1.0
        for p in probs.values():
            overall *= (1.0 - min(p, 1.0))
        overall_denial_prob = 1.0 - overall
        
        # Top risks
        top_risks = sorted(
            probs.items(), key=lambda x: x[1], reverse=True
        )[:3]
        
        return {
            'overall_denial_probability': round(min(overall_denial_prob, 1.0), 4),
            'risk_level': (
                'high' if overall_denial_prob > 0.3 else
                'medium' if overall_denial_prob > 0.1 else 'low'
            ),
            'top_risk_categories': [
                {'category': cat, 'probability': round(prob, 4)}
                for cat, prob in top_risks
            ],
            'category_probabilities': {
                k: round(v, 4) for k, v in probs.items()
            },
        }


class PayerDenialPatternAnalyzer:
    """
    Main orchestrator for payer denial pattern analysis.
    
    Combines clustering, trend analysis, appeal optimization,
    and predictive scoring for comprehensive denial management.
    """
    
    def __init__(self):
        self.clusterer = DenialClusterer()
        self.appeal_optimizer = AppealOptimizer()
        self.probability_scorer = DenialProbabilityScorer()
        
        self.denials: List[DenialRecord] = []
        self.patterns: List[DenialPattern] = []
        self.total_claims_by_payer: Dict[str, int] = {}
    
    def ingest_denial(self, denial: DenialRecord):
        """Add a denial record for analysis."""
        self.denials.append(denial)
    
    def set_total_claims(self, payer_id: str, total: int):
        """Set total claim count for a payer (for rate calculations)."""
        self.total_claims_by_payer[payer_id] = total
    
    def run_analysis(self) -> Dict:
        """Run full denial pattern analysis."""
        # Cluster into patterns
        self.patterns = self.clusterer.cluster_denials(self.denials)
        
        # Train probability scorer
        self.probability_scorer.train(self.denials, self.total_claims_by_payer)
        
        # Financial summary
        total_denied = sum(d.claim_amount for d in self.denials)
        total_recovered = sum(d.appeal_amount_recovered for d in self.denials)
        
        # Category distribution
        category_dist = defaultdict(lambda: {'count': 0, 'amount': 0.0})
        for d in self.denials:
            cat = d.denial_category.value
            category_dist[cat]['count'] += 1
            category_dist[cat]['amount'] += d.claim_amount
        
        # Payer ranking
        payer_denials: Dict[str, Dict] = defaultdict(
            lambda: {'count': 0, 'amount': 0.0, 'name': ''}
        )
        for d in self.denials:
            payer_denials[d.payer_id]['count'] += 1
            payer_denials[d.payer_id]['amount'] += d.claim_amount
            payer_denials[d.payer_id]['name'] = d.payer_name
        
        top_payers = sorted(
            payer_denials.items(), 
            key=lambda x: x[1]['amount'], 
            reverse=True
        )[:10]
        
        return {
            'analysis_summary': {
                'total_denials': len(self.denials),
                'total_denied_amount': round(total_denied, 2),
                'total_recovered': round(total_recovered, 2),
                'recovery_rate': round(
                    total_recovered / max(total_denied, 1) * 100, 1
                ),
                'patterns_identified': len(self.patterns),
            },
            'category_distribution': {
                k: {'count': v['count'], 'amount': round(v['amount'], 2)}
                for k, v in category_dist.items()
            },
            'top_denial_payers': [
                {
                    'payer_id': pid,
                    'payer_name': data['name'],
                    'denial_count': data['count'],
                    'total_amount': round(data['amount'], 2),
                }
                for pid, data in top_payers
            ],
            'top_patterns': [p.to_dict() for p in self.patterns[:10]],
            'actionable_insights': self._generate_insights(),
            'analyzed_at': datetime.now().isoformat(),
        }
    
    def _generate_insights(self) -> List[Dict]:
        """Generate actionable insights from patterns."""
        insights = []
        
        # High-value patterns worth appealing
        for pattern in self.patterns:
            if pattern.appeal_win_rate > 0.5 and pattern.total_denied_amount > 1000:
                insights.append({
                    'type': 'high_appeal_opportunity',
                    'priority': 'high',
                    'description': (
                        f"Pattern '{pattern.description}' has "
                        f"{pattern.appeal_win_rate:.0%} appeal win rate with "
                        f"${pattern.total_denied_amount:,.2f} denied. "
                        f"Systematic appeals could recover significant revenue."
                    ),
                    'estimated_recovery': round(
                        pattern.total_denied_amount * pattern.appeal_win_rate, 2
                    ),
                })
        
        # Trending up patterns
        increasing = [
            p for p in self.patterns 
            if p.trend in (DenialTrend.INCREASING, DenialTrend.SPIKE)
        ]
        for pattern in increasing[:5]:
            insights.append({
                'type': 'trending_denial',
                'priority': 'urgent' if pattern.trend == DenialTrend.SPIKE else 'high',
                'description': (
                    f"{'🚨 SPIKE' if pattern.trend == DenialTrend.SPIKE else '⚠️ Increasing'}: "
                    f"'{pattern.description}' — investigate payer policy change"
                ),
                'pattern_id': pattern.pattern_id,
            })
        
        return sorted(insights, key=lambda x: {
            'urgent': 0, 'high': 1, 'medium': 2, 'low': 3
        }.get(x['priority'], 4))
    
    def get_payer_report(self, payer_id: str) -> Dict:
        """Get denial analysis report for a specific payer."""
        payer_denials = [
            d for d in self.denials if d.payer_id == payer_id
        ]
        
        payer_patterns = [
            p for p in self.patterns if payer_id in p.payer_ids
        ]
        
        total_denied = sum(d.claim_amount for d in payer_denials)
        total_recovered = sum(d.appeal_amount_recovered for d in payer_denials)
        
        return {
            'payer_id': payer_id,
            'payer_name': payer_denials[0].payer_name if payer_denials else 'Unknown',
            'total_denials': len(payer_denials),
            'total_denied_amount': round(total_denied, 2),
            'total_recovered': round(total_recovered, 2),
            'patterns': [p.to_dict() for p in payer_patterns],
            'denial_rate': round(
                len(payer_denials) / max(
                    self.total_claims_by_payer.get(payer_id, len(payer_denials)),
                    1
                ) * 100, 2
            ),
        }
    
    def export_report(self) -> Dict:
        """Export full denial analysis report."""
        return {
            'report_type': 'payer_denial_pattern_analysis',
            'generated_at': datetime.now().isoformat(),
            'analysis': self.run_analysis(),
            'all_patterns': [p.to_dict() for p in self.patterns],
            'total_denials_analyzed': len(self.denials),
        }


def create_analyzer() -> PayerDenialPatternAnalyzer:
    """Create and return a configured analyzer instance."""
    return PayerDenialPatternAnalyzer()
