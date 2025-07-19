# app/ml_logic.py

import pandas as pd
import numpy as np
import pandas_ta as ta
import warnings
from pathlib import Path
import os
import yfinance as yf # <-- Add this import
from .data_cache_reader import get_cached_data

warnings.filterwarnings('ignore')

# This function will now be much more powerful.
def fetch_yfinance_data(symbol, period='90d', interval='1h', use_cache=True):
    """
    MODIFIED: Fetches data, prioritizing the local cache. If data is not in the cache
    or if use_cache is False, it falls back to fetching live data from yfinance.
    """
    # 1. Prioritize reading from the cache for performance and reliability
    if use_cache:
        cached_data = get_cached_data(symbol, interval)
        if cached_data is not None and not cached_data.empty:
            print(f"--- Loaded from CACHE for {symbol} ({interval}) ---")
            # Ensure proper column names (yfinance usually uses Titlecase)
            cached_data.columns = cached_data.columns.str.title()
            return cached_data

    # 2. Fallback to live yfinance fetch if cache is missed or disabled
    print(f"--- Cache miss or disabled. Fetching LIVE from yfinance for {symbol} ({interval}) ---")
    try:
        # Fetch live data
        df = yf.download(tickers=symbol, period=period, interval=interval, progress=False, auto_adjust=True)

        if df.empty:
            print(f"   ❌ yfinance returned no data for {symbol}")
            return None
        
        # yfinance now returns lowercase columns, ensure they are Titlecase for consistency
        df.columns = df.columns.str.title()
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        
        print(f"   ✅ Success! Loaded {len(df)} live rows from yfinance for {symbol}")
        return df
            
    except Exception as e:
        print(f"   ❌ yfinance live fetch FAILED for {symbol}: {e}")
        return None

# The rest of your ml_logic.py file (create_features_for_prediction, get_model_prediction)
# does NOT need to be changed.
# ...

# Keep this alias for backward compatibility within your project
def fetch_data_via_proxies(symbol, period='90d', interval='1h'):
    """Alias for the main data fetching function."""
    return fetch_yfinance_data(symbol, period, interval)
