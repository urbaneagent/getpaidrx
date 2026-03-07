import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// ---- NADAC Database (Top 100 drugs) ----
const NADAC_DATABASE: Record<string, { drugName: string; nadacPerUnit: number; unitType: string; effectiveDate: string }> = {
  '00002-4462-30': { drugName: 'Metformin HCl 500mg', nadacPerUnit: 0.0231, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00002-4462-60': { drugName: 'Metformin HCl 500mg', nadacPerUnit: 0.0231, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00071-0155-23': { drugName: 'Lisinopril 10mg', nadacPerUnit: 0.0341, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00071-0155-40': { drugName: 'Lisinopril 10mg', nadacPerUnit: 0.0341, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-7180-01': { drugName: 'Amlodipine Besylate 5mg', nadacPerUnit: 0.0528, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-7180-10': { drugName: 'Amlodipine Besylate 5mg', nadacPerUnit: 0.0528, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00378-1800-01': { drugName: 'Atorvastatin Calcium 20mg', nadacPerUnit: 0.0412, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00378-1800-10': { drugName: 'Atorvastatin Calcium 20mg', nadacPerUnit: 0.0412, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00781-1506-01': { drugName: 'Omeprazole 20mg', nadacPerUnit: 0.0189, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00781-1506-10': { drugName: 'Omeprazole 20mg', nadacPerUnit: 0.0189, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '51991-0747-01': { drugName: 'Levothyroxine Sodium 50mcg', nadacPerUnit: 0.0287, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '51991-0747-10': { drugName: 'Levothyroxine Sodium 50mcg', nadacPerUnit: 0.0287, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00228-2057-10': { drugName: 'Hydrochlorothiazide 25mg', nadacPerUnit: 0.0156, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00591-0405-01': { drugName: 'Gabapentin 300mg', nadacPerUnit: 0.0812, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00591-0405-10': { drugName: 'Gabapentin 300mg', nadacPerUnit: 0.0812, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '65862-0157-01': { drugName: 'Sertraline HCl 50mg', nadacPerUnit: 0.0673, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '65862-0157-10': { drugName: 'Sertraline HCl 50mg', nadacPerUnit: 0.0673, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00378-3512-01': { drugName: 'Losartan Potassium 50mg', nadacPerUnit: 0.0945, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00378-3512-10': { drugName: 'Losartan Potassium 50mg', nadacPerUnit: 0.0945, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '16714-0296-01': { drugName: 'Metoprolol Succinate ER 25mg', nadacPerUnit: 0.0312, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-0058-01': { drugName: 'Simvastatin 20mg', nadacPerUnit: 0.0489, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '68382-0052-10': { drugName: 'Montelukast Sodium 10mg', nadacPerUnit: 0.1234, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '65862-0676-01': { drugName: 'Escitalopram Oxalate 10mg', nadacPerUnit: 0.0567, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00781-2061-01': { drugName: 'Pantoprazole Sodium 40mg', nadacPerUnit: 0.0423, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '42571-0312-10': { drugName: 'Clopidogrel Bisulfate 75mg', nadacPerUnit: 0.0198, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-5264-01': { drugName: 'Duloxetine HCl 30mg', nadacPerUnit: 0.0756, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '68180-0757-01': { drugName: 'Rosuvastatin Calcium 10mg', nadacPerUnit: 0.0345, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00378-6150-01': { drugName: 'Tamsulosin HCl 0.4mg', nadacPerUnit: 0.0234, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00591-3533-01': { drugName: 'Meloxicam 15mg', nadacPerUnit: 0.0678, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-2263-01': { drugName: 'Pregabalin 75mg', nadacPerUnit: 0.1045, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00378-6085-01': { drugName: 'Bupropion HCl XL 150mg', nadacPerUnit: 0.0189, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-5109-01': { drugName: 'Trazodone HCl 50mg', nadacPerUnit: 0.0567, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '16714-0402-01': { drugName: 'Venlafaxine HCl ER 75mg', nadacPerUnit: 0.0823, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00228-2874-11': { drugName: 'Furosemide 20mg', nadacPerUnit: 0.0234, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00781-1764-01': { drugName: 'Doxycycline Hyclate 100mg', nadacPerUnit: 0.0412, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00555-0972-02': { drugName: 'Prednisone 10mg', nadacPerUnit: 0.0156, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00093-3147-01': { drugName: 'Amoxicillin 500mg', nadacPerUnit: 0.0534, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '68382-0013-01': { drugName: 'Cyclobenzaprine HCl 10mg', nadacPerUnit: 0.0789, unitType: 'TAB', effectiveDate: '2026-01-15' },
  '00781-1965-01': { drugName: 'Cephalexin 500mg', nadacPerUnit: 0.0345, unitType: 'CAP', effectiveDate: '2026-01-15' },
  '00591-0389-01': { drugName: 'Tramadol HCl 50mg', nadacPerUnit: 0.0912, unitType: 'TAB', effectiveDate: '2026-01-15' },
};

// ---- API Routes ----

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', version: '0.1.0', timestamp: new Date().toISOString() });
});

// Get NADAC data (all or by NDC)
app.get('/api/nadac', (req, res) => {
  const { ndc } = req.query;
  
  if (ndc && typeof ndc === 'string') {
    const drug = NADAC_DATABASE[ndc];
    if (drug) {
      res.json({ ndc, ...drug });
    } else {
      res.status(404).json({ error: `No NADAC data for NDC ${ndc}` });
    }
    return;
  }

  // Return all
  const drugs = Object.entries(NADAC_DATABASE).map(([ndc, data]) => ({
    ndc,
    ...data,
  }));
  res.json({ count: drugs.length, drugs });
});

// Analyze claims
app.post('/api/analyze', (req, res) => {
  const { claims } = req.body;
  
  if (!claims || !Array.isArray(claims)) {
    res.status(400).json({ error: 'Request body must include a "claims" array' });
    return;
  }

  const analyzed = claims.map((claim: any) => {
    const nadacData = NADAC_DATABASE[claim.ndc];
    if (!nadacData) {
      return { ...claim, isUnderpaid: false, underpaymentAmount: 0, nadacFound: false };
    }

    const expectedReimbursement = nadacData.nadacPerUnit * (claim.quantity || 1);
    const isUnderpaid = claim.reimbursement < expectedReimbursement * 0.9;
    const underpaymentAmount = isUnderpaid
      ? +(expectedReimbursement - claim.reimbursement).toFixed(2)
      : 0;

    return {
      ...claim,
      nadacPerUnit: nadacData.nadacPerUnit,
      nadacDrugName: nadacData.drugName,
      expectedReimbursement: +expectedReimbursement.toFixed(2),
      isUnderpaid,
      underpaymentAmount,
      nadacFound: true,
    };
  });

  const underpaid = analyzed.filter((c: any) => c.isUnderpaid);
  const totalUnderpayment = underpaid.reduce((sum: number, c: any) => sum + c.underpaymentAmount, 0);

  res.json({
    totalClaims: analyzed.length,
    underpaidCount: underpaid.length,
    totalUnderpayment: +totalUnderpayment.toFixed(2),
    claims: analyzed,
  });
});

// ---- Live NADAC Search (CMS data.medicaid.gov API) ----
// Dataset IDs for CMS NADAC data
const NADAC_DATASET_IDS: Record<string, string> = {
  '2026': 'fbb83258-11c7-47f5-8b18-5f8e79f7e704',
  '2025': 'f38d0706-1239-442c-a3cc-40ef1b686ac0',
};

// Search NADAC by drug name or NDC via CMS live API
app.get('/api/nadac/search', async (req, res) => {
  const { q, ndc, year = '2026', limit = '20' } = req.query;

  if (!q && !ndc) {
    res.status(400).json({ error: 'Provide either q (drug name search) or ndc (NDC lookup)' });
    return;
  }

  const datasetId = NADAC_DATASET_IDS[year as string] || NADAC_DATASET_IDS['2026'];
  const apiUrl = `https://data.medicaid.gov/api/1/datastore/query/${datasetId}/0`;
  const queryLimit = Math.min(parseInt(limit as string) || 20, 100);

  try {
    const params: Record<string, string> = {
      limit: String(queryLimit),
      'sort[0][property]': 'ndc_description',
      'sort[0][order]': 'asc',
    };

    if (ndc && typeof ndc === 'string') {
      // Exact NDC lookup (strip dashes for comparison)
      const cleanNdc = ndc.replace(/-/g, '');
      params['conditions[0][property]'] = 'ndc';
      params['conditions[0][value]'] = cleanNdc;
      params['conditions[0][operator]'] = '=';
    } else if (q && typeof q === 'string') {
      // Drug name search (LIKE with wildcards)
      params['conditions[0][property]'] = 'ndc_description';
      params['conditions[0][value]'] = `%${q.toUpperCase()}%`;
      params['conditions[0][operator]'] = 'LIKE';
    }

    const urlParams = new URLSearchParams(params);
    const response = await fetch(`${apiUrl}?${urlParams}`);

    if (!response.ok) {
      throw new Error(`CMS API returned ${response.status}`);
    }

    const data = await response.json() as {
      results: Array<{
        ndc_description: string;
        ndc: string;
        nadac_per_unit: string;
        effective_date: string;
        pricing_unit: string;
        pharmacy_type_indicator: string;
        otc: string;
        classification_for_rate_setting: string;
        as_of_date: string;
      }>;
      count: number;
    };

    const drugs = data.results.map((r) => ({
      ndc: r.ndc,
      ndcFormatted: r.ndc.length === 11
        ? `${r.ndc.slice(0, 5)}-${r.ndc.slice(5, 9)}-${r.ndc.slice(9)}`
        : r.ndc,
      drugName: r.ndc_description,
      nadacPerUnit: parseFloat(r.nadac_per_unit),
      effectiveDate: r.effective_date,
      pricingUnit: r.pricing_unit,
      pharmacyType: r.pharmacy_type_indicator,
      otc: r.otc === 'Y',
      classification: r.classification_for_rate_setting === 'G' ? 'Generic' : 'Brand',
      asOfDate: r.as_of_date,
    }));

    res.json({
      query: q || ndc,
      year,
      count: drugs.length,
      totalMatches: data.count,
      source: 'CMS data.medicaid.gov (live)',
      drugs,
    });
  } catch (err: any) {
    console.error('NADAC API error:', err.message);

    // Fallback to local database for drug name search
    if (q && typeof q === 'string') {
      const searchTerm = q.toLowerCase();
      const localMatches = Object.entries(NADAC_DATABASE)
        .filter(([_, data]) => data.drugName.toLowerCase().includes(searchTerm))
        .map(([ndc, data]) => ({ ndc, ...data }));

      res.json({
        query: q,
        year,
        count: localMatches.length,
        totalMatches: localMatches.length,
        source: 'local (CMS API unavailable)',
        drugs: localMatches,
      });
    } else {
      res.status(502).json({
        error: 'CMS NADAC API unavailable',
        details: err.message,
      });
    }
  }
});

// NADAC rate check — compare a reimbursement against live CMS NADAC rate
app.post('/api/nadac/check', async (req, res) => {
  const { ndc, quantity, reimbursement } = req.body;

  if (!ndc || !quantity || reimbursement === undefined) {
    res.status(400).json({ error: 'Required: ndc, quantity, reimbursement' });
    return;
  }

  const cleanNdc = ndc.replace(/-/g, '');
  const datasetId = NADAC_DATASET_IDS['2026'];
  const apiUrl = `https://data.medicaid.gov/api/1/datastore/query/${datasetId}/0`;

  try {
    const params = new URLSearchParams({
      limit: '1',
      'conditions[0][property]': 'ndc',
      'conditions[0][value]': cleanNdc,
      'conditions[0][operator]': '=',
      'sort[0][property]': 'effective_date',
      'sort[0][order]': 'desc',
    });

    const response = await fetch(`${apiUrl}?${params}`);
    if (!response.ok) throw new Error(`CMS API returned ${response.status}`);

    const data = await response.json() as {
      results: Array<{
        ndc_description: string;
        ndc: string;
        nadac_per_unit: string;
        effective_date: string;
        pricing_unit: string;
      }>;
    };

    if (data.results.length === 0) {
      // Fallback to local
      const localDrug = NADAC_DATABASE[ndc];
      if (!localDrug) {
        res.status(404).json({ error: `No NADAC data found for NDC ${ndc}` });
        return;
      }
      const expected = localDrug.nadacPerUnit * quantity;
      const diff = reimbursement - expected;
      res.json({
        ndc,
        drugName: localDrug.drugName,
        nadacPerUnit: localDrug.nadacPerUnit,
        quantity,
        expectedReimbursement: +expected.toFixed(2),
        actualReimbursement: reimbursement,
        difference: +diff.toFixed(2),
        isUnderpaid: diff < -expected * 0.1,
        underpaymentPercent: expected > 0 ? +((diff / expected) * 100).toFixed(1) : 0,
        source: 'local',
      });
      return;
    }

    const drug = data.results[0];
    const nadacRate = parseFloat(drug.nadac_per_unit);
    const expected = nadacRate * quantity;
    const diff = reimbursement - expected;

    res.json({
      ndc: drug.ndc,
      drugName: drug.ndc_description,
      nadacPerUnit: nadacRate,
      effectiveDate: drug.effective_date,
      pricingUnit: drug.pricing_unit,
      quantity,
      expectedReimbursement: +expected.toFixed(2),
      actualReimbursement: reimbursement,
      difference: +diff.toFixed(2),
      isUnderpaid: diff < -expected * 0.1,
      underpaymentPercent: expected > 0 ? +((diff / expected) * 100).toFixed(1) : 0,
      source: 'CMS data.medicaid.gov (live)',
    });
  } catch (err: any) {
    console.error('NADAC check error:', err.message);
    res.status(502).json({ error: 'CMS NADAC API unavailable', details: err.message });
  }
});

// ---- Appeal Letter Generator ----
app.post('/api/appeal', (req, res) => {
  const { claim, pharmacyInfo } = req.body;

  if (!claim || !claim.ndc || !claim.reimbursement) {
    res.status(400).json({ error: 'Required: claim object with ndc, reimbursement, and quantity' });
    return;
  }

  const pharmacy = pharmacyInfo || {
    name: '[Pharmacy Name]',
    npi: '[NPI Number]',
    address: '[Address]',
    phone: '[Phone]',
    contact: '[Pharmacist Name]',
  };

  const nadacData = NADAC_DATABASE[claim.ndc];
  const drugName = claim.drugName || nadacData?.drugName || '[Drug Name]';
  const nadacRate = claim.nadacPerUnit || nadacData?.nadacPerUnit || 0;
  const quantity = claim.quantity || 1;
  const expectedReimbursement = nadacRate * quantity;
  const underpayment = expectedReimbursement - claim.reimbursement;
  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  const letter = `${today}

${pharmacy.name}
${pharmacy.address}
NPI: ${pharmacy.npi}
Phone: ${pharmacy.phone}

To: ${claim.payerName || '[PBM/Payer Name]'}
    Claims Department

RE: Formal Appeal – Underpayment on Prescription Claim
    Rx Number: ${claim.rxNumber || '[Rx Number]'}
    Patient: ${claim.patientName || '[Patient Name]'}
    Date of Service: ${claim.dateOfService || '[Date of Service]'}
    NDC: ${claim.ndc}
    Drug: ${drugName}

Dear Claims Review Department,

We are writing to formally appeal the underpayment of the above-referenced claim for the following prescription:

  Drug: ${drugName}
  NDC: ${claim.ndc}
  Quantity Dispensed: ${quantity}
  Days Supply: ${claim.daysSupply || 30}

REIMBURSEMENT ANALYSIS:
  NADAC Per Unit: $${nadacRate.toFixed(4)}
  Expected Reimbursement (${quantity} units × $${nadacRate.toFixed(4)}): $${expectedReimbursement.toFixed(2)}
  Actual Reimbursement Received: $${claim.reimbursement.toFixed(2)}
  Underpayment Amount: $${underpayment.toFixed(2)}

The National Average Drug Acquisition Cost (NADAC), as published by the Centers for Medicare & Medicaid Services (CMS), represents the benchmark acquisition cost for this medication. The reimbursement received for this claim falls ${((underpayment / expectedReimbursement) * 100).toFixed(1)}% below the NADAC rate, which does not adequately cover the cost of acquiring and dispensing this medication.

Per the Consolidated Appropriations Act of 2026, PBMs are required to provide transparency in reimbursement calculations. The underpayment identified in this claim falls below the CMS NADAC benchmark, which serves as the recognized industry standard for drug acquisition costs.

We respectfully request:
1. Immediate review and adjustment of this claim to reflect the current NADAC rate
2. Retroactive reimbursement of the underpayment amount ($${underpayment.toFixed(2)})
3. Written explanation of the reimbursement methodology used for this claim

Please respond within 30 days of receipt of this appeal. If you have any questions, please contact ${pharmacy.contact || '[Pharmacist Name]'} at ${pharmacy.phone}.

Sincerely,

${pharmacy.contact || '[Pharmacist Name]'}, PharmD
${pharmacy.name}

Enclosures:
- NADAC Reference Data (CMS data.medicaid.gov)
- Original Claim Submission
- Remittance Advice`;

  res.json({
    letter,
    summary: {
      drug: drugName,
      ndc: claim.ndc,
      underpaymentAmount: +underpayment.toFixed(2),
      nadacRate,
      actualReimbursement: claim.reimbursement,
      expectedReimbursement: +expectedReimbursement.toFixed(2),
    },
    generatedAt: new Date().toISOString(),
  });
});

// Price comparison (demo endpoint)
app.post('/api/compare', (req, res) => {
  const { drugName, strength, quantity = 30, zipCode } = req.body;

  if (!drugName) {
    res.status(400).json({ error: 'drugName is required' });
    return;
  }

  const seed = drugName.length + quantity;
  const basePrice = 15 + (seed % 40);

  const prices = [
    { pharmacy: 'Walmart', price: +(basePrice * 0.75).toFixed(2), priceType: 'cash', distance: '2.1 mi' },
    { pharmacy: 'Costco', price: +(basePrice * 0.7).toFixed(2), priceType: 'cash', distance: '5.4 mi' },
    { pharmacy: 'CVS', price: +(basePrice * 1.1).toFixed(2), priceType: 'cash', distance: '0.8 mi' },
    { pharmacy: 'CVS (w/ GoodRx)', price: +(basePrice * 0.65).toFixed(2), priceType: 'coupon', couponSource: 'GoodRx', distance: '0.8 mi' },
    { pharmacy: 'Walgreens', price: +(basePrice * 1.05).toFixed(2), priceType: 'cash', distance: '1.2 mi' },
    { pharmacy: 'Walgreens (w/ SingleCare)', price: +(basePrice * 0.68).toFixed(2), priceType: 'coupon', couponSource: 'SingleCare', distance: '1.2 mi' },
    { pharmacy: 'Kroger', price: +(basePrice * 0.85).toFixed(2), priceType: 'cash', distance: '3.0 mi' },
    { pharmacy: 'Insurance Copay', price: +(Math.max(10, basePrice * 0.4)).toFixed(2), priceType: 'insurance' },
  ].sort((a, b) => a.price - b.price);

  res.json({
    drug: { name: drugName, strength, quantity },
    zipCode,
    prices,
    lowestPrice: prices[0],
    highestPrice: prices[prices.length - 1],
    potentialSavings: +(prices[prices.length - 1].price - prices[0].price).toFixed(2),
  });
});

// Serve static files in production
if (process.env.NODE_ENV === 'production') {
  // In production, dist-server/index.js serves dist/ (sibling directory)
  const distPath = path.join(__dirname, '../dist');
  app.use(express.static(distPath));
  app.get('*', (_req, res) => {
    res.sendFile(path.join(distPath, 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`🚀 GetPaidRx API running on port ${PORT}`);
  console.log(`📊 NADAC database loaded: ${Object.keys(NADAC_DATABASE).length} drug entries`);
});

export default app;
