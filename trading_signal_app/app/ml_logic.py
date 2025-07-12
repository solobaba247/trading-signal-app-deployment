# app/ml_logic.py

import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
import warnings
import asyncio
import os

warnings.filterwarnings('ignore')

# --- DATA FETCHING ---
def fetch_yfinance_data(symbol, period='90d', interval='1h'):
    """Fetches data directly using the yfinance library."""
    print(f"--- Starting yfinance fetch for {symbol} ---")
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            print(f"   ⚠️ yfinance returned no data for {symbol}")
            return None
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        if not df.empty:
            print(f"   ✅ Success with yfinance for {symbol}!")
            return df
    except Exception as e:
        print(f"   ❌ yfinance fetch failed for {symbol}: {e}")
    return None

async def fetch_data_for_symbol_async(symbol, timeframe):
    """Asynchronously runs the synchronous yfinance function in a separate thread."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None, fetch_yfinance_data, symbol, '90d', timeframe
    )
    return data

# --- FEATURE ENGINEERING ---
def create_features_for_prediction(data, feature_columns_list):
    """Creates all necessary features for the model from raw price data."""
    df = data.copy()
    if df.empty:
        return pd.DataFrame()

    # --- Standard Technical Indicators ---
    df.ta.rsi(length=14, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.atr(length=14, append=True)
    
    # --- Feature Creation (Matching feature_columns.csv) ---
    df['channel_slope'] = 0.0 # Placeholder
    df['channel_width_atr'] = 1.0 # Placeholder
    df['bars_outside_zone'] = 0 # Placeholder
    df['breakout_distance_norm'] = 0.0 # Placeholder
    df['breakout_candle_body_ratio'] = 0.5 # Placeholder
    df['rsi_14'] = df['RSI_14']
    df['price_vs_ema200'] = df['Close'] / df['EMA_200']
    df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['hour_of_day'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['risk_reward_ratio'] = 2.0 # Placeholder
    df['stop_loss_in_atrs'] = 1.5 # Placeholder
    df['entry_pos_in_channel_norm'] = 0.5 # Placeholder

    for i in range(24):
        df[f'hist_close_channel_dev_t_minus_{i}'] = 0.0 # Placeholder
    
    df['month'] = df.index.month
    df['quarter'] = df.index.quarter
    df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)
    
    df['volume_rsi_interaction'] = df['volume_ratio'] * df['rsi_14']
    df['breakout_strength'] = 0.0 # Placeholder
    df['channel_efficiency'] = 0.0 # Placeholder
    df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
    df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
    df['price_above_ema'] = (df['Close'] > df['EMA_200']).astype(int)
    df['high_risk_trade'] = 0 # Placeholder

    # Ensure all required columns exist, fill NaNs
    df['trade_type_encoded'] = 0 # This will be set per-prediction
    
    for col in feature_columns_list:
        if col not in df.columns:
            df[col] = 0 # Add missing columns with a default value
    
    # Return dataframe with only the required columns, properly ordered and cleaned
    final_df = df[feature_columns_list + ['Close']].fillna(method='ffill').fillna(0)
    return final_df

# --- PREDICTION LOGIC ---
def get_model_prediction(data, model, scaler, feature_columns):
    """Generates a prediction for a single asset."""
    if data is None or data.empty:
        return {"error": "Cannot generate prediction, input data is missing."}

    # 1. Create features
    features_df = create_features_for_prediction(data, feature_columns)
    if features_df.empty:
        return {"error": "Could not create features for prediction."}

    latest_features = features_df.iloc[-1]
    last_price = latest_features['Close']

    # 2. Prepare for both BUY and SELL scenarios
    buy_features = latest_features.copy()
    buy_features['trade_type_encoded'] = 0
    sell_features = latest_features.copy()
    sell_features['trade_type_encoded'] = 1

    buy_df = pd.DataFrame([buy_features])[feature_columns]
    sell_df = pd.DataFrame([sell_features])[feature_columns]

    # 3. Scale and Predict
    buy_prob = model.predict_proba(scaler.transform(buy_df))[0][1]
    sell_prob = model.predict_proba(scaler.transform(sell_df))[0][1]

    # 4. Determine Signal
    confidence_threshold = 0.55
    signal_type = "HOLD"
    confidence = 0.0

    if buy_prob > sell_prob and buy_prob > confidence_threshold:
        signal_type = "BUY"
        confidence = buy_prob
    elif sell_prob > buy_prob and sell_prob > confidence_threshold:
        signal_type = "SELL"
        confidence = sell_prob

    # 6. Format result
    return {
        "signal": signal_type, "confidence": confidence, "latest_price": last_price,
        "buy_prob": buy_prob, "sell_prob": sell_prob,
        "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
