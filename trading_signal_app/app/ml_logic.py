# app/ml_logic.py

import pandas as pd
import numpy as np
import requests
import pandas_ta as ta
import yfinance as yf
import warnings
import asyncio # <--- IMPORT asyncio

warnings.filterwarnings('ignore')

# --- DATA FETCHING (No changes to the original proxy function) ---
# ... (fetch_data_via_proxies remains the same) ...

# --- yfinance FALLBACK FUNCTION (remains the same) ---
def fetch_yfinance_data(symbol, period='90d', interval='1h'):
    """Fetches data directly using the yfinance library as a fallback."""
    print(f"--- Fallback: Starting yfinance fetch for {symbol} ---")
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            print(f"   ⚠️ yfinance returned no data for {symbol}")
            return None
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        if not df.empty:
            print(f"   ✅ Success with yfinance fallback for {symbol}!")
            return df
    except Exception as e:
        print(f"   ❌ yfinance fallback failed for {symbol}: {e}")
    return None

# --- NEW: ASYNC WRAPPER FOR DATA FETCHING ---
async def fetch_data_for_symbol_async(symbol, timeframe):
    """
    Asynchronously fetches data for a single symbol by running the synchronous
    yfinance function in a separate thread.
    """
    loop = asyncio.get_running_loop()
    # Use run_in_executor to run the blocking yfinance call without blocking the event loop
    data = await loop.run_in_executor(
        None,  # Use the default thread pool executor
        fetch_yfinance_data, # The synchronous function to run
        symbol, # The first argument for the function
        '90d', # The second argument (period)
        timeframe # The third argument (interval)
    )
    # The proxy fallback could also be wrapped in an executor if needed,
    # but for simplicity, we'll prioritize the more reliable yfinance.
    return data


# --- Feature Engineering (create_features_for_prediction remains the same) ---
# ... (no changes needed here) ...

# --- Main Prediction Logic (get_model_prediction remains the same) ---
# This function is still useful for the single-asset signal generation
# ... (no changes needed here) ...