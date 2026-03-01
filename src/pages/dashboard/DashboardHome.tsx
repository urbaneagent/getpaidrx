import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useClaimsStore } from '../../stores/claimsStore';
import {
  Upload,
  FileSearch,
  DollarSign,
  FileText,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  BarChart3,
} from 'lucide-react';

export default function DashboardHome() {
  const { user } = useAuth();
  const { analyzedClaims, getStats } = useClaimsStore();
  const stats = getStats();

  const hasData = analyzedClaims.length > 0;

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back{user?.name ? `, ${user.name.split(' ')[0]}` : ''}
        </h1>
        <p className="text-gray-600 mt-1">
          {hasData
            ? 'Here\'s your pharmacy revenue recovery overview.'
            : 'Get started by uploading your claims data.'}
        </p>
      </div>

      {!hasData ? (
        /* Empty state */
        <div className="card p-12 text-center">
          <div className="w-20 h-20 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Upload className="w-10 h-10 text-primary-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-3">Upload Your First Claims File</h2>
          <p className="text-gray-600 max-w-md mx-auto mb-8">
            Export your claims data as a CSV from your pharmacy management system,
            then upload it here. We'll analyze every claim against NADAC benchmarks.
          </p>
          <Link to="/dashboard/upload" className="btn-primary inline-flex items-center gap-2">
            Upload Claims CSV
            <ArrowRight className="w-4 h-4" />
          </Link>
          <div className="mt-8 p-4 bg-gray-50 rounded-lg max-w-lg mx-auto">
            <p className="text-xs text-gray-500 font-medium mb-2">Expected CSV format:</p>
            <code className="text-xs text-gray-600">
              claimId, ndc, drugName, quantity, dateDispensed, reimbursement
            </code>
          </div>
        </div>
      ) : (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">Total Claims</span>
                <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
                  <BarChart3 className="w-4 h-4 text-blue-600" />
                </div>
              </div>
              <p className="text-3xl font-bold text-gray-900">{stats.totalClaims}</p>
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">Underpaid Claims</span>
                <div className="w-8 h-8 bg-red-50 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                </div>
              </div>
              <p className="text-3xl font-bold text-red-600">{stats.underpaidClaims}</p>
              <p className="text-xs text-gray-500 mt-1">
                {stats.totalClaims > 0
                  ? `${((stats.underpaidClaims / stats.totalClaims) * 100).toFixed(1)}% of claims`
                  : ''}
              </p>
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">Total Underpayment</span>
                <div className="w-8 h-8 bg-orange-50 rounded-lg flex items-center justify-center">
                  <DollarSign className="w-4 h-4 text-orange-600" />
                </div>
              </div>
              <p className="text-3xl font-bold text-orange-600">
                ${stats.totalUnderpayment.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">Appeals Generated</span>
                <div className="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
                  <FileText className="w-4 h-4 text-green-600" />
                </div>
              </div>
              <p className="text-3xl font-bold text-green-600">{stats.appealsGenerated}</p>
            </div>
          </div>

          {/* Quick actions */}
          <div className="grid sm:grid-cols-3 gap-4">
            <Link to="/dashboard/upload" className="card hover:border-primary-300 p-5 group">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center group-hover:bg-primary-100 transition-colors">
                  <Upload className="w-5 h-5 text-primary-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">Upload More Claims</p>
                  <p className="text-xs text-gray-500">Analyze another CSV file</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-400 ml-auto" />
              </div>
            </Link>

            <Link to="/dashboard/results" className="card hover:border-primary-300 p-5 group">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                  <FileSearch className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">View Results</p>
                  <p className="text-xs text-gray-500">See all underpaid claims</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-400 ml-auto" />
              </div>
            </Link>

            <Link to="/dashboard/compare" className="card hover:border-primary-300 p-5 group">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center group-hover:bg-purple-100 transition-colors">
                  <TrendingUp className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900 text-sm">Compare Prices</p>
                  <p className="text-xs text-gray-500">Find best drug prices</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-400 ml-auto" />
              </div>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
