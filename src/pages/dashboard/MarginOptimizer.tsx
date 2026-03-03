import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  DollarSign,
  Target,
  Zap,
  BarChart3,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ArrowRight,
} from 'lucide-react';

interface Opportunity {
  opportunity_id: string;
  priority_rank: number;
  category: string;
  title: string;
  description: string;
  monthly_impact: number;
  annual_impact: number;
  difficulty: string;
  time_to_implement: string;
  roi_score: number;
}

interface AnalysisData {
  pharmacy_name: string;
  current_state: {
    gross_margin_pct: number;
    industry_avg_margin_pct: number;
    gap_vs_industry: number;
    generic_fill_rate: number;
    inventory_turns: number;
    daily_scripts: number;
  };
  total_opportunities: number;
  total_monthly_improvement: number;
  total_annual_improvement: number;
  potential_margin_improvement_pct: number;
  opportunities: Opportunity[];
  quick_wins: Opportunity[];
  high_impact: Opportunity[];
  category_summary: Record<string, { count: number; total_annual_impact: number }>;
}

const difficultyColors: Record<string, string> = {
  EASY: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HARD: 'bg-red-100 text-red-800',
};

const categoryIcons: Record<string, string> = {
  generic_switch: '💊',
  dispensing: '💰',
  inventory: '📦',
  contract: '📋',
  volume: '📈',
  services: '🏥',
};

export default function MarginOptimizer() {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'quick' | 'high'>('all');

  useEffect(() => {
    loadAnalysis();
  }, []);

  const loadAnalysis = async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/v1/margin/analyze');
      const result = await resp.json();
      setData(result);
    } catch (err) {
      console.error('Failed to load margin analysis:', err);
    }
    setLoading(false);
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
        <span className="ml-2 text-gray-500">Analyzing margins...</span>
      </div>
    );
  }

  const currentOpps = activeTab === 'quick' ? data.quick_wins :
                      activeTab === 'high' ? data.high_impact :
                      data.opportunities;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Margin Optimizer</h1>
          <p className="text-gray-600 mt-1">
            {data.total_opportunities} opportunities to improve profitability
          </p>
        </div>
        <button onClick={loadAnalysis} className="btn-secondary inline-flex items-center gap-2 text-sm">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-500">Current Margin</span>
            <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-blue-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900">{data.current_state.gross_margin_pct}%</p>
          <p className={`text-xs mt-1 ${data.current_state.gap_vs_industry > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {data.current_state.gap_vs_industry > 0 ? `${data.current_state.gap_vs_industry}% below` : `${Math.abs(data.current_state.gap_vs_industry)}% above`} industry avg
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-500">Monthly Potential</span>
            <div className="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-green-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-green-600">
            ${data.total_monthly_improvement.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500 mt-1">Available improvement</p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-500">Annual Impact</span>
            <div className="w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center">
              <DollarSign className="w-4 h-4 text-emerald-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-emerald-600">
            ${data.total_annual_improvement.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500 mt-1">+{data.potential_margin_improvement_pct}% margin</p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-500">Quick Wins</span>
            <div className="w-8 h-8 bg-yellow-50 rounded-lg flex items-center justify-center">
              <Zap className="w-4 h-4 text-yellow-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-yellow-600">{data.quick_wins.length}</p>
          <p className="text-xs text-gray-500 mt-1">Easy to implement now</p>
        </div>
      </div>

      {/* Category Summary */}
      <div className="card">
        <h3 className="font-bold text-gray-900 mb-4">Opportunity by Category</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(data.category_summary).map(([cat, stats]) => (
            <div key={cat} className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl mb-1">{categoryIcons[cat] || '⚙️'}</div>
              <div className="text-xs text-gray-500 capitalize">{cat.replace('_', ' ')}</div>
              <div className="text-sm font-bold text-gray-900">${stats.total_annual_impact.toLocaleString()}/yr</div>
              <div className="text-xs text-gray-400">{stats.count} opportunities</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Controls */}
      <div className="flex items-center gap-2">
        {([['all', 'All Opportunities'], ['quick', 'Quick Wins'], ['high', 'High Impact']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === key ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Opportunity Cards */}
      <div className="space-y-3">
        {currentOpps.map((opp) => {
          const isExpanded = expandedId === opp.opportunity_id;
          return (
            <div key={opp.opportunity_id} className="card border hover:border-primary-200 transition">
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedId(isExpanded ? null : opp.opportunity_id)}
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-primary-50 rounded-lg flex items-center justify-center text-lg">
                    {categoryIcons[opp.category] || '⚙️'}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-400">#{opp.priority_rank}</span>
                      <h4 className="font-semibold text-gray-900">{opp.title}</h4>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${difficultyColors[opp.difficulty]}`}>
                        {opp.difficulty}
                      </span>
                      <span className="text-xs text-gray-500">{opp.time_to_implement}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-lg font-bold text-green-600">
                      +${opp.annual_impact.toLocaleString()}<span className="text-xs text-gray-400">/yr</span>
                    </p>
                    <div className="flex items-center gap-1">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary-600 h-2 rounded-full"
                          style={{ width: `${opp.roi_score}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">{opp.roi_score}</span>
                    </div>
                  </div>
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </div>
              
              {isExpanded && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-sm text-gray-600 mb-4">{opp.description}</p>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Monthly Impact</p>
                      <p className="text-lg font-bold text-green-600">${opp.monthly_impact.toLocaleString()}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Annual Impact</p>
                      <p className="text-lg font-bold text-green-600">${opp.annual_impact.toLocaleString()}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">ROI Score</p>
                      <p className="text-lg font-bold text-primary-600">{opp.roi_score}/100</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
