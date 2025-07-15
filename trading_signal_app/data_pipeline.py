#!/usr/bin/env python3
"""
Data Pipeline Producer Script
Fetches market data for all assets and timeframes, saves to local cache.
"""

import os
import sys
import pandas as pd
import yfinance as yf
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add the app directory to Python path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self):
        """Initialize the data pipeline."""
        self.base_dir = Path(__file__).parent
        self.cache_dir = self.base_dir / 'data_cache'
        
        # Import asset classes from Flask app config
        self.asset_classes = self._load_asset_classes()
        
        # Define timeframes to fetch
        self.timeframes = {
            '1h': {'period': '30d', 'interval': '1h'},
            '4h': {'period': '60d', 'interval': '4h'},
            '1d': {'period': '1y', 'interval': '1d'}
        }
        
        # Create cache directory structure
        self._setup_cache_directories()
    
    def _load_asset_classes(self):
        """Load asset classes from Flask app configuration."""
        try:
            # Import the Flask app factory
            from app import create_app
            
            # Create app instance to access config
            app = create_app()
            
            # Extract asset classes from app config
            with app.app_context():
                asset_classes = app.config.get('ASSET_CLASSES', {})
                logger.info(f"Loaded asset classes: {list(asset_classes.keys())}")
                return asset_classes
                
        except Exception as e:
            logger.error(f"Failed to load asset classes from Flask app: {e}")
            # Fallback to hardcoded asset classes if import fails
            return {
                "Forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X"],
                "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD"],
                "Stocks": ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "META", "TSLA"],
                "Indices": ["^GSPC", "^DJI", "^IXIC", "^RUT", "^FTSE"]
            }
    
    def _setup_cache_directories(self):
        """Create cache directory structure."""
        for timeframe in self.timeframes.keys():
            timeframe_dir = self.cache_dir / timeframe
            timeframe_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created cache directory: {timeframe_dir}")
    
    def fetch_asset_data(self, symbol, timeframe_config, timeframe_name):
        """
        Fetch data for a single asset and timeframe.
        
        Args:
            symbol (str): Asset symbol (e.g., 'AAPL', 'EURUSD=X')
            timeframe_config (dict): Configuration with period and interval
            timeframe_name (str): Name of the timeframe (e.g., '1h', '4h', '1d')
        
        Returns:
            tuple: (symbol, timeframe_name, success, data_or_error)
        """
        try:
            logger.info(f"Fetching {symbol} for {timeframe_name}")
            
            # Create yfinance ticker
            ticker = yf.Ticker(symbol)
            
            # Fetch historical data
            data = ticker.history(
                period=timeframe_config['period'],
                interval=timeframe_config['interval'],
                auto_adjust=False
            )
            
            if data.empty:
                logger.warning(f"No data returned for {symbol} ({timeframe_name})")
                return symbol, timeframe_name, False, "No data returned"
            
            # Clean the data
            data.columns = data.columns.str.title()
            if 'Adj Close' in data.columns:
                data = data.drop('Adj Close', axis=1)
            
            # Keep only OHLCV data and remove NaN values
            data = data[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
            if len(data) == 0:
                logger.warning(f"No valid data after cleaning for {symbol} ({timeframe_name})")
                return symbol, timeframe_name, False, "No valid data after cleaning"
            
            # Save to cache
            cache_file = self.cache_dir / timeframe_name / f"{symbol.replace('=', '_').replace('^', '_')}.csv"
            data.to_csv(cache_file)
            
            logger.info(f"✅ Successfully cached {symbol} ({timeframe_name}): {len(data)} rows")
            return symbol, timeframe_name, True, len(data)
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {symbol} ({timeframe_name}): {str(e)}")
            return symbol, timeframe_name, False, str(e)
    
    def run_pipeline(self, max_workers=10):
        """
        Run the complete data pipeline.
        
        Args:
            max_workers (int): Maximum number of concurrent workers
        """
        logger.info("🚀 Starting data pipeline execution")
        start_time = datetime.now()
        
        # Collect all tasks
        tasks = []
        for category, symbols in self.asset_classes.items():
            for symbol in symbols:
                for timeframe_name, timeframe_config in self.timeframes.items():
                    tasks.append((symbol, timeframe_config, timeframe_name))
        
        logger.info(f"📊 Total tasks to process: {len(tasks)}")
        
        # Execute tasks concurrently
        results = {
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.fetch_asset_data, symbol, config, tf_name): (symbol, tf_name)
                for symbol, config, tf_name in tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                symbol, timeframe_name, success, result = future.result()
                
                if success:
                    results['success'] += 1
                    results['details'].append(f"✅ {symbol} ({timeframe_name}): {result} rows")
                else:
                    results['failed'] += 1
                    results['details'].append(f"❌ {symbol} ({timeframe_name}): {result}")
        
        # Log final results
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("🎯 Pipeline execution completed")
        logger.info(f"⏱️  Duration: {duration}")
        logger.info(f"✅ Successful: {results['success']}")
        logger.info(f"❌ Failed: {results['failed']}")
        logger.info(f"📈 Success rate: {results['success']/(results['success'] + results['failed'])*100:.1f}%")
        
        # Create summary report
        self._create_summary_report(results, duration)
        
        return results
    
    def _create_summary_report(self, results, duration):
        """Create a summary report of the pipeline execution."""
        report_file = self.cache_dir / 'pipeline_summary.txt'
        
        with open(report_file, 'w') as f:
            f.write(f"Data Pipeline Execution Summary\n")
            f.write(f"{'='*50}\n")
            f.write(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"Duration: {duration}\n")
            f.write(f"Total Tasks: {results['success'] + results['failed']}\n")
            f.write(f"Successful: {results['success']}\n")
            f.write(f"Failed: {results['failed']}\n")
            f.write(f"Success Rate: {results['success']/(results['success'] + results['failed'])*100:.1f}%\n")
            f.write(f"\nDetailed Results:\n")
            f.write(f"{'-'*50}\n")
            
            for detail in results['details']:
                f.write(f"{detail}\n")
        
        logger.info(f"📋 Summary report saved to: {report_file}")

def main():
    """Main entry point."""
    logger.info("🏁 Data Pipeline Starting")
    
    try:
        # Create and run pipeline
        pipeline = DataPipeline()
        results = pipeline.run_pipeline()
        
        # Exit with error code if too many failures
        failure_rate = results['failed'] / (results['success'] + results['failed'])
        if failure_rate > 0.5:  # More than 50% failures
            logger.error(f"❌ High failure rate ({failure_rate*100:.1f}%), exiting with error code")
            sys.exit(1)
        
        logger.info("🎉 Data Pipeline Completed Successfully")
        
    except Exception as e:
        logger.error(f"💥 Pipeline failed with critical error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
