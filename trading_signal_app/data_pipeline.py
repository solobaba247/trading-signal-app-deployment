import requests
import json
import os
import logging
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_pipeline.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ForexDataPipeline:
    def __init__(self, base_url="https://my-finance-appi.onrender.com/api/forex"):
        self.base_url = base_url
        self.max_workers = int(os.getenv('MAX_WORKERS', '10'))
        self.continue_on_failure = os.getenv('CONTINUE_ON_FAILURE', 'true').lower() == 'true'
        
        # Common forex pairs
        self.forex_pairs = [
            'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD',
            'AUDUSD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
            'AUDJPY', 'EURAUD', 'EURCHF', 'AUDCAD', 'GBPCHF'
        ]
        
        self.results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
    
    def fetch_forex_data(self, symbol):
        """Fetch data for a single forex pair"""
        try:
            url = f"{self.base_url}/{symbol}"
            logger.info(f"Fetching data for {symbol}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate required fields
            required_fields = ['currentPrice', 'dayHigh', 'dayLow', 'pairName', 'symbol']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Save data to cache
            self.save_to_cache(symbol, data)
            
            logger.info(f"Successfully fetched data for {symbol}")
            self.results['successful'] += 1
            
            return {
                'symbol': symbol,
                'status': 'success',
                'data': data
            }
            
        except requests.RequestException as e:
            error_msg = f"Request failed for {symbol}: {str(e)}"
            logger.error(error_msg)
            self.results['failed'] += 1
            self.results['errors'].append(error_msg)
            
            return {
                'symbol': symbol,
                'status': 'error',
                'error': str(e)
            }
            
        except ValueError as e:
            error_msg = f"Data validation failed for {symbol}: {str(e)}"
            logger.error(error_msg)
            self.results['failed'] += 1
            self.results['errors'].append(error_msg)
            
            return {
                'symbol': symbol,
                'status': 'error',
                'error': str(e)
            }
        
        except Exception as e:
            error_msg = f"Unexpected error for {symbol}: {str(e)}"
            logger.error(error_msg)
            self.results['failed'] += 1
            self.results['errors'].append(error_msg)
            
            return {
                'symbol': symbol,
                'status': 'error',
                'error': str(e)
            }
    
    def save_to_cache(self, symbol, data):
        """Save data to cache files"""
        try:
            # Create cache directories if they don't exist
            os.makedirs('data_cache/1h', exist_ok=True)
            os.makedirs('data_cache/4h', exist_ok=True)
            os.makedirs('data_cache/1d', exist_ok=True)
            
            # Add timestamp to data
            data['timestamp'] = datetime.utcnow().isoformat()
            
            # Save to different timeframe folders (for now, same data)
            for timeframe in ['1h', '4h', '1d']:
                cache_file = f'data_cache/{timeframe}/{symbol}.json'
                with open(cache_file, 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Failed to save cache for {symbol}: {str(e)}")
            raise
    
    def run_pipeline(self):
        """Run the complete data pipeline"""
        logger.info("Starting forex data pipeline")
        logger.info(f"Max workers: {self.max_workers}")
        logger.info(f"Continue on failure: {self.continue_on_failure}")
        logger.info(f"Processing {len(self.forex_pairs)} forex pairs")
        
        start_time = time.time()
        
        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(self.fetch_forex_data, symbol): symbol 
                for symbol in self.forex_pairs
            }
            
            # Process completed tasks
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    logger.info(f"Completed processing {symbol}: {result['status']}")
                except Exception as e:
                    logger.error(f"Task failed for {symbol}: {str(e)}")
                    self.results['failed'] += 1
                    self.results['errors'].append(f"Task execution failed for {symbol}: {str(e)}")
        
        duration = time.time() - start_time
        success_rate = (self.results['successful'] / len(self.forex_pairs)) * 100
        
        # Log final results
        logger.info("Pipeline execution completed")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Successful: {self.results['successful']}")
        logger.info(f"Failed: {self.results['failed']}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        # Save summary report
        self.save_summary_report(duration, success_rate)
        
        # Determine exit code
        if success_rate == 0 and not self.continue_on_failure:
            logger.error("Pipeline failed completely with 0% success rate")
            sys.exit(1)
        elif success_rate < 50 and not self.continue_on_failure:
            logger.error(f"Pipeline success rate too low: {success_rate:.1f}%")
            sys.exit(1)
        else:
            logger.info("Pipeline completed successfully")
            sys.exit(0)
    
    def save_summary_report(self, duration, success_rate):
        """Save pipeline summary report"""
        try:
            os.makedirs('data_cache', exist_ok=True)
            
            summary = {
                'execution_time': datetime.utcnow().isoformat(),
                'duration_seconds': round(duration, 2),
                'total_symbols': len(self.forex_pairs),
                'successful': self.results['successful'],
                'failed': self.results['failed'],
                'success_rate': round(success_rate, 1),
                'errors': self.results['errors'][:10]  # Limit to first 10 errors
            }
            
            # Save JSON summary
            with open('data_cache/pipeline_summary.json', 'w') as f:
                json.dump(summary, f, indent=2)
            
            # Save text summary
            with open('data_cache/pipeline_summary.txt', 'w') as f:
                f.write(f"Pipeline Summary Report\n")
                f.write(f"=====================\n")
                f.write(f"Execution Time: {summary['execution_time']}\n")
                f.write(f"Duration: {summary['duration_seconds']} seconds\n")
                f.write(f"Total Symbols: {summary['total_symbols']}\n")
                f.write(f"Successful: {summary['successful']}\n")
                f.write(f"Failed: {summary['failed']}\n")
                f.write(f"Success rate: {summary['success_rate']}%\n")
                
                if summary['errors']:
                    f.write(f"\nFirst {len(summary['errors'])} Errors:\n")
                    for i, error in enumerate(summary['errors'], 1):
                        f.write(f"{i}. {error}\n")
                        
        except Exception as e:
            logger.error(f"Failed to save summary report: {str(e)}")

def main():
    """Main entry point"""
    try:
        pipeline = ForexDataPipeline()
        pipeline.run_pipeline()
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed with unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
