# GetPaidRx 💊

**Pharmacy Underpayment Recovery & Drug Price Comparison Platform**

The compliance verification layer for the new PBM transparency rules (Consolidated Appropriations Act 2026).

## Features

### For Pharmacies
- **Underpayment Detection** — Upload claims CSV, compare against NADAC benchmarks, flag underpaid claims
- **1-Click Appeal Letters** — Generate professional, NADAC-backed appeal letters with CMS documentation
- **Revenue Recovery Dashboard** — Track underpayments, appeals, and recovered revenue
- **CSV/PDF Export** — Export underpaid claims and appeal letters

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

## Quick Start

```bash
# Install dependencies
npm install

# Run frontend dev server
npm run dev

# Run backend API (separate terminal)
npm run server

# Or run both
npm run dev:full

# Build for production
npm run build
npm start
```

## Pricing

| Plan | Price | Features |
|------|-------|----------|
| Free | $0/mo | 5 price comparisons/month |
| Pro | $99/mo | 500 claims/month, appeal generator, dashboard |
| Enterprise | $299/mo | Unlimited, API access, multi-pharmacy |

## License

Proprietary. © 2026 GetPaidRx.
