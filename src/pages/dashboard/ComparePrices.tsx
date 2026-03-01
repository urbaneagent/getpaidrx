import React, { useState, useCallback } from 'react';
import {
  Search,
  MapPin,
  DollarSign,
  Award,
  Camera,
  Loader2,
  ArrowDown,
  Tag,
  Pill,
  Building2,
} from 'lucide-react';

interface PharmacyPrice {
  pharmacy: string;
  price: number;
  priceType: 'cash' | 'coupon' | 'insurance';
  couponCode?: string;
  couponSource?: string;
  distance?: string;
  isBest?: boolean;
}

interface ComparisonResult {
  drugName: string;
  strength: string;
  quantity: number;
  prices: PharmacyPrice[];
  savings: number;
}

// Simulated price comparison (would hit real API in production)
function generatePrices(drugName: string, strength: string, quantity: number): PharmacyPrice[] {
  // Use drug name to seed deterministic but varied prices
  const seed = drugName.length + quantity;
  const basePrice = 15 + (seed % 40);
  
  const prices: PharmacyPrice[] = [
    {
      pharmacy: 'Walmart',
      price: +(basePrice * 0.75).toFixed(2),
      priceType: 'cash',
      distance: '2.1 mi',
    },
    {
      pharmacy: 'Costco',
      price: +(basePrice * 0.7).toFixed(2),
      priceType: 'cash',
      distance: '5.4 mi',
    },
    {
      pharmacy: 'CVS',
      price: +(basePrice * 1.1).toFixed(2),
      priceType: 'cash',
      distance: '0.8 mi',
    },
    {
      pharmacy: 'CVS (w/ Coupon)',
      price: +(basePrice * 0.65).toFixed(2),
      priceType: 'coupon',
      couponCode: `GRX${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
      couponSource: 'GoodRx',
      distance: '0.8 mi',
    },
    {
      pharmacy: 'Walgreens',
      price: +(basePrice * 1.05).toFixed(2),
      priceType: 'cash',
      distance: '1.2 mi',
    },
    {
      pharmacy: 'Walgreens (w/ Coupon)',
      price: +(basePrice * 0.68).toFixed(2),
      priceType: 'coupon',
      couponCode: `SC${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
      couponSource: 'SingleCare',
      distance: '1.2 mi',
    },
    {
      pharmacy: 'Kroger',
      price: +(basePrice * 0.85).toFixed(2),
      priceType: 'cash',
      distance: '3.0 mi',
    },
    {
      pharmacy: 'Insurance Copay',
      price: +(Math.max(10, basePrice * 0.4)).toFixed(2),
      priceType: 'insurance',
    },
  ];

  // Sort by price
  prices.sort((a, b) => a.price - b.price);
  prices[0].isBest = true;

  return prices;
}

export default function ComparePrices() {
  const [drugName, setDrugName] = useState('');
  const [strength, setStrength] = useState('');
  const [quantity, setQuantity] = useState(30);
  const [zipCode, setZipCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ComparisonResult | null>(null);

  const handleCompare = useCallback(async () => {
    if (!drugName.trim()) return;
    
    setLoading(true);
    // Simulate API call
    await new Promise(r => setTimeout(r, 800));
    
    const prices = generatePrices(drugName, strength, quantity);
    const savings = prices[prices.length - 1].price - prices[0].price;
    
    setResult({
      drugName,
      strength: strength || 'Standard',
      quantity,
      prices,
      savings,
    });
    setLoading(false);
  }, [drugName, strength, quantity]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleCompare();
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Compare Drug Prices</h1>
        <p className="text-gray-600 mt-1">
          Find the lowest price for any medication across local pharmacies, with coupons.
        </p>
      </div>

      {/* Search form */}
      <div className="card p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Drug Name</label>
            <div className="relative">
              <Pill className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={drugName}
                onChange={e => setDrugName(e.target.value)}
                onKeyDown={handleKeyDown}
                className="input-field pl-10"
                placeholder="e.g., Metformin, Lisinopril, Atorvastatin..."
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Strength</label>
            <input
              type="text"
              value={strength}
              onChange={e => setStrength(e.target.value)}
              onKeyDown={handleKeyDown}
              className="input-field"
              placeholder="e.g., 10mg, 20mg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Quantity</label>
            <input
              type="number"
              value={quantity}
              onChange={e => setQuantity(parseInt(e.target.value) || 30)}
              onKeyDown={handleKeyDown}
              className="input-field"
              min={1}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">ZIP Code</label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={zipCode}
                onChange={e => setZipCode(e.target.value)}
                onKeyDown={handleKeyDown}
                className="input-field pl-10"
                placeholder="e.g., 40502"
                maxLength={5}
              />
            </div>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleCompare}
              disabled={loading || !drugName.trim()}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  Compare Prices
                </>
              )}
            </button>
          </div>
        </div>

        {/* OCR upload hint */}
        <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
          <Camera className="w-5 h-5 text-gray-400" />
          <p className="text-xs text-gray-500">
            <span className="font-medium text-gray-600">Coming soon:</span> Upload a prescription photo
            for auto-fill via OCR.
          </p>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">
              Results for {result.drugName} {result.strength}
              <span className="text-gray-400 font-normal text-sm ml-2">(qty: {result.quantity})</span>
            </h2>
            <div className="flex items-center gap-2 text-sm font-medium text-green-600 bg-green-50 px-3 py-1.5 rounded-full">
              <DollarSign className="w-4 h-4" />
              Save up to ${result.savings.toFixed(2)}
            </div>
          </div>

          <div className="space-y-3">
            {result.prices.map((price, i) => (
              <div
                key={i}
                className={`card flex items-center gap-4 p-4 ${
                  price.isBest ? 'border-2 border-green-400 bg-green-50/50' : ''
                }`}
              >
                {/* Rank */}
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0
                  ${price.isBest ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-500'}
                `}>
                  {i + 1}
                </div>

                {/* Pharmacy info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-gray-900">{price.pharmacy}</p>
                    {price.isBest && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                        <Award className="w-3 h-3" />
                        Best Price
                      </span>
                    )}
                    {price.priceType === 'coupon' && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">
                        <Tag className="w-3 h-3" />
                        {price.couponSource}
                      </span>
                    )}
                    {price.priceType === 'insurance' && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                        Estimated Copay
                      </span>
                    )}
                  </div>
                  {price.distance && (
                    <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {price.distance}
                    </p>
                  )}
                  {price.couponCode && (
                    <p className="text-xs text-purple-600 mt-1 font-mono">
                      Code: {price.couponCode}
                    </p>
                  )}
                </div>

                {/* Price */}
                <div className="text-right flex-shrink-0">
                  <p className={`text-2xl font-bold ${price.isBest ? 'text-green-600' : 'text-gray-900'}`}>
                    ${price.price.toFixed(2)}
                  </p>
                  <p className="text-xs text-gray-500">{price.priceType}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Insurance note */}
          {result.prices.some(p => p.priceType === 'coupon' && p.price < (result.prices.find(x => x.priceType === 'insurance')?.price || Infinity)) && (
            <div className="card p-4 bg-yellow-50 border-yellow-200">
              <p className="text-sm text-yellow-800">
                <strong>💡 Tip:</strong> A coupon price is cheaper than the estimated insurance copay for this medication.
                You may save money by paying cash with a coupon instead of using insurance.
              </p>
            </div>
          )}

          <p className="text-xs text-gray-400 text-center">
            Prices are estimates and may vary. Always confirm with the pharmacy.
            Coupon codes are for illustration — real integrations coming in production.
          </p>
        </div>
      )}
    </div>
  );
}
