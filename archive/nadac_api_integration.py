"""
NADAC API Integration
Real-time NADAC pricing data fetching and caching with automatic updates
"""

import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import hashlib

class NADACAPIIntegration:
    """
    Integration with CMS NADAC API for real-time drug pricing
    https://data.medicaid.gov/Drug-Pricing-and-Payment/NADAC-National-Average-Drug-Acquisition-Cost-/a4y5-998d
    """
    
    BASE_URL = "https://data.medicaid.gov/resource/a4y5-998d.json"
    
    def __init__(self, cache_hours: int = 24):
        self.cache_hours = cache_hours
        self.price_cache = {}
        self.cache_timestamps = {}
        
    def fetch_drug_price(
        self,
        ndc: str,
        effective_date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Fetch NADAC price for a specific NDC
        
        Args:
            ndc: 11-digit NDC code
            effective_date: Optional date (YYYY-MM-DD) to get historical price
        
        Returns:
            {
                'ndc': str,
                'ndc_description': str,
                'nadac_per_unit': float,
                'effective_date': str,
                'pricing_unit': str,
                'pharmacy_type_indicator': str,
                'otc': bool,
                'explanation_code': str
            }
        """
        # Normalize NDC (remove hyphens)
        ndc_clean = ndc.replace('-', '').strip()
        
        # Check cache
        cache_key = f"{ndc_clean}_{effective_date or 'current'}"
        if self._is_cache_valid(cache_key):
            return self.price_cache[cache_key]
        
        # Build query
        params = {
            'ndc': ndc_clean,
            '$limit': 1,
            '$order': 'effective_date DESC'
        }
        
        if effective_date:
            params['effective_date'] = effective_date
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return None
            
            result = {
                'ndc': data[0].get('ndc'),
                'ndc_description': data[0].get('ndc_description'),
                'nadac_per_unit': float(data[0].get('nadac_per_unit', 0)),
                'effective_date': data[0].get('effective_date'),
                'pricing_unit': data[0].get('pricing_unit'),
                'pharmacy_type_indicator': data[0].get('pharmacy_type_indicator'),
                'otc': data[0].get('otc', 'N') == 'Y',
                'explanation_code': data[0].get('explanation_code', '')
            }
            
            # Cache the result
            self.price_cache[cache_key] = result
            self.cache_timestamps[cache_key] = datetime.utcnow()
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NADAC data: {e}")
            return None
    
    def fetch_bulk_prices(self, ndc_list: List[str]) -> Dict[str, Dict]:
        """
        Fetch NADAC prices for multiple NDCs in bulk
        
        Returns:
            {
                'ndc1': {...price data...},
                'ndc2': {...price data...},
                ...
            }
        """
        results = {}
        
        for ndc in ndc_list:
            price_data = self.fetch_drug_price(ndc)
            if price_data:
                results[ndc] = price_data
        
        return results
    
    def search_by_drug_name(self, drug_name: str, limit: int = 10) -> List[Dict]:
        """
        Search NADAC database by drug name
        
        Args:
            drug_name: Drug name to search for
            limit: Max number of results
        
        Returns:
            List of matching drugs with pricing info
        """
        params = {
            '$where': f"UPPER(ndc_description) LIKE UPPER('%{drug_name}%')",
            '$limit': limit,
            '$order': 'effective_date DESC'
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return [
                {
                    'ndc': item.get('ndc'),
                    'ndc_description': item.get('ndc_description'),
                    'nadac_per_unit': float(item.get('nadac_per_unit', 0)),
                    'effective_date': item.get('effective_date'),
                    'pricing_unit': item.get('pricing_unit')
                }
                for item in data
            ]
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching NADAC: {e}")
            return []
    
    def calculate_underpayment(
        self,
        ndc: str,
        amount_paid: float,
        quantity: int,
        dispensing_fee: float = 0.0
    ) -> Dict:
        """
        Calculate underpayment by comparing paid amount to NADAC
        
        Args:
            ndc: Drug NDC
            amount_paid: Total amount paid by payer
            quantity: Quantity dispensed
            dispensing_fee: Dispensing fee (if separate)
        
        Returns:
            {
                'is_underpaid': bool,
                'nadac_expected': float,
                'actual_paid': float,
                'underpayment_amount': float,
                'underpayment_percentage': float,
                'nadac_per_unit': float,
                'paid_per_unit': float
            }
        """
        nadac_data = self.fetch_drug_price(ndc)
        
        if not nadac_data:
            return {
                'is_underpaid': False,
                'error': 'NADAC price not found',
                'nadac_expected': 0,
                'actual_paid': amount_paid,
                'underpayment_amount': 0,
                'underpayment_percentage': 0
            }
        
        nadac_per_unit = nadac_data['nadac_per_unit']
        nadac_expected = (nadac_per_unit * quantity) + dispensing_fee
        
        paid_per_unit = (amount_paid - dispensing_fee) / quantity if quantity > 0 else 0
        underpayment = nadac_expected - amount_paid
        
        is_underpaid = underpayment > 0.01  # Allow 1 cent tolerance
        
        underpayment_pct = (underpayment / nadac_expected * 100) if nadac_expected > 0 else 0
        
        return {
            'is_underpaid': is_underpaid,
            'nadac_expected': round(nadac_expected, 2),
            'actual_paid': round(amount_paid, 2),
            'underpayment_amount': round(underpayment, 2) if is_underpaid else 0,
            'underpayment_percentage': round(underpayment_pct, 2),
            'nadac_per_unit': round(nadac_per_unit, 2),
            'paid_per_unit': round(paid_per_unit, 2),
            'quantity': quantity
        }
    
    def get_price_history(
        self,
        ndc: str,
        days_back: int = 90
    ) -> List[Dict]:
        """
        Get price history for an NDC over time
        
        Args:
            ndc: Drug NDC
            days_back: Number of days to look back
        
        Returns:
            List of historical prices sorted by date
        """
        ndc_clean = ndc.replace('-', '').strip()
        
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        params = {
            'ndc': ndc_clean,
            '$where': f"effective_date >= '{start_date}'",
            '$order': 'effective_date ASC',
            '$limit': 500
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return [
                {
                    'effective_date': item.get('effective_date'),
                    'nadac_per_unit': float(item.get('nadac_per_unit', 0)),
                    'explanation_code': item.get('explanation_code', '')
                }
                for item in data
            ]
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching price history: {e}")
            return []
    
    def detect_price_anomalies(
        self,
        ndc: str,
        days_back: int = 30
    ) -> Dict:
        """
        Detect unusual price changes or anomalies
        
        Returns:
            {
                'has_anomalies': bool,
                'price_changes': List[Dict],
                'volatility': float,
                'trend': str  # 'increasing', 'decreasing', 'stable'
            }
        """
        history = self.get_price_history(ndc, days_back)
        
        if len(history) < 2:
            return {
                'has_anomalies': False,
                'price_changes': [],
                'volatility': 0,
                'trend': 'stable',
                'message': 'Insufficient data for analysis'
            }
        
        # Calculate price changes
        price_changes = []
        for i in range(1, len(history)):
            prev = history[i-1]['nadac_per_unit']
            curr = history[i]['nadac_per_unit']
            
            if prev > 0:
                pct_change = ((curr - prev) / prev) * 100
                
                if abs(pct_change) > 10:  # >10% change is anomalous
                    price_changes.append({
                        'date': history[i]['effective_date'],
                        'old_price': prev,
                        'new_price': curr,
                        'change_pct': round(pct_change, 2)
                    })
        
        # Calculate volatility (standard deviation of prices)
        prices = [h['nadac_per_unit'] for h in history]
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        volatility = variance ** 0.5
        
        # Determine trend
        first_price = history[0]['nadac_per_unit']
        last_price = history[-1]['nadac_per_unit']
        
        if last_price > first_price * 1.05:
            trend = 'increasing'
        elif last_price < first_price * 0.95:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'has_anomalies': len(price_changes) > 0,
            'price_changes': price_changes,
            'volatility': round(volatility, 4),
            'trend': trend,
            'avg_price': round(avg_price, 2),
            'current_price': round(last_price, 2)
        }
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = datetime.utcnow() - self.cache_timestamps[cache_key]
        return age < timedelta(hours=self.cache_hours)
    
    def clear_cache(self):
        """Clear all cached pricing data"""
        self.price_cache.clear()
        self.cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cached_items': len(self.price_cache),
            'cache_size_kb': len(str(self.price_cache)) / 1024,
            'oldest_entry': min(self.cache_timestamps.values()) if self.cache_timestamps else None,
            'newest_entry': max(self.cache_timestamps.values()) if self.cache_timestamps else None
        }

