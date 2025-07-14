# app/routes.py
from flask import current_app, render_template, request, jsonify
from .ml_logic import fetch_yfinance_data, get_model_prediction
from .helpers import calculate_stop_loss_value, get_technical_indicators, get_latest_price # Added missing helper imports

@current_app.route('/')
def index():
    timeframes = { '5m': '5 Minutes', '15m': '15 Minutes', '30m': '30 Minutes', '1h': '1 Hour', '4h': '4 Hours', '1d': '1 Day' }
    asset_classes = getattr(current_app, 'ASSET_CLASSES', {})
    return render_template('index.html', timeframes=timeframes, asset_classes=asset_classes)

@current_app.route('/api/generate_signal')
def generate_signal():
    try:
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', '1h')
        period_days = request.args.get('period', '90')
        
        if not symbol: return jsonify({"error": "Symbol parameter is required"}), 400
        if not hasattr(current_app, 'model') or current_app.model is None: return jsonify({"error": "ML Model is not loaded on the server."}), 503
        
        period_str = f"{period_days}d"
        data = fetch_yfinance_data(symbol, period_str, timeframe)
        if data is None or len(data) < 30: return jsonify({"error": f"Could not fetch sufficient historical data for {symbol} after all server fallbacks."}), 400
        
        prediction = get_model_prediction(data, current_app.model, current_app.scaler, current_app.feature_columns)
        if "error" in prediction: return jsonify({"error": prediction["error"]}), 500
        
        entry_price_val = prediction["latest_price"]
        sl_price_val = entry_price_val * (0.99 if prediction["signal"] == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if prediction["signal"] == 'BUY' else 0.98)
        
        result = {
            "symbol": symbol, "signal": prediction["signal"], "confidence": f"{prediction['confidence']:.2%}",
            "entry_price": f"{entry_price_val:.5f}", "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": prediction["timestamp"]
        }
        return jsonify(result)
    except Exception as e:
        # It's good practice to log the actual exception for debugging
        current_app.logger.error(f"Error in /api/generate_signal: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# ===================================================================
#  FIX IS HERE: Implement the health check function correctly
# ===================================================================
@current_app.route('/api/check_model_status')
def check_model_status():
    """
    Checks if the ML model and its components are loaded correctly.
    This is used by Render for health checks.
    """
    # Check if the attributes we set in __init__.py exist on the app object
    model_loaded = hasattr(current_app, 'model') and current_app.model is not None
    scaler_loaded = hasattr(current_app, 'scaler') and current_app.scaler is not None
    features_loaded = hasattr(current_app, 'feature_columns') and current_app.feature_columns is not None

    if model_loaded and scaler_loaded and features_loaded:
        status = {
            "status": "ok",
            "message": "ML model and all components are loaded successfully."
        }
        # Return a 200 OK status, which tells Render the app is healthy
        return jsonify(status), 200
    else:
        status = {
            "status": "error",
            "message": "One or more ML components failed to load. Check server logs."
        }
        # Return a 503 Service Unavailable status, which tells Render the app is unhealthy
        return jsonify(status), 503

# You may also want to add routes for your other helper functions if they are called from JS
@current_app.route('/api/get_indicators')
def api_get_indicators():
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', '1h')
    return get_technical_indicators(symbol, timeframe)

@current_app.route('/api/get_price')
def api_get_price():
    symbol = request.args.get('symbol')
    return get_latest_price(symbol)
