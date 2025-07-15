# app/data_cache_reader.py
"""
Helper module to read cached data from the data pipeline.
This can be used by your Flask app to quickly access pre-fetched data.
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DataCacheReader:
    """Helper class to read cached market data."""
    
    def __init__(self, cache_dir=None):
        """
        Initialize the data cache reader.
        
        Args:
            cache_dir (str, optional): Path to cache directory. 
                                     Defaults to 'data_cache' in project root.
        """
        if cache_dir is None:
            # Default to data_cache in the project root
            project_root = Path(__file__).parent.parent
            cache_dir = project_root / 'data_cache'
        
        self.cache_dir = Path(cache_dir)
        
        if not self.cache_dir.exists():
            logger.warning(f"Cache directory does not exist: {self.cache_dir}")
    
    def get_cached_data(self, symbol, timeframe='1h'):
        """
        Get cached data for a specific symbol and timeframe.
        
        Args:
            symbol (str): Asset symbol (e.g., 'AAPL', 'EURUSD=X')
            timeframe (str): Timeframe ('1h', '4h', '1d')
        
        Returns:
            pd.DataFrame or None: Cached data if available, None otherwise
        """
        try:
            # Sanitize symbol for filename
            safe_symbol = symbol.replace('=', '_').replace('^', '_')
            cache_file = self.cache_dir / timeframe / f"{safe_symbol}.csv"
            
            if not cache_file.exists():
                logger.warning(f"Cache file not found: {cache_file}")
                return None
            
            # Read cached data
            data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            
            # Check if data is recent enough (within last 2 hours for fresh data)
            if not data.empty:
                last_update = data.index[-1]
                if isinstance(last_update, str):
                    last_update = pd.to_datetime(last_update)
                
                # Check if data is stale (older than 2 hours)
                if datetime.now() - last_update.replace(tzinfo=None) > timedelta(hours=2):
                    logger.info(f"Cached data for {symbol} is stale (last update: {last_update})")
            
            logger.info(f"✅ Loaded cached data for {symbol} ({timeframe}): {len(data)} rows")
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to load cached data for {symbol} ({timeframe}): {e}")
            return None
    
    def is_cache_available(self, symbol, timeframe='1h'):
        """
        Check if cached data is available for a symbol and timeframe.
        
        Args:
            symbol (str): Asset symbol
            timeframe (str): Timeframe
        
        Returns:
            bool: True if cache is available, False otherwise
        """
        safe_symbol = symbol.replace('=', '_').replace('^', '_')
        cache_file = self.cache_dir / timeframe / f"{safe_symbol}.csv"
        return cache_file.exists()
    
    def get_cache_info(self):
        """
        Get information about the cache status.
        
        Returns:
            dict: Cache statistics
        """
        info = {
            'cache_dir': str(self.cache_dir),
            'timeframes': {},
            'total_files': 0,
            'last_updated': None
        }
        
        if not self.cache_dir.exists():
            return info
        
        # Check each timeframe directory
        for timeframe in ['1h', '4h', '1d']:
            timeframe_dir = self.cache_dir / timeframe
            if timeframe_dir.exists():
                csv_files = list(timeframe_dir.glob('*.csv'))
                info['timeframes'][timeframe] = len(csv_files)
                info['total_files'] += len(csv_files)
        
        # Check for summary file to get last update time
        summary_file = self.cache_dir / 'pipeline_summary.txt'
        if summary_file.exists():
            try:
                with open(summary_file, 'r') as f:
                    for line in f:
                        if line.startswith('Execution Time:'):
                            info['last_updated'] = line.split(':', 1)[1].strip()
                            break
            except Exception as e:
                logger.error(f"Failed to read summary file: {e}")
        
        return info
    
    def get_available_symbols(self, timeframe='1h'):
        """
        Get list of available symbols in cache for a timeframe.
        
        Args:
            timeframe (str): Timeframe to check
        
        Returns:
            list: List of available symbols
        """
        timeframe_dir = self.cache_dir / timeframe
        if not timeframe_dir.exists():
            return []
        
        symbols = []
        for csv_file in timeframe_dir.glob('*.csv'):
            # Convert filename back to symbol
            symbol = csv_file.stem.replace('_', '=')
            # Handle special cases
            if symbol.startswith('_'):
                symbol = '^' + symbol[1:]
            symbols.append(symbol)
        
        return sorted(symbols)

# Convenience functions for easy import
def get_cached_data(symbol, timeframe='1h'):
    """Convenience function to get cached data."""
    reader = DataCacheReader()
    return reader.get_cached_data(symbol, timeframe)

def is_cache_available(symbol, timeframe='1h'):
    """Convenience function to check cache availability."""
    reader = DataCacheReader()
    return reader.is_cache_available(symbol, timeframe)

def get_cache_info():
    """Convenience function to get cache information."""
    reader = DataCacheReader()
    return reader.get_cache_info()

# Example usage in your Flask routes:
"""
# In your routes.py, you can now use:
from .data_cache_reader import get_cached_data, is_cache_available

@app.route('/api/generate_signal')
def generate_signal_route():
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', '1h')
    
    # Try to get cached data first
    data = get_cached_data(symbol, timeframe)
    
    if data is None:
        # Fallback to live data fetching
        data = fetch_yfinance_data(symbol, period='90d', interval=timeframe)
    
    # Continue with your existing logic...
"""
