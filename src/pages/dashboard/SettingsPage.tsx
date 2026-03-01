import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useClaimsStore } from '../../stores/claimsStore';
import {
  User,
  Building2,
  Mail,
  Shield,
  Trash2,
  CheckCircle2,
  CreditCard,
  Bell,
} from 'lucide-react';

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { clearAll } = useClaimsStore();
  const [saved, setSaved] = useState(false);
  const [name, setName] = useState(user?.name || '');
  const [pharmacyName, setPharmacyName] = useState(user?.pharmacyName || '');

  const handleSave = () => {
    // In production: API call to update user profile
    if (user) {
      const stored = JSON.parse(localStorage.getItem('getpaidrx_user') || '{}');
      stored.name = name;
      stored.pharmacyName = pharmacyName;
      localStorage.setItem('getpaidrx_user', JSON.stringify(stored));
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleClearData = () => {
    if (confirm('Are you sure you want to clear all analyzed claims data? This cannot be undone.')) {
      clearAll();
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage your account and preferences.</p>
      </div>

      {/* Profile */}
      <div className="card space-y-5">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <User className="w-5 h-5 text-gray-400" />
          Profile
        </h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <div className="flex items-center gap-2">
              <input
                type="email"
                value={user?.email || ''}
                className="input-field bg-gray-50"
                disabled
              />
              <Mail className="w-5 h-5 text-gray-400" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Pharmacy Name</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={pharmacyName}
                onChange={e => setPharmacyName(e.target.value)}
                className="input-field"
                placeholder="Your pharmacy name"
              />
              <Building2 className="w-5 h-5 text-gray-400" />
            </div>
          </div>
          <button
            onClick={handleSave}
            className="btn-primary text-sm py-2.5 flex items-center gap-2"
          >
            {saved ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                Saved!
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>

      {/* Plan */}
      <div className="card space-y-4">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-gray-400" />
          Subscription
        </h2>
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div>
            <p className="font-semibold text-gray-900">
              {user?.plan === 'enterprise' ? 'Enterprise Plan' :
               user?.plan === 'pro' ? 'Pro Plan' : 'Free Plan'}
            </p>
            <p className="text-sm text-gray-500 mt-0.5">
              {user?.plan === 'free'
                ? '5 price comparisons/month'
                : user?.plan === 'pro'
                ? '500 claims/month, unlimited comparisons'
                : 'Unlimited everything'}
            </p>
          </div>
          {user?.plan === 'free' && (
            <button className="btn-primary text-sm py-2">
              Upgrade to Pro
            </button>
          )}
        </div>
      </div>

      {/* Notifications */}
      <div className="card space-y-4">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <Bell className="w-5 h-5 text-gray-400" />
          Notifications
        </h2>
        <div className="space-y-3">
          {[
            { label: 'New underpayment alerts', desc: 'Get notified when we detect new underpayments', checked: true },
            { label: 'Appeal status updates', desc: 'Track when appeals are responded to', checked: true },
            { label: 'Weekly summary', desc: 'Receive a weekly recovery summary email', checked: false },
          ].map(item => (
            <div key={item.label} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">{item.label}</p>
                <p className="text-xs text-gray-500">{item.desc}</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" defaultChecked={item.checked} className="sr-only peer" />
                <div className="w-11 h-6 bg-gray-200 peer-focus:ring-2 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
              </label>
            </div>
          ))}
        </div>
      </div>

      {/* Data Management */}
      <div className="card space-y-4">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <Shield className="w-5 h-5 text-gray-400" />
          Data Management
        </h2>
        <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg">
          <div>
            <p className="font-medium text-red-800">Clear All Claims Data</p>
            <p className="text-sm text-red-600 mt-0.5">
              Remove all analyzed claims and generated appeals
            </p>
          </div>
          <button
            onClick={handleClearData}
            className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 bg-white border border-red-200 px-4 py-2 rounded-lg hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Clear Data
          </button>
        </div>
      </div>
    </div>
  );
}
