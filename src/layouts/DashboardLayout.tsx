import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  Upload,
  BarChart3,
  Search,
  Settings,
  LogOut,
  Menu,
  X,
  Pill,
  ChevronRight,
} from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/dashboard/upload', icon: Upload, label: 'Upload Claims' },
  { to: '/dashboard/results', icon: BarChart3, label: 'Results' },
  { to: '/dashboard/compare', icon: Search, label: 'Compare Prices' },
  { to: '/dashboard/settings', icon: Settings, label: 'Settings' },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-100">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <Pill className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">GetPaid<span className="text-primary-600">Rx</span></span>
            <button className="ml-auto lg:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* User info */}
          <div className="px-6 py-4 border-b border-gray-100">
            <p className="font-medium text-gray-900 text-sm">{user?.name}</p>
            <p className="text-xs text-gray-500">{user?.pharmacyName || user?.email}</p>
            <span className={`
              inline-block mt-1 text-xs font-medium px-2 py-0.5 rounded-full
              ${user?.plan === 'enterprise' ? 'bg-purple-100 text-purple-700' :
                user?.plan === 'pro' ? 'bg-primary-100 text-primary-700' :
                'bg-gray-100 text-gray-600'}
            `}>
              {user?.plan === 'enterprise' ? '⚡ Enterprise' :
               user?.plan === 'pro' ? '🚀 Pro' : 'Free Plan'}
            </span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1">
            {navItems.map(({ to, icon: Icon, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-colors duration-150
                  ${isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}
                `}
              >
                <Icon className="w-5 h-5" />
                {label}
                <ChevronRight className="w-4 h-4 ml-auto opacity-0 group-hover:opacity-100" />
              </NavLink>
            ))}
          </nav>

          {/* Upgrade CTA (for free users) */}
          {user?.plan === 'free' && (
            <div className="mx-3 mb-3 p-4 bg-gradient-to-br from-primary-50 to-primary-100 rounded-xl">
              <p className="text-sm font-semibold text-primary-800">Upgrade to Pro</p>
              <p className="text-xs text-primary-600 mt-1">
                Analyze up to 500 claims/mo with auto-appeal generation.
              </p>
              <button className="mt-3 w-full btn-primary text-xs py-2">
                Upgrade — $99/mo
              </button>
            </div>
          )}

          {/* Logout */}
          <div className="px-3 pb-4">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
          <button
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-6 h-6 text-gray-600" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="hidden sm:inline">PBM Transparency Compliance Tool</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs font-medium">
              Beta
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
