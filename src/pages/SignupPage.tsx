import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Pill, ArrowLeft } from 'lucide-react';

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pharmacyName, setPharmacyName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      await signup(email, password, name, pharmacyName || undefined);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel - form */}
      <div className="flex-1 flex flex-col justify-center px-8 sm:px-16 lg:px-24 py-12">
        <Link to="/" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-12">
          <ArrowLeft className="w-4 h-4" /> Back to home
        </Link>

        <div className="max-w-md">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <Pill className="w-5 h-5 text-white" />
            </div>
            <span className="text-2xl font-bold text-gray-900">GetPaid<span className="text-primary-600">Rx</span></span>
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">Join the Beta</h1>
          <p className="text-gray-600 mb-8">Create your account and start recovering lost revenue.</p>

          {error && (
            <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                className="input-field"
                placeholder="Dr. Jane Smith"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="input-field"
                placeholder="you@pharmacy.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Pharmacy Name <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="text"
                value={pharmacyName}
                onChange={e => setPharmacyName(e.target.value)}
                className="input-field"
                placeholder="Smith's Pharmacy"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          <p className="mt-6 text-sm text-gray-600 text-center">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 font-medium hover:text-primary-700">
              Sign In
            </Link>
          </p>
        </div>
      </div>

      {/* Right panel - branding */}
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-primary-600 to-emerald-600 p-16 items-center justify-center">
        <div className="max-w-md text-white">
          <div className="inline-flex items-center gap-2 bg-white/20 text-sm font-medium px-4 py-2 rounded-full mb-6">
            🚀 Early Access Beta
          </div>
          <h2 className="text-3xl font-bold mb-4">Built for the New PBM Rules</h2>
          <p className="text-lg text-primary-100 leading-relaxed mb-8">
            The Consolidated Appropriations Act of 2026 mandates PBM transparency.
            GetPaidRx gives you the verification tools to ensure you're being paid fairly.
          </p>
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <span className="text-2xl">🆓</span>
              <div>
                <p className="font-semibold">Free tier available</p>
                <p className="text-sm text-primary-200">5 price comparisons/month, no credit card</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-2xl">⚡</span>
              <div>
                <p className="font-semibold">Set up in minutes</p>
                <p className="text-sm text-primary-200">Upload a CSV, see results instantly</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="text-2xl">📊</span>
              <div>
                <p className="font-semibold">Investor-backed roadmap</p>
                <p className="text-sm text-primary-200">Continuous improvements, API coming soon</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
