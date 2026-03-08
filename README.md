# GetPaidRx 💊

**Pharmacy Underpayment Recovery & Drug Price Comparison Platform**

The compliance verification layer for the new PBM transparency rules (Consolidated Appropriations Act 2026).

**Live Production:** https://getpaidrx.onrender.com
**GitHub:** https://github.com/urbaneagent/getpaidrx

## ⚡ New Features (2026-03-08)

### 🏛️ CMS Complaint Report Generator
- **Formal PBM Violation Reports** — Generate formatted complaints for CMS submission based on the new PBM transparency law
- **Automated Documentation** — Includes claim details, NADAC analysis, legal basis, and submission instructions
- **Multi-Claim Support** — Aggregate underpayment data across multiple claims and payers
- **Endpoint:** `POST /api/cms-complaint`

### 📊 Dashboard Metrics API
- **Real-time Analytics** — Track total recovered, pending appeals, success rate
- **Per-Payer Breakdown** — Identify which PBMs systematically underpay
- **Top Underpaid Drugs** — See which medications are most frequently underpaid
- **Endpoint:** `GET /api/metrics`

### ✅ Enhanced CSV Validation
- **Intelligent Column Detection** — Supports 20+ column name variations (ndc, ndc_code, quantity, qty, etc.)
- **Helpful Error Messages** — Clear suggestions for fixing format issues
- **Format Examples** — Shows expected CSV structure when validation fails
- **Endpoint:** `POST /api/validate-csv`

## Features

### For Pharmacies
- **Underpayment Detection** — Upload claims CSV, compare against NADAC benchmarks, flag underpaid claims
- **1-Click Appeal Letters** — Generate professional, NADAC-backed appeal letters with CMS documentation
- **CMS Complaint Generator** — Create formal PBM violation reports for CMS submission (NEW)
- **Revenue Recovery Dashboard** — Track underpayments, appeals, and recovered revenue with detailed metrics (ENHANCED)
- **CSV/PDF Export** — Export underpaid claims and appeal letters
- **Smart CSV Validation** — Upload validation with helpful error messages and format suggestions (ENHANCED)

### For Patients
- **Drug Price Comparison** — Compare cash, insurance, and coupon prices across pharmacies
- **Prescription OCR** — Upload a prescription photo for auto-fill (coming soon)
- **Coupon Finder** — Find GoodRx, SingleCare, and other discount codes

### Live NADAC API Integration
- **Drug Search** — `GET /api/nadac/search?q=metformin` — queries CMS's live NADAC database (1.8M+ records)
- **NDC Lookup** — `GET /api/nadac/search?ndc=00002446230` — lookup specific NDC codes
- **Rate Check** — `POST /api/nadac/check` — compare actual reimbursement against current NADAC rate
- **Fallback** — automatically falls back to local database if CMS API is unavailable

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Backend:** Express, TypeScript
- **Data:** NADAC (CMS National Average Drug Acquisition Cost) database
- **Testing:** Vitest, Supertest (42 comprehensive API tests)

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Run frontend dev server (http://localhost:5173)
npm run dev

# Run backend API (http://localhost:3001) - separate terminal
npm run server

# Or run both concurrently
npm run dev:full

# Run tests
npm test
```

### Production Build

```bash
# Build frontend and backend
npm run build

# Start production server
npm start
```

## API Endpoints

### Claims Analysis
- `POST /api/analyze` — Analyze claims for underpayment
- `POST /api/cms-complaint` — Generate CMS complaint report
- `POST /api/appeal` — Generate appeal letter for single claim
- `POST /api/validate-csv` — Validate CSV format before upload

### NADAC Data
- `GET /api/nadac` — Get all NADAC data or by NDC
- `GET /api/nadac/search?q=metformin` — Search drugs by name
- `GET /api/nadac/search?ndc=00002446230` — Lookup by NDC
- `POST /api/nadac/check` — Check if reimbursement is below NADAC

### Metrics & Analytics
- `GET /api/metrics` — Dashboard metrics (total recovered, by payer, etc.)

### Price Comparison
- `POST /api/compare` — Compare drug prices across pharmacies

### Health Check
- `GET /api/health` — API health status

## Deployment Guide

### Deploy to Render

1. **Connect GitHub Repository**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub account and select the `getpaidrx` repository

2. **Configure Build Settings**
   ```
   Name: getpaidrx
   Environment: Node
   Build Command: npm install && npm run build
   Start Command: npm start
   ```

3. **Environment Variables**
   ```
   NODE_ENV=production
   PORT=3001
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy
   - Your app will be live at `https://getpaidrx.onrender.com`

### Deploy to Vercel (Alternative)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

### Deploy to Heroku (Alternative)

```bash
# Login to Heroku
heroku login

# Create app
heroku create getpaidrx

# Deploy
git push heroku master

# Open app
heroku open
```

### Environment Variables for Production

```bash
NODE_ENV=production
PORT=3001  # or your preferred port
```

## Testing

The project includes comprehensive API tests covering:
- Health checks and basic endpoints
- NADAC database lookup and search
- Claims analysis and underpayment detection
- Appeal letter generation
- CMS complaint report generation
- CSV validation with error handling
- Price comparison
- Metrics tracking

Run tests with:
```bash
npm test
```

## CSV Upload Format

Your CSV must include these required columns (various name formats supported):

**Required:**
- `ndc` (or ndc_code, ndc_number, national_drug_code)
- `quantity` (or qty, units, count)
- `reimbursement` (or reimb, amount, paid, paid_amount)

**Optional (recommended):**
- `drug_name` (or drugname, medication, med)
- `payer` (or payer_name, pbm, insurance)
- `date_of_service` (or dos, service_date, fill_date)

**Example CSV:**
```csv
ndc,quantity,reimbursement,drug_name,payer,date_of_service
00002-4462-30,90,2.50,Metformin HCl 500mg,Blue Cross,2026-01-15
00071-0155-23,30,1.20,Lisinopril 10mg,UnitedHealthcare,2026-01-16
```

## Pricing

| Plan | Price | Features |
|------|-------|----------|
| Free | $0/mo | 5 price comparisons/month |
| Pro | $99/mo | 500 claims/month, appeal generator, dashboard, CMS reports |
| Enterprise | $299/mo | Unlimited, API access, multi-pharmacy, priority support |

## Legal Compliance

This tool is designed to help pharmacies comply with and leverage the **Consolidated Appropriations Act of 2026**, which mandates:
- PBM reimbursement transparency
- Prohibition of systematic underpayment below NADAC benchmarks
- Formal pathway for reporting PBM violations to CMS

**Disclaimer:** This tool provides analysis based on publicly available NADAC data. Consult with legal counsel before submitting formal complaints to CMS.

## Support

- **GitHub Issues:** https://github.com/urbaneagent/getpaidrx/issues
- **Email:** support@getpaidrx.com
- **Documentation:** https://getpaidrx.onrender.com/docs

## License

Proprietary. © 2026 GetPaidRx.
