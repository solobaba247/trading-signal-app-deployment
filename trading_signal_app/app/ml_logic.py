# --- Main Prediction Logic (This was the missing function) ---
def get_model_prediction(data, model, scaler, feature_columns):
    """
    Generates a prediction for a single asset using the loaded model.
    This is used by the single asset signal generator.
    """
    if data.empty:
        return {"error": "Feature calculation resulted in empty data."}

    # 1. Create features
    features_df = create_features_for_prediction(data)
    if features_df is None or features_df.empty:
        return {"error": "Could not create features for prediction."}

    latest_features = features_df.iloc[-1]
    last_price = latest_features['Close']

    # 2. Prepare data for both BUY and SELL scenarios
    buy_features = latest_features.copy()
    buy_features['trade_type_encoded'] = 0  # 0 for BUY
    sell_features = latest_features.copy()
    sell_features['trade_type_encoded'] = 1 # 1 for SELL

    buy_df = pd.DataFrame([buy_features])[feature_columns]
    sell_df = pd.DataFrame([sell_features])[feature_columns]

    # 3. Scale the features
    buy_df_scaled = scaler.transform(buy_df)
    sell_df_scaled = scaler.transform(sell_df)

    # 4. Get prediction probabilities
    buy_prob = model.predict_proba(buy_df_scaled)[0][1]
    sell_prob = model.predict_proba(sell_df_scaled)[0][1]

    # 5. Determine the signal
    confidence_threshold = 0.55 # Same as in the scanner
    signal_type = "HOLD"
    confidence = 0.0

    if buy_prob > sell_prob and buy_prob > confidence_threshold:
        signal_type = "BUY"
        confidence = buy_prob
    elif sell_prob > buy_prob and sell_prob > confidence_threshold:
        signal_type = "SELL"
        confidence = sell_prob

    # 6. Format the result
    return {
        "signal": signal_type,
        "confidence": confidence,
        "latest_price": last_price,
        "buy_prob": buy_prob,
        "sell_prob": sell_prob,
        "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def create_features_for_prediction(data):
    """
    Creates all necessary features for the model from raw price data.
    NOTE: This is a placeholder. The original file prompt did not include this function's
    content, but it's required. We will create a basic version.
    This function needs to create ALL the columns listed in feature_columns.csv.
    """
    df = data.copy()
    df.ta.rsi(length=14, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.atr(length=14, append=True)
    
    # --- Basic Features (Add more as needed to match your model) ---
    df['channel_slope'] = 0.0
    df['channel_width_atr'] = 1.0
    df['bars_outside_zone'] = 0
    df['breakout_distance_norm'] = 0.0
    df['breakout_candle_body_ratio'] = 0.5
    df['rsi_14'] = df['RSI_14']
    df['price_vs_ema200'] = df['Close'] / df['EMA_200']
    df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['hour_of_day'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['risk_reward_ratio'] = 2.0
    df['stop_loss_in_atrs'] = 1.5
    df['entry_pos_in_channel_norm'] = 0.5

    # Create historical channel deviation features (dummy values)
    for i in range(24):
        df[f'hist_close_channel_dev_t_minus_{i}'] = 0.0
    
    df['month'] = df.index.month
    df['quarter'] = df.index.quarter
    df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)
    df['trade_type_encoded'] = 0 # This will be set per-prediction
    
    # Interaction / derived features (dummy values)
    df['volume_rsi_interaction'] = df['volume_ratio'] * df['rsi_14']
    df['breakout_strength'] = 0.0
    df['channel_efficiency'] = 0.0
    df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
    df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
    df['price_above_ema'] = (df['Close'] > df['EMA_200']).astype(int)
    df['high_risk_trade'] = 0

    # Ensure all columns exist, fill NaNs
    # We add this logic because some calculations might produce NaNs at the start
    all_feature_cols = pd.read_csv('trading_signal_app/ml_models/feature_columns.csv')['feature_name'].tolist()
    for col in all_feature_cols:
        if col not in df.columns:
            df[col] = 0 # Add missing columns with a default value
    
    # Keep only the feature columns and the 'Close' price for context
    df = df[all_feature_cols + ['Close']].fillna(method='ffill').fillna(0)
    
    return df
