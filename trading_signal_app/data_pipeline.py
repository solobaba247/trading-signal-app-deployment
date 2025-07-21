# trading-signal-app-deployment-main/trading_signal_app/data_pipeline.py
# --- MORE ROBUST AND EFFICIENT VERSION ---

import yfinance as yf
import os
import logging
from datetime import datetime
import time
import sys
import pandas as pd
import requests # <-- ADD THIS IMPORT

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CACHE_BASE_DIR = 'data_cache'
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
GROUP_DELAY_SECONDS = 10 # <-- ADD A DELAY BETWEEN ASSET CLASSES

class TradingDataPipeline:
    def __init__(self):
        # ... (asset_classes, timeframes, periods are unchanged) ...
        self.asset_classes = {
            'forex': [
                'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'USDCAD=X',
                'AUDUSD=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
                'AUDJPY=X', 'EURAUD=X', 'EURCHF=X', 'AUDCAD=X', 'GBPCHF=X'
            ],
            'stocks': [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA',
                'NFLX', 'ORCL', 'CRM', 'ADBE', 'PYPL', 'INTC', 'AMD'
            ],
            'crypto': [
                'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
                'SOL-USD', 'DOT-USD', 'DOGE-USD', 'AVAX-USD', 'MATIC-USD'
            ],
            'indices': [
                '^GSPC', '^DJI', '^IXIC', '^RUT', '^VIX', '^FTSE',
                '^GDAXI', '^FCHI', '^N225', '^HSI'
            ]
        }
        self.timeframes = ['1h', '4h', '1d']
        self.periods = {'1h': '730d', '4h': '730d', '1d': '10y'}
        
        self.results = {'successful': 0, 'failed': 0, 'errors': []}

        # --- KEY ADDITION: CREATE A SESSION OBJECT ---
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # --- END OF ADDITION ---


    def fetch_and_save_group(self, asset_class, symbols, timeframe):
        logger.info(f"--- Processing group: {asset_class.upper()} for timeframe: {timeframe} ---")
        
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                period = self.periods.get(timeframe, '10y')
                
                # --- MODIFICATION: PASS THE SESSION TO YFINANCE ---
                data = yf.download(
                    tickers=symbols,
                    period=period,
                    interval=timeframe,
                    group_by='ticker',
                    progress=False,
                    auto_adjust=True,
                    threads=True,
                    session=self.session # <-- PASS THE SESSION HERE
                )
                # --- END OF MODIFICATION ---

                # Filter out symbols that failed (yfinance returns object dtype columns for them)
                if isinstance(data.columns, pd.MultiIndex):
                    valid_cols = [col for col in data.columns if data[col].dtype != 'object']
                    if not valid_cols:
                        raise ValueError("Downloaded data contains no valid columns (all tickers may have failed).")
                    data = data[valid_cols]
                
                if not data.empty:
                    logger.info(f"Successfully downloaded group {asset_class} with {len(data.columns.get_level_values(0).unique())} symbols.")
                    break 
                else:
                    raise ValueError("Downloaded data is empty after filtering failed tickers.")

            except Exception as e:
                # ... (rest of the function is mostly unchanged) ...
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for group {asset_class} ({timeframe}): {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error(f"All retries failed for group {asset_class} ({timeframe}).")
                    self.results['errors'].append(f"Failed to download group {asset_class} ({timeframe})")
                    self.results['failed'] += len(symbols)
                    return
        
        # ... (rest of the function for saving data is unchanged) ...
        # Save each symbol's data to its own CSV file
        for symbol in symbols:
            try:
                # Handle single vs multi-symbol download result
                if len(symbols) > 1:
                    if symbol not in data.columns.get_level_values(0):
                        logger.warning(f"No data found for {symbol} in the downloaded group, skipping.")
                        continue # Skip to the next symbol
                    symbol_data = data[symbol]
                else:
                    symbol_data = data

                symbol_data.dropna(how='all', inplace=True)

                if symbol_data.empty:
                    raise ValueError(f"No valid data for symbol {symbol} after cleaning.")

                safe_symbol = symbol.replace('=', '_').replace('^', '_')
                cache_dir = os.path.join(CACHE_BASE_DIR, timeframe)
                os.makedirs(cache_dir, exist_ok=True)
                
                cache_file = os.path.join(cache_dir, f"{safe_symbol}.csv")
                symbol_data.to_csv(cache_file)
                self.results['successful'] += 1
                
            except Exception as e:
                logger.error(f"Failed to process/save data for {symbol}: {e}")
                if symbol not in str(self.results['errors']): # Avoid double-counting
                    self.results['failed'] += 1
                self.results['errors'].append(f"Processing failed for {symbol}: {e}")


    def run_pipeline(self):
        logger.info("Starting robust trading data pipeline")
        start_time = time.time()
        
        for timeframe in self.timeframes:
            for asset_class, symbols in self.asset_classes.items():
                if symbols:
                    self.fetch_and_save_group(asset_class, symbols, timeframe)
                    # --- ADDITION: BE POLITE, PAUSE BETWEEN BIG REQUESTS ---
                    logger.info(f"Pausing for {GROUP_DELAY_SECONDS} seconds before next asset class...")
                    time.sleep(GROUP_DELAY_SECONDS)
        
        # ... (rest of the run_pipeline method is unchanged) ...
        duration = time.time() - start_time
        total_tasks = sum(len(s) for s in self.asset_classes.values()) * len(self.timeframes)
        # Adjust failed count if it was over-counted from group failures
        self.results['failed'] = total_tasks - self.results['successful']

        success_rate = (self.results['successful'] / total_tasks) * 100 if total_tasks > 0 else 0
        
        logger.info("--- PIPELINE EXECUTION COMPLETE ---")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Successful tasks: {self.results['successful']}")
        logger.info(f"Failed tasks: {self.results['failed']}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        self.save_summary_report(duration, success_rate, total_tasks)
        
        if self.results['successful'] == 0 and self.results['failed'] > 0:
            logger.error("Pipeline failed completely with no successful data processing.")
            sys.exit(1)
        else:
            logger.info("Pipeline completed.")
            sys.exit(0)

    # ... (save_summary_report is unchanged) ...

if __name__ == "__main__":
    pipeline = TradingDataPipeline()
    pipeline.run_pipeline()
