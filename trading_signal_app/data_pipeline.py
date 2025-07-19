# trading-signal-app-deployment-main/trading_signal_app/data_pipeline.py
# --- MORE ROBUST AND EFFICIENT VERSION ---

import yfinance as yf
import os
import logging
from datetime import datetime
import time
import sys
import pandas as pd

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

class TradingDataPipeline:
    def __init__(self):
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

    # <-- KEY CHANGE: This function now fetches a group of symbols at once -->
    def fetch_and_save_group(self, asset_class, symbols, timeframe):
        logger.info(f"--- Processing group: {asset_class.upper()} for timeframe: {timeframe} ---")
        
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                period = self.periods.get(timeframe, '10y')
                
                # Download all symbols in the group with one API call
                data = yf.download(
                    tickers=symbols,
                    period=period,
                    interval=timeframe,
                    group_by='ticker',
                    progress=False,
                    auto_adjust=True,
                    threads=True # Use multiple threads for yfinance download
                )
                
                if not data.empty:
                    logger.info(f"Successfully downloaded group {asset_class}")
                    break # Exit retry loop on success
                else:
                    raise ValueError("Downloaded data is empty.")

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for group {asset_class} ({timeframe}): {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error(f"All retries failed for group {asset_class} ({timeframe}).")
                    self.results['errors'].append(f"Failed to download group {asset_class} ({timeframe})")
                    # Mark all symbols in this group as failed for reporting
                    self.results['failed'] += len(symbols)
                    return

        # Save each symbol's data to its own CSV file
        for symbol in symbols:
            try:
                symbol_data = data[symbol] if len(symbols) > 1 else data
                symbol_data.dropna(how='all', inplace=True)

                if symbol_data.empty:
                    raise ValueError(f"No valid data for symbol {symbol} in the downloaded group.")

                safe_symbol = symbol.replace('=', '_').replace('^', '_')
                cache_dir = os.path.join(CACHE_BASE_DIR, timeframe)
                os.makedirs(cache_dir, exist_ok=True)
                
                cache_file = os.path.join(cache_dir, f"{safe_symbol}.csv")
                symbol_data.to_csv(cache_file)
                self.results['successful'] += 1
                
            except Exception as e:
                logger.error(f"Failed to process/save data for {symbol}: {e}")
                self.results['failed'] += 1
                self.results['errors'].append(f"Processing failed for {symbol}: {e}")

    def run_pipeline(self):
        logger.info("Starting robust trading data pipeline")
        start_time = time.time()
        
        for timeframe in self.timeframes:
            for asset_class, symbols in self.asset_classes.items():
                if symbols:
                    self.fetch_and_save_group(asset_class, symbols, timeframe)
        
        duration = time.time() - start_time
        total_tasks = sum(len(s) for s in self.asset_classes.values()) * len(self.timeframes)
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
    
    def save_summary_report(self, duration, success_rate, total_tasks):
        os.makedirs(CACHE_BASE_DIR, exist_ok=True)
        summary = {
            'execution_time': datetime.utcnow().isoformat(),
            'duration_seconds': round(duration, 2),
            'total_tasks': total_tasks,
            'successful': self.results['successful'],
            'failed': self.results['failed'],
            'success_rate': round(success_rate, 1),
            'errors': self.results['errors'][:20]
        }
        
        report_path = os.path.join(CACHE_BASE_DIR, 'pipeline_summary.txt')
        with open(report_path, 'w') as f:
            f.write("Pipeline Summary Report\n=====================\n")
            for key, value in summary.items():
                if key != 'errors':
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            if summary['errors']:
                f.write("\nFirst 20 Errors:\n")
                for i, error in enumerate(summary['errors'], 1):
                    f.write(f"{i}. {error}\n")
        logger.info(f"Summary report saved to {report_path}")

if __name__ == "__main__":
    pipeline = TradingDataPipeline()
    pipeline.run_pipeline()
