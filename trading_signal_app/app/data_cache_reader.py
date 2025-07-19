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

# ... (existing DataCacheReader class is unchanged) ...

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

# --- ADDED THE FOLLOWING FUNCTIONS ---
def list_cached_symbols(timeframe='1h'):
    """Convenience function to get list of available symbols in cache for a timeframe."""
    reader = DataCacheReader()
    # The app uses asset classes, so let's get symbols from all of them
    all_symbols = []
    for tf in ['1h', '4h', '1d']:
        all_symbols.extend(reader.get_available_symbols(tf))
    return sorted(list(set(all_symbols)))

def cache_status():
    """Convenience function to get detailed cache status."""
    return get_cache_info()
# --- END OF ADDED FUNCTIONS ---

# Example usage in your Flask routes:
"""
# In your routes.py, you can now use:
from .data_cache_reader import get_cached_data, is_cache_available
# ... (rest of the example) ...
"""
