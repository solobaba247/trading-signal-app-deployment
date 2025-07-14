from flask import current_app, render_template, request, jsonify
from .ml_logic import fetch_yfinance_data, get_model_prediction
from .helpers import calculate_stop_loss_value

# This function is now also aware of the period
def get_prediction_for_symbol(symbol, timeframe, period, model, scaler, feature_columns):
    """ Fetches data and generates a prediction for one symbol. """
    try:
        # Pass the period to the data fetching function
        data = fetch_yfinance_data(symbol, period, timeframe)
        if data is None or len(data) < 20: # Use a lower threshold as fallback might generate less data
            print(f"Skipping {symbol}: Insufficient data.")
            return None

        prediction = get_model_prediction(data, model, scaler, feature_columns)
        if "error" in prediction or prediction["signal"] == "HOLD":
            return None

        entry_price_val = prediction["latest_price"]
        sl_price_val = entry_price_val * (0.99 if prediction["signal"] == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if prediction["signal"] == 'BUY' else 0.98)

        return {
            "symbol": symbol, "signal": prediction["signal"],
            "confidence": f"{prediction['confidence']:.2%}",
            "entry_price": f"{entry_price_val:.5f}", "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": prediction["timestamp"]
        }
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

@current_app.route('/')
def index():
    timeframes = { '5 Minutes': '5m', '15 Minutes': '15m', '30 Minutes': '30m', '1 Hour': '1h', '4 Hours': '4h', '1 Day': '1d' }
    asset_classes = getattr(current_app, 'ASSET_CLASSES', {})
    return render_template('index.html', timeframes=timeframes, asset_classes=asset_classes)

@current_app.route('/api/generate_signal')
def generate_signal():
    try:
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', '1h')
        # NEW: Get period from request args
        period_days = request.args.get('period', '90')
        
        if not symbol: return jsonify({"error": "Symbol parameter is required"}), 400
        if not hasattr(current_app, 'model') or current_app.model is None: return jsonify({"error": "Model not loaded"}), 503
        
        # Format the period string for yfinance (e.g., '90d')
        period_str = f"{period_days}d"
        data = fetch_yfinance_data(symbol, period_str, timeframe)
        if data is None or len(data) < 20: return jsonify({"error": f"Insufficient data for {symbol} after all fallbacks"}), 400
        
        prediction = get_model_prediction(data, current_app.model, current_app.scaler, current_app.feature_columns)
        if "error" in prediction: return jsonify({"error": prediction["error"]}), 500
        
        entry_price_val = prediction["latest_price"]
        sl_price_val = entry_price_val * (0.99 if prediction["signal"] == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if prediction["signal"] == 'BUY' else 0.98)
        
        result = {
            "symbol": symbol, "signal": prediction["signal"],
            "confidence": f"{prediction['confidence']:.2%}",
            "entry_price": f"{entry_price_val:.5f}", "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": prediction["timestamp"]
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/scan_market', methods=['POST'])
def scan_market_route():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No JSON data provided"}), 400
            
        asset_type = data.get('asset_type')
        timeframe = data.get('timeframe', '1h')
        # NEW: Get period from request JSON
        period_days = data.get('period', 90) # Default to 90 if not provided
        period_str = f"{period_days}d"

        ASSET_CLASSES = getattr(current_app, 'ASSET_CLASSES', {})
        if not asset_type or asset_type not in ASSET_CLASSES:
            return jsonify({"error": "Invalid asset type", "available_types": list(ASSET_CLASSES.keys())}), 400
        if not hasattr(current_app, 'model') or current_app.model is None:
            return jsonify({"error": "Model not loaded"}), 503

        symbols_to_scan = ASSET_CLASSES[asset_type]
        scan_results = []
        for symbol in symbols_to_scan:
            result = get_prediction_for_symbol(
                symbol, timeframe, period_str, # Pass period here
                current_app.model, current_app.scaler, current_app.feature_columns
            )
            if result:
                scan_results.append(result)
        
        return jsonify(scan_results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/check_model_status')
def check_model_status():
    status = { "status": "error", "models_loaded": False }
    code = 503
    try:
        if (hasattr(current_app, 'model') and current_app.model and
            hasattr(current_app, 'scaler') and current_app.scaler and
            hasattr(current_app, 'feature_columns') and current_app.feature_columns):
            status.update({
                "status": "ok", "models_loaded": True,
                "message": "Model and scaler are loaded.",
                "feature_count": len(current_app.feature_columns)
            })
            code = 200
        else:
            status["message"] = "Model and/or scaler failed to load."
    except Exception as e:
        status["message"] = f"Error checking model status: {e}"
    return jsonify(status), code
