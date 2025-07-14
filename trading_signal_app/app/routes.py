# app/routes.py
from flask import current_app, render_template, request, jsonify
from .ml_logic import fetch_yfinance_data, get_model_prediction
from .helpers import calculate_stop_loss_value

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
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/check_model_status')
def check_model_status():
    # ... (This function remains unchanged) ...
    pass
