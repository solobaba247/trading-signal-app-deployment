# app/ml_logic.py

import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
import warnings
import asyncio
import os
import requests # Added for API fallbacks

warnings.filterwarnings('ignore')

# --- DATA FETCHING FALLBACKS & ORCHESTRATION ---

def _map_symbol_to_binance_crypto(symbol: str) -> str:
    """Maps a yfinance crypto symbol (e.g., BTC-USD) to a Binance symbol (e.g., BTCUSDT)."""
    return symbol.replace('-USD', 'USDT').upper()

def _map_symbol_to_binance_forex(symbol: str) -> str:
    """Maps a yfinance forex symbol (e.g., EURUSD=X) to a Binance symbol (e.g., EURUSDT)."""
    clean_symbol = symbol.replace('=X', '').upper()
    # Handle USD-based pairs to map to USDT
    if 'USD' in clean_symbol:
        return clean_symbol.replace('USD', 'USDT')
    return clean_symbol

def _fetch_binance_fallback(binance_symbol: str, interval: str = '1h'):
    """
    Fetches historical OHLCV data from Binance as a fallback.
    Binance is used because its API provides volume data, which is crucial for our model features.
    """
    # Map yfinance interval to Binance interval
    interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1h', '4h': '4h', '1d': '1d'}
    binance_interval = interval_map.get(interval)
    if not binance_interval:
        print(f"   - Binance Fallback: Unsupported interval '{interval}' for {binance_symbol}")
        return None

    # Binance API has a limit of 1000 candles per request. This is usually sufficient.
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={binance_interval}&limit=1000"
    
    response = requests.get(url, timeout=10)
    response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
    data = response.json()
    
    if not data:
        return None
        
    # Process data into a DataFrame matching yfinance format
    df = pd.DataFrame(data, columns=[
        'Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_time', 
        'Quote_asset_volume', 'Number_of_trades', 'Taker_buy_base_asset_volume', 
        'Taker_buy_quote_asset_volume', 'Ignore'
    ])
    
    df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
    df.set_index('Timestamp', inplace=True)
    df = df.astype(float)
    
    # Ensure column names match the required format (Capitalized)
    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    
    return df

def _fetch_yfinance_primary(symbol: str, period: str = '90d', interval: str = '1h'):
    """Primary data fetch function using the yfinance library."""
    try:
        # yfinance can be inconsistent with some tickers, so we handle this.
        if "EURONEXT:" in symbol:
            symbol = symbol.split(":")[1] # yfinance may not need the exchange prefix
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            return None # The orchestrator will log the failure
        
        df.columns = df.columns.str.title()
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        
        return df if not df.empty else None
    except Exception as e:
        # Don't print the full stack trace for common yfinance errors
        # print(f"   - yfinance internal error for {symbol}: {e}")
        return None

# --- PUBLIC DATA FETCHING FUNCTION ---

def fetch_yfinance_data(symbol, period='90d', interval='1h'):
    """
    Fetches historical data, starting with yfinance and using fallbacks for specific asset classes.
    A fallback to the Binance API is implemented for crypto and forex assets.
    """
    print(f"--- Starting data fetch for {symbol} ({interval}) ---")
    
    # 1. Try yfinance first (primary source for all assets)
    data = _fetch_yfinance_primary(symbol, period, interval)
    if data is not None and not data.empty:
        print(f"   ✅ Success with yfinance for {symbol}!")
        return data
        
    print(f"   ⚠️ yfinance primary fetch failed for {symbol}. Attempting fallbacks...")
    
    binance_symbol = None
    asset_type = "unknown"

    # 2. Determine Fallback Strategy
    if "-USD" in symbol:
        asset_type = "crypto"
        binance_symbol = _map_symbol_to_binance_crypto(symbol)
    elif "=X" in symbol:
        asset_type = "forex"
        binance_symbol = _map_symbol_to_binance_forex(symbol)

    # 3. Execute Fallback if applicable
    if binance_symbol:
        print(f"   -> Detected {asset_type} asset. Attempting Binance fallback with symbol {binance_symbol}...")
        try:
            data = _fetch_binance_fallback(binance_symbol, interval)
            if data is not None and not data.empty:
                print(f"   ✅ Success with Binance fallback for {symbol}!")
                return data
            else:
                print(f"   - Binance fallback returned no data for {binance_symbol}.")
        except Exception as e:
            print(f"   - Binance fallback request failed for {binance_symbol}: {e}")
    else:
        print(f"   - No specific fallback available for asset type of {symbol}.")
            
    # 4. If all sources and fallbacks fail
    print(f"   ❌ All data sources failed for {symbol}.")
    return None

async def fetch_data_for_symbol_async(symbol, timeframe):
    """Asynchronously runs the synchronous data fetch orchestrator in a separate thread."""
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
    # Use forward fill and then backward fill to handle NaN values
    final_df = df[feature_columns_list + ['Close']].fillna(method='ffill').fillna(method='bfill').fillna(0)
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
    try:
        buy_prob = model.predict_proba(scaler.transform(buy_df))[0][1]
        sell_prob = model.predict_proba(scaler.transform(sell_df))[0][1]
    except Exception as e:
        return {"error": f"Prediction failed: {str(e)}"}

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

    # 5. Format result
    return {
        "signal": signal_type, 
        "confidence": confidence, 
        "latest_price": last_price,
        "buy_prob": buy_prob, 
        "sell_prob": sell_prob,
        "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }
