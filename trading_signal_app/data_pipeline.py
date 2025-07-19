# trading-signal-app-deployment-main/trading_signal_app/data_pipeline.py

import yfinance as yf
import os
import logging
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import pandas as pd

# --- Configuration ---
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define the root directory for the cache, assuming the script runs from the repository root
CACHE_BASE_DIR = 'trading_signal_app/data_cache'

class TradingDataPipeline:
    def __init__(self):
        self.max_workers = int(os.getenv('MAX_WORKERS', '10'))
        
        # Asset classes used by the application
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
        # Use yfinance-compatible symbols for forex
        self.asset_classes['forex'] = [f.replace('EURUSD', 'EURUSD=X') for f in self.asset_classes['forex']]

        self.all_symbols = [symbol for sublist in self.asset_classes.values() for symbol in sublist]
        self.timeframes = ['1h', '4h', '1d']
        self.periods = {'1h': '730d', '4h': '730d', '1d': '10y'}
        
        self.results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
    
    def fetch_and_save_data(self, symbol, timeframe):
        """Fetch data for a single symbol and timeframe using yfinance and save as CSV"""
        try:
            logger.info(f"Fetching data for {symbol} ({timeframe})")
            
            # Use appropriate periods for different intervals
            period = self.periods.get(timeframe, '10y')
            data = yf.download(tickers=symbol, period=period, interval=timeframe, progress=False, auto_adjust=True)
            
            if data.empty:
                raise ValueError(f"No data returned from yfinance for {symbol} ({timeframe})")
            
            # Sanitize symbol for filename (compatible with data_cache_reader)
            safe_symbol = symbol.replace('=', '_').replace('^', '_')
            
            # Create cache directories if they don't exist
            cache_dir = os.path.join(CACHE_BASE_DIR, timeframe)
            os.makedirs(cache_dir, exist_ok=True)
            
            # Save data to CSV
            cache_file = os.path.join(cache_dir, f"{safe_symbol}.csv")
            data.to_csv(cache_file)
            
            self.results['successful'] += 1
            return {'symbol': symbol, 'timeframe': timeframe, 'status': 'success'}
            
        except Exception as e:
            error_msg = f"Failed for {symbol} ({timeframe}): {str(e)}"
            logger.error(error_msg)
            self.results['failed'] += 1
            self.results['errors'].append(error_msg)
            return {'symbol': symbol, 'timeframe': timeframe, 'status': 'error', 'error': str(e)}

    def run_pipeline(self):
        """Run the complete data pipeline"""
        logger.info("Starting trading data pipeline with yfinance")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = []
            for symbol in self.all_symbols:
                for timeframe in self.timeframes:
                    tasks.append(executor.submit(self.fetch_and_save_data, symbol, timeframe))
            
            for future in as_completed(tasks):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"A task generated an exception: {e}")

        duration = time.time() - start_time
        total_tasks = len(self.all_symbols) * len(self.timeframes)
        success_rate = (self.results['successful'] / total_tasks) * 100 if total_tasks > 0 else 0
        
        logger.info("Pipeline execution completed")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Successful tasks: {self.results['successful']}")
        logger.info(f"Failed tasks: {self.results['failed']}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        self.save_summary_report(duration, success_rate, total_tasks)
        
        if self.results['failed'] > 0 and self.results['successful'] == 0:
            logger.error("Pipeline failed completely with no successful data processing")
            sys.exit(1)
        else:
            logger.info("Pipeline completed.")
            sys.exit(0)
    
    def save_summary_report(self, duration, success_rate, total_tasks):
        """Save pipeline summary report"""
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
        
        # Save JSON and TXT reports
        with open(os.path.join(CACHE_BASE_DIR, 'pipeline_summary.json'), 'w') as f:
            import json
            json.dump(summary, f, indent=2)
            
        with open(os.path.join(CACHE_BASE_DIR, 'pipeline_summary.txt'), 'w') as f:
            f.write("Pipeline Summary Report\n=====================\n")
            for key, value in summary.items():
                if key != 'errors':
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            if summary['errors']:
                f.write("\nFirst 20 Errors:\n")
                for i, error in enumerate(summary['errors'], 1):
                    f.write(f"{i}. {error}\n")

if __name__ == "__main__":
    pipeline = TradingDataPipeline()
    pipeline.run_pipeline()
