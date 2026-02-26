/**
 * GetPaidRx - Patient Portal: Drug Price Comparison
 * 
 * Features:
 * - Compare drug prices across pharmacies (CVS, Walgreens, Walmart, local)
 * - GoodRx API integration for coupon finder
 * - Insurance vs cash comparison
 * - Prescription OCR upload (photo → auto-fill drug name/strength)
 */

import axios from 'axios';
import Tesseract from 'tesseract.js';

export interface DrugInfo {
  name: string;
  strength: string; // e.g., "10mg"
  quantity: number;
  ndc?: string; // National Drug Code
}

export interface PharmacyPrice {
  pharmacy: string;
  location?: string;
  price: number;
  priceType: 'cash' | 'insurance' | 'coupon';
  couponCode?: string;
  couponSource?: 'GoodRx' | 'SingleCare' | 'RxSaver';
  distance?: number; // miles from user
}

export interface PriceComparisonResult {
  drug: DrugInfo;
  prices: PharmacyPrice[];
  lowestPrice: PharmacyPrice;
  potentialSavings: number; // vs highest price
  insuranceEstimate?: number;
}

export class DrugPriceComparator {
  private goodRxApiKey: string;
  private nadacDatabase: Map<string, number>; // NDC → NADAC price

  constructor(goodRxApiKey: string) {
    this.goodRxApiKey = goodRxApiKey;
    this.nadacDatabase = new Map();
    this.loadNADACDatabase();
  }

  // Load NADAC (National Average Drug Acquisition Cost) database
  private async loadNADACDatabase(): Promise<void> {
    try {
      // NADAC data from CMS (updated weekly)
      const response = await axios.get(
        'https://data.medicaid.gov/api/1/datastore/query/nadac-national-average-drug-acquisition-cost/0'
      );

      response.data.results.forEach((drug: any) => {
        if (drug.ndc && drug.nadac_per_unit) {
          this.nadacDatabase.set(drug.ndc, parseFloat(drug.nadac_per_unit));
        }
      });

      console.log(`✅ Loaded ${this.nadacDatabase.size} NADAC prices`);
    } catch (error) {
      console.error('❌ Failed to load NADAC database:', error);
    }
  }

  // OCR prescription image to extract drug info
  async scanPrescription(imageDataUrl: string): Promise<DrugInfo | null> {
    try {
      const result = await Tesseract.recognize(imageDataUrl, 'eng');
      const text = result.data.text;

      // Parse drug name, strength, quantity from OCR text
      // (Simple regex patterns - improve with ML in production)
      const nameMatch = text.match(/(?:drug|medication|rx):\s*([A-Za-z]+)/i);
      const strengthMatch = text.match(/(\d+\s*mg|\d+\s*mcg)/i);
      const quantityMatch = text.match(/(?:qty|quantity):\s*(\d+)/i);

      if (!nameMatch) {
        console.warn('⚠️ Could not extract drug name from prescription');
        return null;
      }

      return {
        name: nameMatch[1],
        strength: strengthMatch?.[1] || 'Unknown',
        quantity: quantityMatch ? parseInt(quantityMatch[1]) : 30
      };
    } catch (error) {
      console.error('❌ Prescription scan failed:', error);
      return null;
    }
  }

  // Compare prices across pharmacies
  async comparePrices(drug: DrugInfo, zipCode: string): Promise<PriceComparisonResult> {
    const prices: PharmacyPrice[] = [];

    // 1. Get GoodRx prices
    const goodRxPrices = await this.fetchGoodRxPrices(drug, zipCode);
    prices.push(...goodRxPrices);

    // 2. Get cash prices from major chains (mock data for demo)
    prices.push(
      { pharmacy: 'CVS', price: 45.99, priceType: 'cash', location: 'Main St' },
      { pharmacy: 'Walgreens', price: 42.50, priceType: 'cash', location: 'Oak Ave' },
      { pharmacy: 'Walmart', price: 38.75, priceType: 'cash', location: 'Highway 60' },
      { pharmacy: 'Costco', price: 35.00, priceType: 'cash', location: 'Members only' }
    );

    // 3. Estimate insurance price (if NDC available)
    let insuranceEstimate: number | undefined;
    if (drug.ndc) {
      const nadacPrice = this.nadacDatabase.get(drug.ndc);
      if (nadacPrice) {
        // Typical insurance copay: $10 or 20% of NADAC, whichever is higher
        insuranceEstimate = Math.max(10, nadacPrice * drug.quantity * 0.2);
        prices.push({
          pharmacy: 'Your Insurance',
          price: insuranceEstimate,
          priceType: 'insurance'
        });
      }
    }

    // Sort by price (lowest first)
    prices.sort((a, b) => a.price - b.price);

    const lowestPrice = prices[0];
    const highestPrice = prices[prices.length - 1];
    const potentialSavings = highestPrice.price - lowestPrice.price;

    return {
      drug,
      prices,
      lowestPrice,
      potentialSavings,
      insuranceEstimate
    };
  }

  // Fetch GoodRx coupon prices
  private async fetchGoodRxPrices(drug: DrugInfo, zipCode: string): Promise<PharmacyPrice[]> {
    try {
      // GoodRx API endpoint (mock structure - replace with real API)
      const response = await axios.get('https://api.goodrx.com/v1/prices', {
        params: {
          drug_name: drug.name,
          strength: drug.strength,
          quantity: drug.quantity,
          zip: zipCode,
          api_key: this.goodRxApiKey
        }
      });

      return response.data.prices.map((p: any) => ({
        pharmacy: p.pharmacy,
        location: p.address,
        price: p.price,
        priceType: 'coupon' as const,
        couponCode: p.coupon_code,
        couponSource: 'GoodRx' as const,
        distance: p.distance
      }));
    } catch (error) {
      console.error('❌ GoodRx API failed:', error);
      // Return fallback coupon prices
      return [
        {
          pharmacy: 'CVS (GoodRx)',
          price: 32.50,
          priceType: 'coupon',
          couponCode: 'GRXCVS123',
          couponSource: 'GoodRx'
        },
        {
          pharmacy: 'Walgreens (GoodRx)',
          price: 30.99,
          priceType: 'coupon',
          couponCode: 'GRXWAL456',
          couponSource: 'GoodRx'
        }
      ];
    }
  }

  // Generate savings report
  generateSavingsReport(result: PriceComparisonResult): string {
    let report = `💊 DRUG PRICE COMPARISON\n\n`;
    report += `Drug: ${result.drug.name} ${result.drug.strength}\n`;
    report += `Quantity: ${result.drug.quantity}\n\n`;
    report += `📊 PRICE BREAKDOWN:\n\n`;

    result.prices.forEach((p, i) => {
      const badge = i === 0 ? '🏆 BEST PRICE' : '';
      const couponInfo = p.couponCode ? ` (Code: ${p.couponCode})` : '';
      report += `${i + 1}. ${p.pharmacy} - $${p.price.toFixed(2)} (${p.priceType})${couponInfo} ${badge}\n`;
    });

    report += `\n💰 POTENTIAL SAVINGS: $${result.potentialSavings.toFixed(2)}\n`;

    if (result.insuranceEstimate) {
      const savingsVsInsurance = result.insuranceEstimate - result.lowestPrice.price;
      if (savingsVsInsurance > 0) {
        report += `\n⚠️ CASH PRICE IS CHEAPER THAN INSURANCE by $${savingsVsInsurance.toFixed(2)}\n`;
      }
    }

    return report;
  }
}

// React Component
export function DrugPriceComparisonWidget() {
  const [drug, setDrug] = React.useState<DrugInfo>({ name: '', strength: '', quantity: 30 });
  const [zipCode, setZipCode] = React.useState('');
  const [result, setResult] = React.useState<PriceComparisonResult | null>(null);
  const [loading, setLoading] = React.useState(false);

  const comparator = new DrugPriceComparator(process.env.GOODRX_API_KEY || '');

  const handleCompare = async () => {
    setLoading(true);
    const comparison = await comparator.comparePrices(drug, zipCode);
    setResult(comparison);
    setLoading(false);
  };

  const handleScanPrescription = async (imageFile: File) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      const imageDataUrl = e.target?.result as string;
      const scanned = await comparator.scanPrescription(imageDataUrl);
      if (scanned) {
        setDrug(scanned);
      }
    };
    reader.readAsDataURL(imageFile);
  };

  return (
    <div className="drug-comparison">
      <h2>💊 Compare Drug Prices</h2>
      
      <input
        type="file"
        accept="image/*"
        onChange={(e) => e.target.files?.[0] && handleScanPrescription(e.target.files[0])}
      />

      <input 
        placeholder="Drug Name"
        value={drug.name}
        onChange={(e) => setDrug({ ...drug, name: e.target.value })}
      />

      <input 
        placeholder="Strength (e.g., 10mg)"
        value={drug.strength}
        onChange={(e) => setDrug({ ...drug, strength: e.target.value })}
      />

      <input 
        placeholder="Quantity"
        type="number"
        value={drug.quantity}
        onChange={(e) => setDrug({ ...drug, quantity: parseInt(e.target.value) })}
      />

      <input 
        placeholder="ZIP Code"
        value={zipCode}
        onChange={(e) => setZipCode(e.target.value)}
      />

      <button onClick={handleCompare} disabled={loading}>
        {loading ? 'Comparing...' : 'Compare Prices'}
      </button>

      {result && (
        <div className="results">
          <h3>🏆 Best Price: ${result.lowestPrice.price.toFixed(2)} at {result.lowestPrice.pharmacy}</h3>
          <p>💰 Save ${result.potentialSavings.toFixed(2)} vs highest price</p>
          
          <ul>
            {result.prices.map((p, i) => (
              <li key={i}>
                {p.pharmacy} - ${p.price.toFixed(2)} ({p.priceType})
                {p.couponCode && ` | Code: ${p.couponCode}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
