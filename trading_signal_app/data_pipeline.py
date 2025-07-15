# data_pipeline.py

import os
import yfinance as yf
import pandas as pd
from pathlib import Path
from app import create_app  # Import the app factory
import time

# --- CONFIGURATION ---
# Create a directory to store our cached data
DATA_CACHE_DIR = Path("data_cache")
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Fetch slightly more data than needed to ensure indicators have enough history
FETCH_PERIOD = "120d" 

def run_pipeline():
    """
    The main function to fetch and cache all required financial data.
    """
    print("--- Starting Data Pipeline ---")
    
    # Create a temporary Flask app instance just to access its config
    app = create_app()
    asset_classes = app.config.get('ASSET_CLASSES', {})
    timeframes = app.config.get('TIMEFRAMES', {})

    # Flatten all symbols into a single unique list
    all_symbols = set()
    for category in asset_classes.values():
        for symbol in category:
            all_symbols.add(symbol)
            
    print(f"Found {len(all_symbols)} unique symbols to process across {len(timeframes)} timeframes.")

    # --- MAIN FETCHING LOOP ---
    for interval_name, interval_code in timeframes.items():
        print(f"\n--- Processing Timeframe: {interval_name} ({interval_code}) ---")
        
        # Create a subdirectory for this timeframe
        timeframe_dir = DATA_CACHE_DIR / interval_code
        timeframe_dir.mkdir(exist_ok=True)
        
        success_count = 0
        fail_count = 0

        for symbol in sorted(list(all_symbols)):
            try:
                # Define the cache file path
                # Use a sanitized filename for symbols like '^GSPC'
                sanitized_symbol = symbol.replace('^', 'INDEX_')
                cache_file = timeframe_dir / f"{sanitized_symbol}.csv"

                print(f"  Fetching {symbol}...")
                
                # Fetch data from yfinance
                data = yf.download(
                    tickers=symbol,
                    period=FETCH_PERIOD,
                    interval=interval_code,
                    auto_adjust=False, # Important for consistency
                    progress=False # Keep the log clean
                )

                if data.empty:
                    print(f"    - WARNING: No data returned for {symbol}.")
                    fail_count += 1
                    continue

                # Save the data to a CSV file
                data.to_csv(cache_file)
                success_count += 1
                
                # Small delay to be polite to Yahoo's servers
                time.sleep(0.5) 

            except Exception as e:
                print(f"    - ERROR fetching {symbol}: {e}")
                fail_count += 1
        
        print(f"--- Timeframe {interval_name} Complete. Success: {success_count}, Failed: {fail_count} ---")
        
    print("\n✅ --- Data Pipeline Finished Successfully! ---")


if __name__ == "__main__":
    run_pipeline()
