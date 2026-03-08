import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import app from '../index.js';

describe('GetPaidRx API', () => {
  // ---- Health Endpoint ----
  describe('GET /api/health', () => {
    it('returns correct structure with status, version, and timestamp', async () => {
      const res = await request(app).get('/api/health');
      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('status', 'ok');
      expect(res.body).toHaveProperty('version', '0.1.0');
      expect(res.body).toHaveProperty('timestamp');
      expect(new Date(res.body.timestamp).getTime()).not.toBeNaN();
    });
  });

  // ---- NADAC Lookup ----
  describe('GET /api/nadac', () => {
    it('returns data for a known NDC (Metformin)', async () => {
      const res = await request(app).get('/api/nadac?ndc=00002-4462-30');
      expect(res.status).toBe(200);
      expect(res.body.ndc).toBe('00002-4462-30');
      expect(res.body.drugName).toBe('Metformin HCl 500mg');
      expect(res.body.nadacPerUnit).toBe(0.0231);
      expect(res.body.unitType).toBe('TAB');
      expect(res.body.effectiveDate).toBeDefined();
    });

    it('returns 404 for an unknown NDC', async () => {
      const res = await request(app).get('/api/nadac?ndc=99999-9999-99');
      expect(res.status).toBe(404);
      expect(res.body).toHaveProperty('error');
      expect(res.body.error).toContain('99999-9999-99');
    });

    it('returns all drugs when no NDC is specified', async () => {
      const res = await request(app).get('/api/nadac');
      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('count');
      expect(res.body).toHaveProperty('drugs');
      expect(res.body.count).toBeGreaterThan(0);
      expect(Array.isArray(res.body.drugs)).toBe(true);
    });
  });

  // ---- Analyze Endpoint ----
  describe('POST /api/analyze', () => {
    it('analyzes valid claims and detects underpayment', async () => {
      const res = await request(app)
        .post('/api/analyze')
        .send({
          claims: [
            {
              ndc: '00002-4462-30',
              quantity: 90,
              reimbursement: 0.50, // well below NADAC of 0.0231 * 90 = $2.079
            },
          ],
        });

      expect(res.status).toBe(200);
      expect(res.body.totalClaims).toBe(1);
      expect(res.body.underpaidCount).toBe(1);
      expect(res.body.totalUnderpayment).toBeGreaterThan(0);
      expect(res.body.claims[0].isUnderpaid).toBe(true);
      expect(res.body.claims[0].nadacFound).toBe(true);
      expect(res.body.claims[0].nadacDrugName).toBe('Metformin HCl 500mg');
    });

    it('returns 400 for invalid input (no claims array)', async () => {
      const res = await request(app)
        .post('/api/analyze')
        .send({ data: 'bad' });

      expect(res.status).toBe(400);
      expect(res.body).toHaveProperty('error');
    });

    it('returns 400 for claims that is not an array', async () => {
      const res = await request(app)
        .post('/api/analyze')
        .send({ claims: 'not-an-array' });

      expect(res.status).toBe(400);
      expect(res.body.error).toContain('claims');
    });

    it('handles claims with unknown NDC gracefully', async () => {
      const res = await request(app)
        .post('/api/analyze')
        .send({
          claims: [{ ndc: '99999-9999-99', quantity: 30, reimbursement: 10 }],
        });

      expect(res.status).toBe(200);
      expect(res.body.claims[0].nadacFound).toBe(false);
      expect(res.body.claims[0].isUnderpaid).toBe(false);
    });
  });

  // ---- Appeal Letter Generation ----
  describe('POST /api/appeal', () => {
    it('generates a complete appeal letter', async () => {
      const res = await request(app)
        .post('/api/appeal')
        .send({
          claim: {
            ndc: '00002-4462-30',
            reimbursement: 0.50,
            quantity: 90,
            payerName: 'Test PBM',
            rxNumber: 'RX123456',
            patientName: 'John Doe',
            dateOfService: '2026-01-15',
          },
          pharmacyInfo: {
            name: 'Test Pharmacy',
            npi: '1234567890',
            address: '123 Main St, Anytown, USA',
            phone: '555-123-4567',
            contact: 'Dr. Smith',
          },
        });

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('letter');
      expect(res.body).toHaveProperty('summary');
      expect(res.body).toHaveProperty('generatedAt');
      expect(res.body.letter).toContain('Test Pharmacy');
      expect(res.body.letter).toContain('Metformin HCl 500mg');
      expect(res.body.letter).toContain('RX123456');
      expect(res.body.letter).toContain('John Doe');
      expect(res.body.letter).toContain('Test PBM');
      expect(res.body.letter).toContain('NADAC Per Unit');
      expect(res.body.summary.ndc).toBe('00002-4462-30');
      expect(res.body.summary.underpaymentAmount).toBeGreaterThan(0);
    });

    it('returns 400 when claim is missing required fields', async () => {
      const res = await request(app)
        .post('/api/appeal')
        .send({ claim: {} });

      expect(res.status).toBe(400);
      expect(res.body).toHaveProperty('error');
    });

    it('returns 400 when no claim is provided', async () => {
      const res = await request(app)
        .post('/api/appeal')
        .send({});

      expect(res.status).toBe(400);
    });
  });

  // ---- Price Comparison ----
  describe('POST /api/compare', () => {
    it('returns price comparison data for a given drug', async () => {
      const res = await request(app)
        .post('/api/compare')
        .send({ drugName: 'Metformin', strength: '500mg', quantity: 30 });

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('drug');
      expect(res.body.drug.name).toBe('Metformin');
      expect(res.body).toHaveProperty('prices');
      expect(Array.isArray(res.body.prices)).toBe(true);
      expect(res.body.prices.length).toBeGreaterThan(0);
      expect(res.body).toHaveProperty('lowestPrice');
      expect(res.body).toHaveProperty('highestPrice');
      expect(res.body).toHaveProperty('potentialSavings');
      // Prices should be sorted ascending
      for (let i = 1; i < res.body.prices.length; i++) {
        expect(res.body.prices[i].price).toBeGreaterThanOrEqual(res.body.prices[i - 1].price);
      }
    });

    it('returns 400 when drugName is missing', async () => {
      const res = await request(app)
        .post('/api/compare')
        .send({});

      expect(res.status).toBe(400);
      expect(res.body).toHaveProperty('error');
    });
  });

  // ---- CSV Validation ----
  describe('POST /api/validate-csv', () => {
    it('validates a correct CSV', async () => {
      const csv = `ndc,quantity,reimbursement,drug_name
00002-4462-30,90,1.50,Metformin
00071-0155-23,30,0.80,Lisinopril`;

      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv });

      expect(res.status).toBe(200);
      expect(res.body.valid).toBe(true);
      expect(res.body.totalRows).toBe(2);
      expect(res.body.validRows).toBe(2);
      expect(res.body.errors).toHaveLength(0);
      expect(res.body.columnMapping.detected).toContain('ndc');
      expect(res.body.columnMapping.detected).toContain('quantity');
      expect(res.body.columnMapping.detected).toContain('reimbursement');
      expect(res.body.columnMapping.missing).toHaveLength(0);
    });

    it('detects missing required columns', async () => {
      const csv = `drug_name,quantity
Metformin,90`;

      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv });

      expect(res.status).toBe(200);
      expect(res.body.valid).toBe(false);
      expect(res.body.columnMapping.missing).toContain('ndc');
      expect(res.body.columnMapping.missing).toContain('reimbursement');
    });

    it('detects invalid NDC format', async () => {
      const csv = `ndc,quantity,reimbursement
ABC-1234-XX,90,1.50`;

      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv });

      expect(res.status).toBe(200);
      expect(res.body.valid).toBe(false);
      expect(res.body.errors.some((e: any) => e.field === 'ndc')).toBe(true);
    });

    it('detects invalid quantity (negative)', async () => {
      const csv = `ndc,quantity,reimbursement
00002-4462-30,-5,1.50`;

      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv });

      expect(res.status).toBe(200);
      expect(res.body.valid).toBe(false);
      expect(res.body.errors.some((e: any) => e.field === 'quantity')).toBe(true);
    });

    it('supports column name aliases', async () => {
      const csv = `ndc_code,qty,paid_amount,medication
00002-4462-30,90,1.50,Metformin`;

      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv });

      expect(res.status).toBe(200);
      expect(res.body.valid).toBe(true);
      expect(res.body.columnMapping.detected).toContain('ndc');
      expect(res.body.columnMapping.detected).toContain('quantity');
      expect(res.body.columnMapping.detected).toContain('reimbursement');
    });

    it('returns 400 when csv string is missing', async () => {
      const res = await request(app)
        .post('/api/validate-csv')
        .send({});

      expect(res.status).toBe(400);
    });

    it('handles CSV with only header row', async () => {
      const res = await request(app)
        .post('/api/validate-csv')
        .send({ csv: 'ndc,quantity,reimbursement' });

      expect(res.status).toBe(400);
      expect(res.body.valid).toBe(false);
    });
  });

  // ---- Metrics Endpoint ----
  describe('GET /api/metrics', () => {
    it('returns metrics with correct structure', async () => {
      const res = await request(app).get('/api/metrics');

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('summary');
      expect(res.body.summary).toHaveProperty('totalClaimsAnalyzed');
      expect(res.body.summary).toHaveProperty('totalUnderpaid');
      expect(res.body.summary).toHaveProperty('totalRecoveryAmount');
      expect(res.body.summary).toHaveProperty('averageUnderpayment');
      expect(res.body.summary).toHaveProperty('appealsGenerated');
      expect(res.body).toHaveProperty('topUnderpaidDrugs');
      expect(res.body).toHaveProperty('underpaymentByPayer');
      expect(res.body).toHaveProperty('nadacDatabaseSize');
      expect(res.body).toHaveProperty('lastUpdated');
      expect(res.body.nadacDatabaseSize).toBeGreaterThan(0);
    });

    it('reflects metrics after analyze call', async () => {
      // First get baseline metrics
      const before = await request(app).get('/api/metrics');
      const baselineClaims = before.body.summary.totalClaimsAnalyzed;

      // Analyze some claims
      await request(app)
        .post('/api/analyze')
        .send({
          claims: [
            { ndc: '00071-0155-23', quantity: 30, reimbursement: 0.10, payerName: 'TestPBM' },
            { ndc: '00093-7180-01', quantity: 60, reimbursement: 0.50, payerName: 'TestPBM' },
          ],
        });

      // Check updated metrics
      const after = await request(app).get('/api/metrics');
      expect(after.body.summary.totalClaimsAnalyzed).toBe(baselineClaims + 2);
      expect(after.body.summary.totalUnderpaid).toBeGreaterThan(before.body.summary.totalUnderpaid);
      expect(after.body.summary.totalRecoveryAmount).toBeGreaterThan(before.body.summary.totalRecoveryAmount);
    });

    it('tracks appeals generated', async () => {
      const before = await request(app).get('/api/metrics');

      await request(app)
        .post('/api/appeal')
        .send({
          claim: {
            ndc: '00002-4462-30',
            reimbursement: 0.50,
            quantity: 90,
          },
        });

      const after = await request(app).get('/api/metrics');
      expect(after.body.summary.appealsGenerated).toBe(before.body.summary.appealsGenerated + 1);
    });
  });

  // ---- Export ----
  describe('App export', () => {
    it('exports a default app that is defined', () => {
      expect(app).toBeDefined();
      expect(typeof app).toBe('function'); // Express apps are functions
    });
  });
});
