import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Package,
  TrendingDown,
  Users,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';

interface ShortageItem {
  shortage_id: string;
  fda_id: string;
  ndc: string;
  drug_name: string;
  generic_name: string;
  manufacturer: string;
  severity: string;
  severity_info: {
    label: string;
    color: string;
    description: string;
  };
  reason: string;
  reported_date: string;
  estimated_resolution: string;
  days_supply_remaining: number;
  inventory_status: string;
  alternative_count: number;
  alternatives: Array<{
    name: string;
    ndc: string;
    cost_diff_pct: number;
  }>;
}

interface ImpactData {
  total_active_shortages: number;
  critical_shortages: number;
  major_shortages: number;
  estimated_monthly_revenue_at_risk: number;
  estimated_affected_patients: number;
  recommendations: Array<{
    priority: string;
    action: string;
    details: string;
    drugs: string[];
  }>;
}

const severityColors: Record<string, { bg: string; text: string; badge: string }> = {
  CRITICAL: { bg: 'bg-red-50', text: 'text-red-700', badge: 'bg-red-100 text-red-800' },
  MAJOR: { bg: 'bg-orange-50', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-800' },
  MODERATE: { bg: 'bg-blue-50', text: 'text-blue-700', badge: 'bg-blue-100 text-blue-800' },
  MINOR: { bg: 'bg-green-50', text: 'text-green-700', badge: 'bg-green-100 text-green-800' },
};

const inventoryStatusLabels: Record<string, { label: string; color: string }> = {
  OUT_OF_STOCK: { label: 'Out of Stock', color: 'text-red-600' },
  CRITICAL_LOW: { label: 'Critical Low', color: 'text-red-500' },
  LOW: { label: 'Low', color: 'text-orange-500' },
  ADEQUATE: { label: 'Adequate', color: 'text-green-500' },
  COMFORTABLE: { label: 'Comfortable', color: 'text-green-600' },
};

export default function ShortageTracker() {
  const [shortages, setShortages] = useState<ShortageItem[]>([]);
  const [impact, setImpact] = useState<ImpactData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [shortageResp, impactResp] = await Promise.all([
        fetch('/api/v1/shortages/active'),
        fetch('/api/v1/shortages/impact'),
      ]);
      const shortageData = await shortageResp.json();
      const impactData = await impactResp.json();
      setShortages(shortageData.shortages || []);
      setImpact(impactData);
    } catch (err) {
      console.error('Failed to load shortage data:', err);
    }
    setLoading(false);
  };

  const filtered = filterSeverity === 'ALL'
    ? shortages
    : shortages.filter(s => s.severity === filterSeverity);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
        <span className="ml-2 text-gray-500">Loading shortage data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Drug Shortage Tracker</h1>
          <p className="text-gray-600 mt-1">
            Monitor active FDA shortages and their impact on your pharmacy.
          </p>
        </div>
        <button
          onClick={loadData}
          className="btn-secondary inline-flex items-center gap-2 text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Impact Summary Cards */}
      {impact && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Active Shortages</span>
              <div className="w-8 h-8 bg-red-50 rounded-lg flex items-center justify-center">
                <AlertTriangle className="w-4 h-4 text-red-600" />
              </div>
            </div>
            <p className="text-3xl font-bold text-gray-900">{impact.total_active_shortages}</p>
            <p className="text-xs text-red-600 mt-1">
              {impact.critical_shortages} critical, {impact.major_shortages} major
            </p>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Revenue at Risk</span>
              <div className="w-8 h-8 bg-orange-50 rounded-lg flex items-center justify-center">
                <TrendingDown className="w-4 h-4 text-orange-600" />
              </div>
            </div>
            <p className="text-3xl font-bold text-orange-600">
              ${impact.estimated_monthly_revenue_at_risk.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500 mt-1">Monthly estimate</p>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Patients Affected</span>
              <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
                <Users className="w-4 h-4 text-blue-600" />
              </div>
            </div>
            <p className="text-3xl font-bold text-blue-600">{impact.estimated_affected_patients}</p>
            <p className="text-xs text-gray-500 mt-1">Estimated patients</p>
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Alternatives</span>
              <div className="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
                <Package className="w-4 h-4 text-green-600" />
              </div>
            </div>
            <p className="text-3xl font-bold text-green-600">
              {shortages.reduce((sum, s) => sum + s.alternative_count, 0)}
            </p>
            <p className="text-xs text-gray-500 mt-1">Available alternatives</p>
          </div>
        </div>
      )}

      {/* Recommendations */}
      {impact?.recommendations && impact.recommendations.length > 0 && (
        <div className="card bg-yellow-50 border-yellow-200">
          <h3 className="font-bold text-yellow-800 mb-3">⚡ Action Required</h3>
          <div className="space-y-2">
            {impact.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                  rec.priority === 'CRITICAL' ? 'bg-red-100 text-red-800' :
                  rec.priority === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  {rec.priority}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-900">{rec.action}</p>
                  <p className="text-xs text-gray-600">{rec.details}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Filter:</span>
        {['ALL', 'CRITICAL', 'MAJOR', 'MODERATE', 'MINOR'].map(sev => (
          <button
            key={sev}
            onClick={() => setFilterSeverity(sev)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              filterSeverity === sev
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {sev}
          </button>
        ))}
      </div>

      {/* Shortage List */}
      <div className="space-y-3">
        {filtered.map(shortage => {
          const colors = severityColors[shortage.severity] || severityColors.MODERATE;
          const invStatus = inventoryStatusLabels[shortage.inventory_status] || { label: 'Unknown', color: 'text-gray-500' };
          const isExpanded = expandedId === shortage.shortage_id;

          return (
            <div key={shortage.shortage_id} className={`card ${colors.bg} border`}>
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedId(isExpanded ? null : shortage.shortage_id)}
              >
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${colors.badge}`}>
                    {shortage.severity}
                  </span>
                  <div>
                    <h4 className="font-semibold text-gray-900">{shortage.drug_name}</h4>
                    <p className="text-xs text-gray-500">
                      {shortage.manufacturer} • {shortage.reason} • FDA: {shortage.fda_id}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className={`text-sm font-medium ${invStatus.color}`}>
                      {invStatus.label}
                    </span>
                    <p className="text-xs text-gray-500">
                      {shortage.days_supply_remaining > 0
                        ? `${shortage.days_supply_remaining} days supply`
                        : 'No stock'}
                    </p>
                  </div>
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </div>

              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-xs text-gray-500">Reported</p>
                      <p className="text-sm font-medium">{shortage.reported_date}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Est. Resolution</p>
                      <p className="text-sm font-medium">{shortage.estimated_resolution}</p>
                    </div>
                  </div>

                  {shortage.alternatives.length > 0 && (
                    <div>
                      <h5 className="text-sm font-semibold text-gray-700 mb-2">
                        Therapeutic Alternatives ({shortage.alternatives.length})
                      </h5>
                      <div className="space-y-2">
                        {shortage.alternatives.map((alt, i) => (
                          <div key={i} className="flex items-center justify-between bg-white rounded-lg p-3">
                            <div>
                              <p className="text-sm font-medium">{alt.name}</p>
                              <p className="text-xs text-gray-500">NDC: {alt.ndc}</p>
                            </div>
                            <span className={`text-sm font-semibold ${
                              alt.cost_diff_pct > 50 ? 'text-red-600' :
                              alt.cost_diff_pct > 0 ? 'text-orange-600' :
                              'text-green-600'
                            }`}>
                              {alt.cost_diff_pct > 0 ? '+' : ''}{alt.cost_diff_pct}% cost
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="card text-center py-12">
          <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-gray-500">No shortages found</h3>
          <p className="text-sm text-gray-400">
            {filterSeverity !== 'ALL'
              ? `No ${filterSeverity.toLowerCase()} shortages active.`
              : 'All drug supplies are currently adequate.'}
          </p>
        </div>
      )}
    </div>
  );
}
