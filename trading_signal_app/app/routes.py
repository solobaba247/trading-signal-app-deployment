# app/routes.py

from flask import current_app, render_template, request, jsonify
import pandas as pd
import asyncio
# V-- THIS IS THE KEY CHANGE: We import all logic functions from ml_logic.py --V
from .ml_logic import get_model_prediction, create_features_for_prediction, fetch_data_for_symbol_async
from .helpers import calculate_stop_loss_value, get_latest_price, get_technical_indicators

# --- Helper function for the market scanner ---
async def get_prediction_for_symbol(symbol, timeframe, model, scaler, feature_columns):
    """Async-compatible function to fetch data and generate a prediction for one symbol."""
    try:
        # 1. Fetch data asynchronously
        data = await fetch_data_for_symbol_async(symbol, timeframe)
        if data is None or len(data) < 50:
            print(f"Skipping {symbol}: Insufficient data.")
            return None

        # 2. Create features using the function from ml_logic
        features_df = create_features_for_prediction(data, feature_columns)
        if features_df.empty:
            print(f"Skipping {symbol}: Feature calculation resulted in empty data.")
            return None

        latest_features = features_df.iloc[-1]
        last_price = latest_features['Close']

        # 3. Prepare for both BUY and SELL scenarios
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

        # 4. Determine signal based on probabilities
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
            return None # Don't return HOLD signals for the scanner

        # 5. Format the final result
        entry_price_val = last_price
        sl_price_val = entry_price_val * (0.99 if signal_type == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if signal_type == 'BUY' else 0.98)

        return {
            "symbol": symbol, "signal": signal_type, "confidence": f"{confidence:.2%}",
            "entry_price": f"{entry_price_val:.5f}", "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# --- Main API Routes ---

@current_app.route('/api/scan_market', methods=['POST'])
async def scan_market_route():
    """API endpoint for the market scanner feature."""
    ASSET_CLASSES = getattr(current_app, 'ASSET_CLASSES', {})
    asset_type = request.json.get('asset_type')
    timeframe = request.json.get('timeframe', '1h')

    if not asset_type or asset_type not in ASSET_CLASSES:
        return jsonify({"error": "Invalid asset type"}), 400

    symbols_to_scan = ASSET_CLASSES[asset_type]
    
    tasks = [get_prediction_for_symbol(
        symbol, timeframe, current_app.model, current_app.scaler, current_app.feature_columns
    ) for symbol in symbols_to_scan]
    
    scan_results = await asyncio.gather(*tasks)
    final_results = [result for result in scan_results if result is not None]
    
    return jsonify(final_results)

@current_app.route('/api/check_model_status')
def check_model_status():
    """Health check endpoint for Render."""
    if current_app.model is not None and current_app.scaler is not None:
        return jsonify({"status": "ok", "message": "Model and scaler are loaded."}), 200
    else:
        return jsonify({
            "status": "error", "message": "Model and/or scaler failed to load."
        }), 503

# You will need to add your other routes (like the single asset signal) here if they exist.
# The original prompt did not include them. If you add them, make sure they also use the
# functions imported from ml_logic.py correctly.
