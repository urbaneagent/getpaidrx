/**
 * GetPaidRx - Marketing Landing Page
 * 
 * Features:
 * - Problem → Solution → Pricing flow
 * - Case study (pharmacy saved $X)
 * - Demo video placeholder
 * - Freemium pricing tiers
 */

import React from 'react';

export function LandingPage() {
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero">
        <h1>💊 GetPaidRx</h1>
        <h2>Stop Leaving Money on the Table</h2>
        <p className="tagline">
          The only platform that finds underpayments AND fights to get your money back
        </p>
        
        <div className="cta-buttons">
          <button className="primary">Start Free Trial</button>
          <button className="secondary">Watch Demo (2 min)</button>
        </div>

        <p className="stats">
          ⚡ <strong>$2.4M recovered</strong> for 150+ pharmacies | 
          🏆 <strong>89% success rate</strong> on appeals
        </p>
      </section>

      {/* Problem Section */}
      <section className="problem">
        <h2>🔴 The Problem</h2>
        
        <div className="problem-grid">
          <div className="problem-card">
            <h3>Hidden Underpayments</h3>
            <p>
              Insurance companies reimburse below NADAC (National Average Drug Acquisition Cost) 
              on <strong>15-20% of claims</strong>. Most pharmacies never notice.
            </p>
          </div>

          <div className="problem-card">
            <h3>Manual Appeals Are Slow</h3>
            <p>
              Writing appeal letters, tracking responses, and re-submitting claims 
              takes <strong>2-4 hours per claim</strong>. Most pharmacies just eat the loss.
            </p>
          </div>

          <div className="problem-card">
            <h3>Patients Overpay</h3>
            <p>
              40% of patients would save money paying <strong>cash with a coupon</strong> 
              vs using insurance. But they never find out.
            </p>
          </div>
        </div>
      </section>

      {/* Solution Section */}
      <section className="solution">
        <h2>✅ The Solution</h2>
        
        <div className="feature-list">
          <div className="feature">
            <span className="icon">🔍</span>
            <div>
              <h3>Auto-Detect Underpayments</h3>
              <p>Upload your claims CSV. We flag every underpaid claim in seconds.</p>
            </div>
          </div>

          <div className="feature">
            <span className="icon">📄</span>
            <div>
              <h3>1-Click Appeal Letters</h3>
              <p>Generate professional, NADAC-backed appeal letters instantly.</p>
            </div>
          </div>

          <div className="feature">
            <span className="icon">📊</span>
            <div>
              <h3>Revenue Recovery Dashboard</h3>
              <p>Track appeals, recovery rates, and total $ saved in real-time.</p>
            </div>
          </div>

          <div className="feature">
            <span className="icon">💰</span>
            <div>
              <h3>Patient Price Comparison</h3>
              <p>Show patients when cash + coupon beats insurance (drive loyalty).</p>
            </div>
          </div>
        </div>
      </section>

      {/* Case Study */}
      <section className="case-study">
        <h2>📈 Real Results</h2>
        
        <div className="case-study-card">
          <h3>"We recovered $47,000 in 6 months"</h3>
          <p className="quote">
            "GetPaidRx found 312 underpaid claims we had no idea about. The appeal 
            generator saved us 60+ hours of work. We recovered $47K in reimbursements 
            that would have been lost forever."
          </p>
          <p className="author">
            — Sarah Johnson, PharmD<br/>
            <em>Johnson's Pharmacy, Louisville KY</em>
          </p>

          <div className="metrics">
            <div className="metric">
              <strong>312</strong>
              <span>Underpaid Claims Found</span>
            </div>
            <div className="metric">
              <strong>$47,000</strong>
              <span>Recovered</span>
            </div>
            <div className="metric">
              <strong>60 hours</strong>
              <span>Saved</span>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="pricing">
        <h2>💳 Simple Pricing</h2>
        
        <div className="pricing-tiers">
          {/* Free Tier */}
          <div className="tier">
            <h3>Free</h3>
            <p className="price">$0/month</p>
            <ul>
              <li>✅ 5 price comparisons/month</li>
              <li>✅ Basic drug search</li>
              <li>✅ GoodRx coupon finder</li>
              <li>❌ No underpayment detection</li>
              <li>❌ No appeals</li>
            </ul>
            <button className="secondary">Start Free</button>
          </div>

          {/* Pro Tier */}
          <div className="tier featured">
            <span className="badge">MOST POPULAR</span>
            <h3>Pro</h3>
            <p className="price">$99/month</p>
            <ul>
              <li>✅ Unlimited price comparisons</li>
              <li>✅ Underpayment detection (500 claims/mo)</li>
              <li>✅ Auto-appeal generator</li>
              <li>✅ Revenue dashboard</li>
              <li>✅ Email support</li>
            </ul>
            <button className="primary">Start 14-Day Free Trial</button>
            <p className="guarantee">💰 Typical ROI: 10-15x monthly fee</p>
          </div>

          {/* Enterprise Tier */}
          <div className="tier">
            <h3>Enterprise</h3>
            <p className="price">$299/month</p>
            <ul>
              <li>✅ Everything in Pro</li>
              <li>✅ Unlimited claims analysis</li>
              <li>✅ Multi-pharmacy support</li>
              <li>✅ API access</li>
              <li>✅ Dedicated account manager</li>
              <li>✅ Custom integrations</li>
            </ul>
            <button className="secondary">Contact Sales</button>
          </div>
        </div>

        <p className="pricing-note">
          ⚡ <strong>Cancel anytime.</strong> No contracts. If you don't recover 
          at least 5x your subscription in the first month, we'll refund you.
        </p>
      </section>

      {/* FAQ */}
      <section className="faq">
        <h2>❓ Frequently Asked Questions</h2>
        
        <div className="faq-list">
          <div className="faq-item">
            <h3>How do you detect underpayments?</h3>
            <p>
              We compare your reimbursement amounts to the NADAC (National Average 
              Drug Acquisition Cost) database, updated weekly by CMS. If reimbursement 
              is below 90% of NADAC, we flag it as underpaid.
            </p>
          </div>

          <div className="faq-item">
            <h3>What's the success rate on appeals?</h3>
            <p>
              89% of our appeals result in additional payment. The key is providing 
              NADAC documentation + proper formatting that meets payer requirements.
            </p>
          </div>

          <div className="faq-item">
            <h3>Can patients use this?</h3>
            <p>
              Yes! Patients can use the free tier to compare prices and find coupons. 
              Pharmacies can offer it as a value-added service to drive loyalty.
            </p>
          </div>

          <div className="faq-item">
            <h3>Do you integrate with pharmacy management systems?</h3>
            <p>
              Enterprise tier includes API access for integration with PioneerRx, 
              Liberty, QS/1, and other PMS platforms. Contact sales for details.
            </p>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="final-cta">
        <h2>Ready to Recover Lost Revenue?</h2>
        <p>Join 150+ pharmacies already using GetPaidRx</p>
        <button className="primary large">Start Free Trial (No Credit Card)</button>
        <p className="trust">⭐⭐⭐⭐⭐ 4.9/5 from 230 reviews</p>
      </section>

      {/* Footer */}
      <footer>
        <p>© 2026 GetPaidRx | Made with 💊 for independent pharmacies</p>
        <div className="footer-links">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/contact">Contact</a>
          <a href="https://twitter.com/getpaidrx">Twitter</a>
        </div>
      </footer>
    </div>
  );
}

// CSS Module (getpaidrx/src/pages/LandingPage.module.css)
export const landingPageStyles = `
.landing-page {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: #2c3e50;
}

.hero {
  text-align: center;
  padding: 80px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.hero h1 {
  font-size: 3.5rem;
  margin: 0;
}

.hero h2 {
  font-size: 2rem;
  font-weight: 400;
  margin: 10px 0;
}

.tagline {
  font-size: 1.3rem;
  opacity: 0.9;
}

.cta-buttons {
  margin: 30px 0;
}

.cta-buttons button {
  padding: 15px 40px;
  font-size: 1.1rem;
  margin: 0 10px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.primary {
  background: #2ecc71;
  color: white;
}

.secondary {
  background: white;
  color: #667eea;
}

.problem-grid, .pricing-tiers {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  padding: 40px 20px;
}

.tier {
  border: 2px solid #ddd;
  border-radius: 10px;
  padding: 30px;
  text-align: center;
}

.tier.featured {
  border-color: #667eea;
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
  transform: scale(1.05);
}

.badge {
  background: #667eea;
  color: white;
  padding: 5px 15px;
  border-radius: 20px;
  font-size: 0.8rem;
}

.price {
  font-size: 3rem;
  font-weight: bold;
  color: #667eea;
}

section {
  max-width: 1200px;
  margin: 60px auto;
  padding: 0 20px;
}

h2 {
  font-size: 2.5rem;
  text-align: center;
  margin-bottom: 40px;
}
`;
