# app/ml_logic.py

import pandas as pd
import numpy as np
# yfinance is no longer needed here for fetching, but still for pandas_ta
import pandas_ta as ta
import warnings
from pathlib import Path # Use pathlib for robust path handling
import os

warnings.filterwarnings('ignore')

# Define the path to the cache directory relative to this file
# This is more robust than assuming the current working directory
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR.parent
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"

def fetch_yfinance_data(symbol, period='90d', interval='1h'):
    """
    MODIFIED: Fetches data from the local file cache instead of yfinance.
    """
    print(f"--- Reading from CACHE for {symbol} ({interval}) ---")
    try:
        # Sanitize symbol to match the filename saved by the pipeline
        sanitized_symbol = symbol.replace('^', 'INDEX_')
        
        # Construct the expected file path
        cache_file = DATA_CACHE_DIR / interval / f"{sanitized_symbol}.csv"

        if not os.path.exists(cache_file):
            print(f"   ❌ CACHE MISS: File not found at {cache_file}")
            print(f"   ACTION: Please run the `python data_pipeline.py` script first.")
            return None

        # Read the data from the CSV
        # Set the Datetime column as the index, which is what yfinance does
        df = pd.read_csv(cache_file, index_col='Date', parse_dates=True)
        
        if df.empty:
            print(f"   ⚠️ Cache file for {symbol} is empty.")
            return None
        
        # Ensure proper column names (yfinance usually uses Titlecase)
        df.columns = df.columns.str.title()
        if 'Adj Close' in df.columns:
            df = df.drop('Adj Close', axis=1)
        
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        
        print(f"   ✅ Success! Loaded {len(df)} rows from cache for {symbol}")
        return df
            
    except Exception as e:
        print(f"   ❌ Cache read FAILED for {symbol}: {e}")
        return None

# The rest of your ml_logic.py file (create_features_for_prediction, get_model_prediction)
# does NOT need to be changed.
# ... (keep the rest of the file as is) ...

# Keep this alias for backward compatibility within your project
def fetch_data_via_proxies(symbol, period='90d', interval='1h'):
    """Alias for the main data fetching function."""
    return fetch_yfinance_data(symbol, period, interval)
