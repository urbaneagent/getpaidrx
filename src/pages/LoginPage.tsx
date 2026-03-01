import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Pill, ArrowLeft } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed');
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

          <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome back</h1>
          <p className="text-gray-600 mb-8">Sign in to access your pharmacy dashboard.</p>

          {error && (
            <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
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
                'Sign In'
              )}
            </button>
          </form>

          <p className="mt-6 text-sm text-gray-600 text-center">
            Don't have an account?{' '}
            <Link to="/signup" className="text-primary-600 font-medium hover:text-primary-700">
              Join the Beta
            </Link>
          </p>
        </div>
      </div>

      {/* Right panel - branding */}
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-primary-600 to-emerald-600 p-16 items-center justify-center">
        <div className="max-w-md text-white">
          <h2 className="text-3xl font-bold mb-4">Recover What You're Owed</h2>
          <p className="text-lg text-primary-100 leading-relaxed">
            PBM reform is now law. GetPaidRx helps you verify every reimbursement
            against NADAC benchmarks and recover underpayments automatically.
          </p>
          <div className="mt-8 space-y-4">
            {[
              'Upload claims → detect underpayments',
              'Generate appeal letters in one click',
              'Track recovery in real-time',
            ].map(item => (
              <div key={item} className="flex items-center gap-3 text-primary-100">
                <div className="w-2 h-2 rounded-full bg-primary-300" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
