# app/__init__.py (Complete version)

from flask import Flask, jsonify, request
import os
import joblib
from pathlib import Path
import logging
from .data_cache_reader import get_cached_data, list_cached_symbols, cache_status
from .ml_logic import get_model_prediction, fetch_yfinance_data, generate_fallback_prediction

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask app"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Initialize ML models as None (they will be loaded if available)
    app.model = None
    app.scaler = None
    app.feature_columns = None
    
    # Load ML models if available
    load_ml_models(app)
    
    # Asset classes for the API
    app.ASSET_CLASSES = {
        'forex': [
            'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD',
            'AUDUSD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
            'AUDJPY', 'EURAUD', 'EURCHF', 'AUDCAD', 'GBPCHF'
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
    
    # Register routes
    register_routes(app)
    
    return app

def load_ml_models(app):
    """Load ML models if they exist"""
    try:
        model_dir = Path(__file__).parent.parent / 'models'
        
        model_path = model_dir / 'trading_model.pkl'
        scaler_path = model_dir / 'scaler.pkl'
        features_path = model_dir / 'feature_columns.pkl'
        
        if all(path.exists() for path in [model_path, scaler_path, features_path]):
            app.model = joblib.load(model_path)
            app.scaler = joblib.load(scaler_path)
            app.feature_columns = joblib.load(features_path)
            logger.info("ML models loaded successfully")
        else:
            logger.warning("ML models not found. Using fallback prediction system.")
            
    except Exception as e:
        logger.error(f"Failed to load ML models: {e}")
        app.model = None
        app.scaler = None
        app.feature_columns = None

def register_routes(app):
    """Register all API routes"""
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'ml_models_loaded': app.model is not None,
            'cache_status': cache_status()
        })
    
    @app.route('/api/symbols', methods=['GET'])
    def get_symbols():
        """Get all available symbols by category"""
        return jsonify({
            'asset_classes': app.ASSET_CLASSES,
            'cached_symbols': list_cached_symbols()
        })
    
    @app.route('/api/symbols/<category>', methods=['GET'])
    def get_symbols_by_category(category):
        """Get symbols for a specific category"""
        if category not in app.ASSET_CLASSES:
            return jsonify({'error': 'Invalid category'}), 400
        
        return jsonify({
            'category': category,
            'symbols': app.ASSET_CLASSES[category]
        })
    
    @app.route('/api/data/<symbol>', methods=['GET'])
    def get_symbol_data(symbol):
        """Get cached data for a symbol"""
        interval = request.args.get('interval', '1h')
        
        # Check if symbol is valid
        all_symbols = []
        for symbols in app.ASSET_CLASSES.values():
            all_symbols.extend(symbols)
        
        if symbol not in all_symbols:
            return jsonify({'error': 'Symbol not found'}), 404
        
        # Get cached data
        data = get_cached_data(symbol, interval)
        
        if data is None:
            return jsonify({
                'error': 'Data not found in cache',
                'message': 'Please run the data pipeline first'
            }), 404
        
        # Convert to JSON-serializable format
        data_dict = {
            'symbol': symbol,
            'interval': interval,
            'data': data.tail(100).to_dict('records'),  # Last 100 records
            'latest_price': float(data['Close'].iloc[-1]),
            'timestamp': data.index[-1].isoformat()
        }
        
        return jsonify(data_dict)
    
    @app.route('/api/predict/<symbol>', methods=['GET'])
    def predict_symbol(symbol):
        """Get ML prediction for a symbol"""
        interval = request.args.get('interval', '1h')
        
        # Get data
        data = get_cached_data(symbol, interval)
        
        if data is None:
            return jsonify({
                'error': 'Data not found in cache',
                'message': 'Please run the data pipeline first'
            }), 404
        
        # Get prediction
        if app.model is not None and app.scaler is not None:
            prediction = get_model_prediction(data, app.model, app.scaler, app.feature_columns)
        else:
            prediction = generate_fallback_prediction(data)
        
        prediction['symbol'] = symbol
        prediction['interval'] = interval
        
        return jsonify(prediction)
    
    @app.route('/api/batch_predict', methods=['POST'])
    def batch_predict():
        """Get predictions for multiple symbols"""
        try:
            request_data = request.get_json()
            symbols = request_data.get('symbols', [])
            interval = request_data.get('interval', '1h')
            
            if not symbols:
                return jsonify({'error': 'No symbols provided'}), 400
            
            predictions = {}
            
            for symbol in symbols:
                data = get_cached_data(symbol, interval)
                
                if data is not None:
                    if app.model is not None and app.scaler is not None:
                        prediction = get_model_prediction(data, app.model, app.scaler, app.feature_columns)
                    else:
                        prediction = generate_fallback_prediction(data)
                    
                    predictions[symbol] = prediction
                else:
                    predictions[symbol] = {
                        'error': 'Data not found in cache',
                        'signal': 'HOLD',
                        'confidence': '0.00%'
                    }
            
            return jsonify({
                'interval': interval,
                'predictions': predictions,
                'total_symbols': len(symbols),
                'successful_predictions': len([p for p in predictions.values() if 'error' not in p])
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/market_overview', methods=['GET'])
    def market_overview():
        """Get market overview with key metrics"""
        try:
            overview = {
                'forex': {},
                'stocks': {},
                'crypto': {},
                'indices': {}
            }
            
            # Get sample data from each category
            for category, symbols in app.ASSET_CLASSES.items():
                for symbol in symbols[:5]:  # Get first 5 symbols from each category
                    data = get_cached_data(symbol, '1h')
                    
                    if data is not None:
                        latest_price = float(data['Close'].iloc[-1])
                        prev_price = float(data['Close'].iloc[-2]) if len(data) > 1 else latest_price
                        change = ((latest_price - prev_price) / prev_price) * 100
                        
                        overview[category][symbol] = {
                            'price': f"{latest_price:.5f}",
                            'change': f"{change:.2f}%",
                            'volume': int(data['Volume'].iloc[-1]) if 'Volume' in data else 0
                        }
            
            return jsonify({
                'timestamp': pd.Timestamp.now().isoformat(),
                'overview': overview
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/cache/refresh', methods=['POST'])
    def refresh_cache():
        """Trigger cache refresh (would normally call the data pipeline)"""
        return jsonify({
            'message': 'Cache refresh requested',
            'note': 'Please run the data pipeline script manually: python updated_data_pipeline.py'
        })
    
    @app.route('/api/cache/status', methods=['GET'])
    def get_cache_status():
        """Get detailed cache status"""
        return jsonify(cache_status())
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
