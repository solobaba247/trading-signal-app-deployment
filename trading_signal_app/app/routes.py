# app/routes.py

from flask import current_app, render_template, request, jsonify
import pandas as pd
from .ml_logic import create_features_for_prediction, fetch_yfinance_data
from .helpers import calculate_stop_loss_value

# --- NEW: THIS IS THE HOMEPAGE ROUTE ---
@current_app.route('/')
def index():
    """Renders the main HTML page."""
    # We can access the data we defined in __init__.py via current_app
    asset_classes = current_app.ASSET_CLASSES
    timeframes = current_app.TIMEFRAMES
    return render_template('index.html', asset_classes=asset_classes, timeframes=timeframes)


# --- Helper function for the scanner (now synchronous) ---
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

        # 2. Create features
        features_df = create_features_for_prediction(data)
        if features_df.empty:
            print(f"Skipping {symbol}: Feature calculation resulted in empty data.")
            return None

        latest_features = features_df.iloc[-1]
        last_price = latest_features['Close']

        # Prepare for both BUY and SELL scenarios
        buy_features = latest_features.copy()
        buy_features['trade_type_encoded'] = 0
        sell_features = latest_features.copy()
        sell_features['trade_type_encoded'] = 1
        
        buy_df = pd.DataFrame([buy_features])[feature_columns]
        sell_df = pd.DataFrame([sell_features])[feature_columns]

        buy_df_scaled = scaler.transform(buy_df)
        sell_df_scaled = scaler.transform(sell_df)

        buy_prob = model.predict_proba(buy_df_scaled)[0][1]
        sell_prob = model.predict_proba(sell_df_scaled)[0][1]

        # 3. Determine signal
        confidence_threshold = 0.55
        signal_type = "HOLD"
        confidence = 0.0

        if buy_prob > sell_prob and buy_prob > confidence_threshold:
            signal_type = "BUY"
            confidence = buy_prob
        elif sell_prob > buy_prob and sell_prob > confidence_threshold:
            signal_type = "SELL"
            confidence = sell_prob
        
        if signal_type == "HOLD":
            return None # Don't return HOLD signals

        # 4. Format result
        entry_price_val = last_price
        sl_price_val = entry_price_val * (0.99 if signal_type == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if signal_type == 'BUY' else 0.98)

        return {
            "symbol": symbol, "signal": signal_type, "confidence": f"{confidence:.2%}",
            "entry_price": f"{entry_price_val:.5f}",
            "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# --- Market Scan Route (now synchronous) ---
@current_app.route('/api/scan_market', methods=['POST'])
def scan_market_route():
    asset_type = request.json.get('asset_type')
    timeframe = request.json.get('timeframe', '1h')
    asset_classes = current_app.ASSET_CLASSES
    if not asset_type or asset_type not in asset_classes:
        return jsonify({"error": "Invalid asset type"}), 400

    symbols_to_scan = asset_classes[asset_type]
    
    scan_results = []
    # Use a simple loop
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

# --- Health Check Route ---
@current_app.route('/api/check_model_status')
def check_model_status():
    if current_app.model is not None and current_app.scaler is not None:
        return jsonify({"status": "ok", "message": "Model and scaler are loaded."}), 200
    else:
        return jsonify({
            "status": "error", 
            "message": "Model and/or scaler failed to load."
        }), 503
