import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useClaimsStore, Claim, AppealLetter } from '../../stores/claimsStore';
import {
  AlertTriangle,
  FileText,
  Download,
  Copy,
  CheckCircle2,
  X,
  Filter,
  ArrowUpDown,
  Upload,
  ArrowRight,
} from 'lucide-react';

export default function ResultsPage() {
  const { analyzedClaims, generateAppealLetter, exportUnderpaidCSV, getStats } = useClaimsStore();
  const stats = getStats();

  const [filter, setFilter] = useState<'all' | 'underpaid' | 'ok'>('all');
  const [sortBy, setSortBy] = useState<'amount' | 'drug' | 'date'>('amount');
  const [appealModal, setAppealModal] = useState<AppealLetter | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredClaims = useMemo(() => {
    let claims = [...analyzedClaims];
    
    if (filter === 'underpaid') claims = claims.filter(c => c.isUnderpaid);
    if (filter === 'ok') claims = claims.filter(c => !c.isUnderpaid);
    
    claims.sort((a, b) => {
      if (sortBy === 'amount') return (b.underpaymentAmount || 0) - (a.underpaymentAmount || 0);
      if (sortBy === 'drug') return a.drugName.localeCompare(b.drugName);
      return b.dateDispensed.localeCompare(a.dateDispensed);
    });

    return claims;
  }, [analyzedClaims, filter, sortBy]);

  const handleGenerateAppeal = (claim: Claim) => {
    const appeal = generateAppealLetter(claim);
    setAppealModal(appeal);
  };

  const handleCopyAppeal = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportCSV = () => {
    const csv = exportUnderpaidCSV();
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `underpaid-claims-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (analyzedClaims.length === 0) {
    return (
      <div className="max-w-xl mx-auto text-center py-20">
        <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <Upload className="w-8 h-8 text-gray-400" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-3">No Claims Analyzed Yet</h2>
        <p className="text-gray-600 mb-8">Upload your claims CSV first, then come back to see the results.</p>
        <Link to="/dashboard/upload" className="btn-primary inline-flex items-center gap-2">
          Upload Claims
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claims Analysis Results</h1>
          <p className="text-gray-600 text-sm mt-1">
            {stats.underpaidClaims} underpaid claims found — ${stats.totalUnderpayment.toFixed(2)} in potential recovery
          </p>
        </div>
        <button
          onClick={handleExportCSV}
          className="btn-secondary text-sm py-2.5 flex items-center gap-2 self-start"
        >
          <Download className="w-4 h-4" />
          Export Underpaid CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          {([['all', 'All Claims'], ['underpaid', 'Underpaid'], ['ok', 'Paid OK']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`text-sm font-medium px-3 py-1.5 rounded-md transition-colors ${
                filter === key ? 'bg-white shadow-sm text-gray-900' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {label}
              {key === 'underpaid' && ` (${stats.underpaidClaims})`}
            </button>
          ))}
        </div>

        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value as any)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white"
        >
          <option value="amount">Sort by Underpayment</option>
          <option value="drug">Sort by Drug Name</option>
          <option value="date">Sort by Date</option>
        </select>
      </div>

      {/* Claims table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-600">Status</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-600">Claim ID</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-600">Drug</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-600">NDC</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">Qty</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">Paid</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">Expected</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">Shortfall</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredClaims.map(claim => (
                <tr key={claim.claimId} className={`hover:bg-gray-50 ${claim.isUnderpaid ? 'bg-red-50/30' : ''}`}>
                  <td className="py-3 px-4">
                    {claim.isUnderpaid ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">
                        <AlertTriangle className="w-3 h-3" />
                        Underpaid
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        OK
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs">{claim.claimId}</td>
                  <td className="py-3 px-4 font-medium">{claim.drugName}</td>
                  <td className="py-3 px-4 font-mono text-xs text-gray-500">{claim.ndc}</td>
                  <td className="py-3 px-4 text-right">{claim.quantity}</td>
                  <td className="py-3 px-4 text-right">${claim.reimbursement.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right">
                    {claim.expectedReimbursement ? `$${claim.expectedReimbursement.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-3 px-4 text-right font-semibold">
                    {claim.isUnderpaid ? (
                      <span className="text-red-600">${(claim.underpaymentAmount || 0).toFixed(2)}</span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {claim.isUnderpaid && (
                      <button
                        onClick={() => handleGenerateAppeal(claim)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700 bg-primary-50 hover:bg-primary-100 px-3 py-1.5 rounded-md transition-colors"
                      >
                        <FileText className="w-3 h-3" />
                        Appeal
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Appeal Letter Modal */}
      {appealModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-bold text-gray-900">Appeal Letter — {appealModal.claimId}</h2>
              <button
                onClick={() => setAppealModal(null)}
                className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">
                {appealModal.letterText}
              </pre>
            </div>
            <div className="flex items-center gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
              <button
                onClick={() => handleCopyAppeal(appealModal.letterText, appealModal.claimId)}
                className="btn-primary text-sm py-2.5 flex items-center gap-2"
              >
                {copiedId === appealModal.claimId ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy to Clipboard
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  const blob = new Blob([appealModal.letterText], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `appeal-${appealModal.claimId}.txt`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="btn-secondary text-sm py-2.5 flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
