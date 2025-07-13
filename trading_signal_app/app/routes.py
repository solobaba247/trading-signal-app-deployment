# app/routes.py

from flask import current_app, render_template, request, jsonify
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# --- Placeholder functions (replace with your actual implementations) ---
def fetch_yfinance_data(symbol, period='90d', interval='1h'):
    """Fetch data from Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        if data.empty:
            return None
        return data
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def create_features_for_prediction(data):
    """Create features for prediction using pandas-ta"""
    try:
        import pandas_ta as ta
        
        # Add technical indicators using pandas-ta
        data.ta.sma(length=20, append=True)  # SMA_20
        data.ta.sma(length=50, append=True)  # SMA_50
        data.ta.rsi(length=14, append=True)  # RSI_14
        data.ta.macd(append=True)  # MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
        data.ta.bbands(length=20, append=True)  # BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        
        # Price-based features
        data['price_change'] = data['Close'].pct_change()
        data['volume_change'] = data['Volume'].pct_change()
        data['high_low_ratio'] = data['High'] / data['Low']
        data['close_open_ratio'] = data['Close'] / data['Open']
        
        # Remove NaN values
        data = data.dropna()
        
        return data
    except Exception as e:
        print(f"Error creating features: {e}")
        return pd.DataFrame()

def calculate_rsi(prices, window=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal).mean()
    return macd, macd_signal

def calculate_bollinger_bands(prices, window=20, num_std=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, lower_band

def calculate_stop_loss_value(symbol, entry_price, stop_loss_price):
    """Calculate stop loss value"""
    return abs(entry_price - stop_loss_price)

# --- Helper function for the scanner ---
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

        # Get the latest features
        latest_features = features_df.iloc[-1]
        last_price = latest_features['Close']

        # Prepare feature vector for prediction
        # This is a simplified version - adjust based on your actual feature columns
        feature_vector = []
        for col in feature_columns:
            if col in latest_features.index:
                feature_vector.append(latest_features[col])
            elif col == 'trade_type_encoded':
                feature_vector.append(0)  # Default to BUY scenario
            else:
                feature_vector.append(0)  # Default value for missing features

        # Prepare for both BUY and SELL scenarios
        buy_features = feature_vector.copy()
        sell_features = feature_vector.copy()
        
        # Assume trade_type_encoded is in the feature columns
        if 'trade_type_encoded' in feature_columns:
            trade_type_idx = feature_columns.index('trade_type_encoded')
            buy_features[trade_type_idx] = 0
            sell_features[trade_type_idx] = 1
        
        buy_df = pd.DataFrame([buy_features], columns=feature_columns)
        sell_df = pd.DataFrame([sell_features], columns=feature_columns)

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
            return None  # Don't return HOLD signals

        # 4. Format result
        entry_price_val = last_price
        sl_price_val = entry_price_val * (0.99 if signal_type == 'BUY' else 1.01)
        tp_price_val = entry_price_val * (1.02 if signal_type == 'BUY' else 0.98)

        return {
            "symbol": symbol, 
            "signal": signal_type, 
            "confidence": f"{confidence:.2%}",
            "entry_price": f"{entry_price_val:.5f}",
            "exit_price": f"{tp_price_val:.5f}",
            "stop_loss": f"{sl_price_val:.5f}",
            "stop_loss_value": calculate_stop_loss_value(symbol, entry_price_val, sl_price_val),
            "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"Error processing {symbol}: {e}")
        return None

# --- Routes ---
@current_app.route('/')
def index():
    """Home page - HTML interface"""
    return render_template('index.html')

@current_app.route('/api')
def api_info():
    """API information endpoint"""
    return jsonify({
        "message": "Trading Signal API",
        "endpoints": {
            "health_check": "/api/check_model_status",
            "market_scan": "/api/scan_market"
        }
    })

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
        
        return jsonify({
            "asset_type": asset_type,
            "timeframe": timeframe,
            "total_signals": len(scan_results),
            "results": scan_results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@current_app.route('/api/check_model_status')
def check_model_status():
    """Health check endpoint"""
    if current_app.model is not None and current_app.scaler is not None:
        return jsonify({
            "status": "ok", 
            "message": "Model and scaler are loaded.",
            "feature_count": len(current_app.feature_columns) if current_app.feature_columns else 0
        }), 200
    else:
        return jsonify({
            "status": "error", 
            "message": "Model and/or scaler failed to load."
        }), 503
