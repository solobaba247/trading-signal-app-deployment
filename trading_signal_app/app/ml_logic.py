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
    """
    Fetches data using the more robust yf.download() method.
    """
    print(f"--- Starting yfinance fetch for {symbol} using yf.download ---")
    try:
        # yf.download is generally more robust for historical data.
        df = yf.download(
            tickers=symbol,
            period=period,
            interval=interval,
            auto_adjust=False, # Important for consistency
            progress=False,    # Suppress progress bar in logs
            show_errors=False  # Suppress yfinance error messages
        )
        
        if df.empty:
            print(f"   ⚠️ yfinance.download returned no data for {symbol}")
            return None
        
        # Handle multi-level columns (when yf.download returns multi-index columns)
        if df.columns.nlevels > 1:
            # Flatten the multi-index columns
            df.columns = df.columns.get_level_values(0)
        
        # Ensure proper column names and select only OHLCV data
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Check if all required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"   ⚠️ Missing columns {missing_columns} for {symbol}")
            return None
        
        # Select only the required columns and drop rows with any NaN values
        df = df[required_columns].dropna()
        
        if not df.empty:
            print(f"   ✅ Success with yfinance.download for {symbol}! Got {len(df)} rows")
            return df
        else:
            # This case can happen if dropna() removes all rows
            print(f"   ⚠️ Data for {symbol} was fetched but became empty after cleaning.")
            return None
            
    except Exception as e:
        print(f"   ❌ yfinance.download fetch failed for {symbol}: {e}")
    
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

    print(f"Creating features for {len(df)} rows of data...")
    
    try:
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
        df['rsi_14'] = df.get('RSI_14', 50.0) # Use get() to handle missing columns
        df['price_vs_ema200'] = df['Close'] / df.get('EMA_200', df['Close'])
        df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
        
        # Handle datetime index for time-based features
        if hasattr(df.index, 'hour'):
            df['hour_of_day'] = df.index.hour
        else:
            df['hour_of_day'] = 12  # Default to noon
            
        if hasattr(df.index, 'dayofweek'):
            df['day_of_week'] = df.index.dayofweek
        else:
            df['day_of_week'] = 1  # Default to Tuesday
        
        df['risk_reward_ratio'] = 2.0 # Placeholder
        df['stop_loss_in_atrs'] = 1.5 # Placeholder
        df['entry_pos_in_channel_norm'] = 0.5 # Placeholder

        # Historical features
        for i in range(24):
            df[f'hist_close_channel_dev_t_minus_{i}'] = 0.0 # Placeholder
        
        # More time-based features
        if hasattr(df.index, 'month'):
            df['month'] = df.index.month
            df['quarter'] = df.index.quarter
            df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)
        else:
            df['month'] = 1
            df['quarter'] = 1
            df['is_weekend'] = 0
        
        # Interaction features
        df['volume_rsi_interaction'] = df['volume_ratio'] * df['rsi_14']
        df['breakout_strength'] = 0.0 # Placeholder
        df['channel_efficiency'] = 0.0 # Placeholder
        df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
        df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
        df['price_above_ema'] = (df['Close'] > df.get('EMA_200', df['Close'])).astype(int)
        df['high_risk_trade'] = 0 # Placeholder

        # Trade type will be set per-prediction
        df['trade_type_encoded'] = 0
        
        # Ensure all required columns exist, fill NaNs
        for col in feature_columns_list:
            if col not in df.columns:
                df[col] = 0 # Add missing columns with a default value
        
        # Return dataframe with only the required columns, properly ordered and cleaned
        # Use forward fill and then backward fill to handle NaN values
        final_df = df[feature_columns_list + ['Close']].fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        print(f"   ✅ Features created successfully. Shape: {final_df.shape}")
        return final_df
        
    except Exception as e:
        print(f"   ❌ Error creating features: {e}")
        return pd.DataFrame()

# --- PREDICTION LOGIC ---
def get_model_prediction(data, model, scaler, feature_columns):
    """Generates a prediction for a single asset."""
    
    # Validate inputs
    if data is None or data.empty:
        return {"error": "Cannot generate prediction, input data is missing."}
    
    if model is None:
        return {"error": "ML model is not loaded."}
    
    if scaler is None:
        return {"error": "Feature scaler is not loaded."}
    
    if feature_columns is None:
        return {"error": "Feature columns list is not loaded."}

    print(f"Generating prediction with {len(data)} rows of data...")
    
    try:
        # 1. Create features
        features_df = create_features_for_prediction(data, feature_columns)
        if features_df.empty:
            return {"error": "Could not create features for prediction."}

        latest_features = features_df.iloc[-1]
        last_price = latest_features['Close']
        
        print(f"   Latest price: {last_price}")

        # 2. Prepare for both BUY and SELL scenarios
        buy_features = latest_features.copy()
        buy_features['trade_type_encoded'] = 0
        sell_features = latest_features.copy()
        sell_features['trade_type_encoded'] = 1

        # Create DataFrames with proper column order
        buy_df = pd.DataFrame([buy_features])[feature_columns]
        sell_df = pd.DataFrame([sell_features])[feature_columns]
        
        print(f"   Feature vectors shape: {buy_df.shape}")

        # 3. Scale and Predict
        buy_prob = model.predict_proba(scaler.transform(buy_df))[0][1]
        sell_prob = model.predict_proba(scaler.transform(sell_df))[0][1]
        
        print(f"   Buy probability: {buy_prob:.3f}")
        print(f"   Sell probability: {sell_prob:.3f}")

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

        print(f"   Final signal: {signal_type} with confidence {confidence:.3f}")

        # 5. Format result
        return {
            "signal": signal_type, 
            "confidence": confidence, 
            "latest_price": last_price,
            "buy_prob": buy_prob, 
            "sell_prob": sell_prob,
            "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"   ❌ Prediction failed: {e}")
        return {"error": f"Prediction failed: {str(e)}"}
