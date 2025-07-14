# app/routes.py

from flask import current_app, render_template, request, jsonify
from .ml_logic import fetch_yfinance_data, get_model_prediction
from .helpers import calculate_stop_loss_value # Import from helpers to avoid duplication

def get_prediction_for_symbol(symbol, timeframe, model, scaler, feature_columns):
    """
    Fetches data and generates a prediction for one symbol.
    """
    try:
        # 1. Fetch data
        data = fetch_yfinance_data(symbol, '90d', timeframe)
        if data is None or len(data) < 50:
            print(f"Skipping {symbol}: Insufficient data.")
            return None

        # 2. Get model prediction using the ml_logic function
        prediction = get_model_prediction(data, model, scaler, feature_columns)
        
        if "error" in prediction:
            print(f"Skipping {symbol}: {prediction['error']}")
            return None
        
        if prediction["signal"] == "HOLD":
            return None  # Don't return HOLD signals

        # 3. Calculate stop loss and take profit
        entry_price_val = prediction["latest_price"]
        sl_price_val = entry_price_val * (0.99 if prediction["signal"] == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if prediction["signal"] == 'BUY' else 0.98)

        return {
            "symbol": symbol,
            "signal": prediction["signal"],
            "confidence": f"{prediction['confidence']:.2%}",
            "entry_price": f"{entry_price_val:.5f}",
            "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": prediction["timestamp"]
        }

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# --- Routes ---
@current_app.route('/')
def index():
    """Home page - HTML interface"""
    # Define timeframes for the template
    timeframes = {
        '1 Minute': '1m',
        '5 Minutes': '5m',
        '15 Minutes': '15m',
        '30 Minutes': '30m',
        '1 Hour': '1h',
        '4 Hours': '4h',
        '1 Day': '1d'
    }
    
    # Get asset classes from the app config
    asset_classes = getattr(current_app, 'ASSET_CLASSES', {})
    
    return render_template('index.html', 
                         timeframes=timeframes,
                         asset_classes=asset_classes)

@current_app.route('/api')
def api_info():
    """API information endpoint"""
    return jsonify({
        "message": "Trading Signal API",
        "endpoints": {
            "health_check": "/api/check_model_status",
            "market_scan": "/api/scan_market",
            "generate_signal": "/api/generate_signal"
        }
    })

@current_app.route('/api/generate_signal')
def generate_signal():
    """Generate signal for a single symbol"""
    try:
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', '1h')
        
        if not symbol:
            return jsonify({"error": "Symbol parameter is required"}), 400
        
        # Check if models are loaded
        if not hasattr(current_app, 'model') or current_app.model is None:
            return jsonify({"error": "Model not loaded"}), 503
        
        # Fetch data and generate prediction
        data = fetch_yfinance_data(symbol, '90d', timeframe)
        if data is None or len(data) < 50:
            return jsonify({"error": f"Insufficient data for {symbol}"}), 400
        
        prediction = get_model_prediction(data, current_app.model, current_app.scaler, current_app.feature_columns)
        
        if "error" in prediction:
            return jsonify({"error": prediction["error"]}), 500
        
        # Calculate stop loss and take profit
        entry_price_val = prediction["latest_price"]
        sl_price_val = entry_price_val * (0.99 if prediction["signal"] == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if prediction["signal"] == 'BUY' else 0.98)
        
        result = {
            "symbol": symbol,
            "signal": prediction["signal"],
            "confidence": f"{prediction['confidence']:.2%}",
            "entry_price": f"{entry_price_val:.5f}",
            "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": prediction["timestamp"]
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/scan_market', methods=['POST'])
def scan_market_route():
    """Market scan endpoint"""
    try:
        ASSET_CLASSES = getattr(current_app, 'ASSET_CLASSES', {})
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        asset_type = data.get('asset_type')
        timeframe = data.get('timeframe', '1h')
        
        if not asset_type or asset_type not in ASSET_CLASSES:
            return jsonify({
                "error": "Invalid asset type", 
                "available_types": list(ASSET_CLASSES.keys())
            }), 400

        # Check if models are loaded
        if not hasattr(current_app, 'model') or current_app.model is None:
            return jsonify({"error": "Model not loaded"}), 503

        symbols_to_scan = ASSET_CLASSES[asset_type]
        
        scan_results = []
        for symbol in symbols_to_scan:
            result = get_prediction_for_symbol(
                symbol, 
                timeframe, 
                current_app.model, 
                current_app.scaler, 
                current_app.feature_columns
            )
            if result:
                scan_results.append(result)
        
        return jsonify(scan_results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/check_model_status')
def check_model_status():
    """Health check endpoint"""
    try:
        if (hasattr(current_app, 'model') and current_app.model is not None and 
            hasattr(current_app, 'scaler') and current_app.scaler is not None and
            hasattr(current_app, 'feature_columns') and current_app.feature_columns is not None):
            return jsonify({
                "status": "ok",
                "models_loaded": True,
                "message": "Model and scaler are loaded.",
                "feature_count": len(current_app.feature_columns)
            }), 200
        else:
            return jsonify({
                "status": "error",
                "models_loaded": False,
                "message": "Model and/or scaler failed to load."
            }), 503
    except Exception as e:
        return jsonify({
            "status": "error",
            "models_loaded": False,
            "message": f"Error checking model status: {str(e)}"
        }), 500
