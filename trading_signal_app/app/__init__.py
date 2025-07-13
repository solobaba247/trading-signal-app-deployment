# app/__init__.py

import os
from flask import Flask
import joblib
import pandas as pd

def create_app():
    app = Flask(__name__)

    # --- Configuration ---
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(APP_DIR)
    ML_MODELS_FOLDER = os.path.join(PROJECT_ROOT, 'ml_models/')

    # --- Define Asset Classes ---
    app.ASSET_CLASSES = {
        'forex': [
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'USDCAD=X',
            'AUDUSD=X', 'NZDUSD=X', 'EURJPY=X', 'GBPJPY=X', 'EURGBP=X'
        ],
        'crypto': [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            'SOL-USD', 'DOT-USD', 'AVAX-USD', 'MATIC-USD', 'LINK-USD'
        ],
        'stocks': [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
            'NVDA', 'META', 'NFLX', 'BABA', 'V'
        ],
        'indices': [
            '^GSPC', '^DJI', '^IXIC', '^RUT', '^VIX',
            '^FTSE', '^GDAXI', '^FCHI', '^N225', '^HSI'
        ]
    }

    # --- Load Model Artifacts ---
    print("\n--- Initializing Model Loading ---")
    try:
        model_path = os.path.join(ML_MODELS_FOLDER, 'model.joblib')
        scaler_path = os.path.join(ML_MODELS_FOLDER, 'scaler.joblib')
        features_path = os.path.join(ML_MODELS_FOLDER, 'feature_columns.csv')

        app.model = joblib.load(model_path)
        print("✅ SUCCESS: Model loaded.")

        app.scaler = joblib.load(scaler_path)
        print("✅ SUCCESS: Scaler loaded.")

        app.feature_columns = pd.read_csv(features_path)['feature_name'].tolist()
        print(f"✅ SUCCESS: Feature columns ({len(app.feature_columns)}) loaded.")

    except Exception as e:
        app.model = None
        app.scaler = None
        app.feature_columns = None
        print(f"🔥🔥🔥 CRITICAL ERROR loading ML artifacts: {e}")

    # Register routes
    with app.app_context():
        from . import routes

    return app
