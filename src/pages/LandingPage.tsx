import React from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  FileSearch,
  FileText,
  BarChart3,
  DollarSign,
  ArrowRight,
  CheckCircle2,
  Pill,
  Zap,
  Users,
  TrendingUp,
  Scale,
} from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Navbar */}
      <nav className="fixed top-0 w-full bg-white/80 backdrop-blur-lg z-50 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <Pill className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">GetPaid<span className="text-primary-600">Rx</span></span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How It Works</a>
            <a href="#pricing" className="hover:text-gray-900 transition-colors">Pricing</a>
            <a href="#compliance" className="hover:text-gray-900 transition-colors">PBM Compliance</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Sign In
            </Link>
            <Link to="/signup" className="btn-primary text-sm py-2.5 px-6">
              Join the Beta
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto text-center">
          {/* Compliance badge */}
          <div className="inline-flex items-center gap-2 bg-emerald-50 text-emerald-700 text-sm font-medium px-4 py-2 rounded-full mb-8 animate-fade-in-up">
            <Scale className="w-4 h-4" />
            Built for the new PBM Transparency Rules (CAA 2026)
          </div>

          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 leading-tight animate-fade-in-up animate-delay-100">
            Stop Losing Money on{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-emerald-500">
              Underpaid Claims
            </span>
          </h1>

          <p className="mt-6 text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed animate-fade-in-up animate-delay-200">
            GetPaidRx detects pharmacy reimbursement underpayments, generates NADAC-backed appeal letters,
            and helps patients find the lowest drug prices — all in one platform.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up animate-delay-300">
            <Link to="/signup" className="btn-primary text-lg py-4 px-10 flex items-center gap-2">
              Join the Beta — It's Free
              <ArrowRight className="w-5 h-5" />
            </Link>
            <a href="#how-it-works" className="btn-secondary text-lg py-4 px-10">
              See How It Works
            </a>
          </div>

          <p className="mt-6 text-sm text-gray-500 animate-fade-in-up animate-delay-400">
            🔒 No credit card required · Free tier available · HIPAA-conscious design
          </p>
        </div>
      </section>

      {/* Problem Statement */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="section-title text-gray-900">
            The Problem Is Bigger Than You Think
          </h2>
          <p className="section-subtitle">
            PBMs underpay pharmacies billions annually. Most pharmacies don't have the tools to catch it.
          </p>

          <div className="grid md:grid-cols-3 gap-8 mt-8">
            <div className="card text-center p-8">
              <div className="w-14 h-14 bg-red-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                <DollarSign className="w-7 h-7 text-red-500" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Hidden Underpayments</h3>
              <p className="text-gray-600">
                Industry data shows 15-20% of pharmacy claims are reimbursed below NADAC.
                Without automated detection, these losses go unnoticed.
              </p>
            </div>

            <div className="card text-center p-8">
              <div className="w-14 h-14 bg-orange-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                <FileText className="w-7 h-7 text-orange-500" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Manual Appeals Drain Time</h3>
              <p className="text-gray-600">
                Writing appeal letters, gathering NADAC documentation, and tracking responses
                takes hours per claim. Most pharmacies just absorb the loss.
              </p>
            </div>

            <div className="card text-center p-8">
              <div className="w-14 h-14 bg-blue-50 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Users className="w-7 h-7 text-blue-500" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">Patients Overpay Too</h3>
              <p className="text-gray-600">
                Many patients would save money paying cash with a coupon instead of using insurance —
                but they never know to compare.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="section-title">Everything You Need to Recover Revenue</h2>
          <p className="section-subtitle">
            From detection to appeal to recovery — GetPaidRx handles the full workflow.
          </p>

          <div className="grid md:grid-cols-2 gap-8 mt-8">
            <div className="card flex gap-5 p-8">
              <div className="w-12 h-12 bg-primary-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <FileSearch className="w-6 h-6 text-primary-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Auto-Detect Underpayments</h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  Upload your claims CSV. We compare every claim against the NADAC database
                  and flag underpayments instantly — with the exact dollar amount you're owed.
                </p>
              </div>
            </div>

            <div className="card flex gap-5 p-8">
              <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <FileText className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">1-Click Appeal Letters</h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  Generate professional, NADAC-documented appeal letters for any flagged claim.
                  Includes CMS pricing data, proper formatting, and all required documentation.
                </p>
              </div>
            </div>

            <div className="card flex gap-5 p-8">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <BarChart3 className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Recovery Dashboard</h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  Track every underpaid claim, submitted appeal, and recovered dollar in real-time.
                  See your total revenue recovery at a glance with clear visualizations.
                </p>
              </div>
            </div>

            <div className="card flex gap-5 p-8">
              <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <DollarSign className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Patient Price Comparison</h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  Help patients find the best drug prices across pharmacies.
                  Compare cash, insurance, and coupon prices. Includes prescription photo OCR.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 bg-gray-50">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="section-title">How It Works</h2>
          <p className="section-subtitle">
            Three steps. Five minutes. Start recovering lost revenue today.
          </p>

          <div className="space-y-12 mt-12">
            {[
              {
                step: '01',
                title: 'Upload Your Claims',
                desc: 'Export claims data from your pharmacy management system as a CSV. Drag and drop it into GetPaidRx.',
                icon: Upload,
              },
              {
                step: '02',
                title: 'We Detect Underpayments',
                desc: 'Our engine compares each claim\'s reimbursement against the CMS NADAC database. Every underpaid claim is flagged with the exact shortfall amount.',
                icon: FileSearch,
              },
              {
                step: '03',
                title: 'Appeal & Recover',
                desc: 'Generate professional appeal letters with one click. Track submissions, responses, and recovered revenue from your dashboard.',
                icon: TrendingUp,
              },
            ].map(({ step, title, desc, icon: Icon }) => (
              <div key={step} className="flex items-start gap-6">
                <div className="flex-shrink-0 w-16 h-16 rounded-2xl bg-primary-600 flex items-center justify-center">
                  <span className="text-xl font-bold text-white">{step}</span>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">{title}</h3>
                  <p className="text-gray-600 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PBM Compliance Section */}
      <section id="compliance" className="py-20">
        <div className="max-w-5xl mx-auto px-6">
          <div className="card p-10 md:p-14 bg-gradient-to-br from-emerald-50 to-primary-50 border-emerald-200">
            <div className="flex items-center gap-3 mb-6">
              <Shield className="w-8 h-8 text-emerald-600" />
              <h2 className="text-3xl font-bold text-gray-900">The PBM Transparency Era Is Here</h2>
            </div>
            <p className="text-lg text-gray-700 leading-relaxed mb-6">
              The <strong>Consolidated Appropriations Act of 2026</strong> mandates unprecedented PBM transparency.
              Pharmacies now have the legal right to verify their reimbursements against published benchmarks.
            </p>
            <p className="text-lg text-gray-700 leading-relaxed mb-8">
              GetPaidRx is <strong>the compliance verification layer</strong> for these new rules —
              giving pharmacies the tools to audit every claim, catch every underpayment,
              and enforce fair reimbursement under the law.
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              {[
                'NADAC benchmark verification',
                'CMS-sourced pricing data',
                'Automated compliance documentation',
                'Appeal-ready evidence packages',
                'Audit trail for every claim',
                'PBM transparency rule alignment',
              ].map(item => (
                <div key={item} className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                  <span className="text-gray-700 font-medium">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="section-title">Simple, Transparent Pricing</h2>
          <p className="section-subtitle">
            Start free. Upgrade when you see the value. Cancel anytime.
          </p>

          <div className="grid md:grid-cols-3 gap-8 mt-8 max-w-5xl mx-auto">
            {/* Free */}
            <div className="card p-8 text-center">
              <h3 className="text-lg font-bold text-gray-900">Free</h3>
              <p className="text-4xl font-bold text-gray-900 mt-4">$0</p>
              <p className="text-gray-500 text-sm">forever</p>
              <ul className="mt-8 space-y-3 text-left text-sm">
                {[
                  '5 price comparisons / month',
                  'Basic drug search',
                  'Coupon finder',
                ].map(f => (
                  <li key={f} className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{f}</span>
                  </li>
                ))}
              </ul>
              <Link to="/signup" className="btn-secondary w-full mt-8 block text-center text-sm py-3">
                Get Started Free
              </Link>
            </div>

            {/* Pro */}
            <div className="card p-8 text-center border-2 border-primary-500 relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary-600 text-white text-xs font-bold px-4 py-1 rounded-full">
                RECOMMENDED
              </div>
              <h3 className="text-lg font-bold text-gray-900">Pro</h3>
              <p className="text-4xl font-bold text-gray-900 mt-4">$99</p>
              <p className="text-gray-500 text-sm">/ month</p>
              <ul className="mt-8 space-y-3 text-left text-sm">
                {[
                  'Unlimited price comparisons',
                  'Underpayment detection (500 claims/mo)',
                  '1-click appeal letter generator',
                  'Revenue recovery dashboard',
                  'CSV export & PDF appeals',
                  'Email support',
                ].map(f => (
                  <li key={f} className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{f}</span>
                  </li>
                ))}
              </ul>
              <Link to="/signup" className="btn-primary w-full mt-8 block text-center text-sm py-3">
                Start 14-Day Free Trial
              </Link>
            </div>

            {/* Enterprise */}
            <div className="card p-8 text-center">
              <h3 className="text-lg font-bold text-gray-900">Enterprise</h3>
              <p className="text-4xl font-bold text-gray-900 mt-4">$299</p>
              <p className="text-gray-500 text-sm">/ month</p>
              <ul className="mt-8 space-y-3 text-left text-sm">
                {[
                  'Everything in Pro',
                  'Unlimited claims analysis',
                  'Multi-pharmacy support',
                  'API access',
                  'Dedicated account manager',
                  'Custom PMS integrations',
                ].map(f => (
                  <li key={f} className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{f}</span>
                  </li>
                ))}
              </ul>
              <Link to="/signup" className="btn-secondary w-full mt-8 block text-center text-sm py-3">
                Contact Sales
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 bg-yellow-50 text-yellow-700 text-sm font-medium px-4 py-2 rounded-full mb-6">
            <Zap className="w-4 h-4" />
            Early Access — Limited Beta
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            Ready to Recover Lost Revenue?
          </h2>
          <p className="text-xl text-gray-600 mb-10">
            Join our early access beta and be among the first pharmacies to leverage
            automated underpayment detection under the new PBM transparency mandates.
          </p>
          <Link to="/signup" className="btn-primary text-lg py-4 px-12 inline-flex items-center gap-2">
            Join the Beta — Free to Start
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                <Pill className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-bold text-white">GetPaid<span className="text-primary-400">Rx</span></span>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Contact</a>
            </div>
            <p className="text-sm">© 2026 GetPaidRx. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
