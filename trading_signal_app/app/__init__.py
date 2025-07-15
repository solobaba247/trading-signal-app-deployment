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
    ML_MODELS_FOLDER = os.path.join(PROJECT_ROOT, 'ml_models')

    # --- Define Asset Classes (Expanded) ---
    app.ASSET_CLASSES = {
        'forex': [
            # Majors
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'USDCAD=X', 'AUDUSD=X', 'NZDUSD=X',
            # Minors / Crosses
            'EURJPY=X', 'GBPJPY=X', 'EURGBP=X', 'AUDCAD=X', 'AUDJPY=X', 'AUDNZD=X', 'CADCHF=X', 
            'CADJPY=X', 'CHFJPY=X', 'EURAUD=X', 'EURCAD=X', 'EURCHF=X', 'EURNZD=X', 'GBPAUD=X', 
            'GBPCAD=X', 'GBPCHF=X', 'GBPNZD=X', 'NZDCAD=X', 'NZDJPY=X',
            # Exotics
            'USDZAR=X', 'USDMXN=X', 'USDTRY=X', 'USDSGD=X', 'USDNOK=X', 'USDSEK=X', 'USDHKD=X'
        ],
        'crypto': [
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD', 'SOL-USD', 'DOGE-USD',
            'DOT-USD', 'AVAX-USD', 'MATIC-USD', 'LINK-USD', 'LTC-USD', 'TRX-USD', 'SHIB-USD'
        ],
        'stocks': [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX', 
            'JPM', 'V', 'PYPL', 'DIS', 'BABA', 'BA'
        ],
        'indices': [
            '^GSPC', '^DJI', '^IXIC', '^RUT', '^VIX', '^FTSE', '^GDAXI', 
            '^FCHI', '^N225', '^HSI', '^STOXX50E', 'EURONEXT:^N100'
        ]
    }

    # --- Load Model Artifacts ---
    print("\n--- Initializing Model Loading ---")
    print(f"APP_DIR: {APP_DIR}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"ML_MODELS_FOLDER: {ML_MODELS_FOLDER}")
    
    # Check if ml_models directory exists
    if not os.path.exists(ML_MODELS_FOLDER):
        print(f"🔥 CRITICAL ERROR: ML models directory does not exist at {ML_MODELS_FOLDER}")
        print("Please ensure the 'ml_models' folder exists in your project root with the required files:")
        print("- model.joblib")
        print("- scaler.joblib") 
        print("- feature_columns.csv")
        app.model = None
        app.scaler = None
        app.feature_columns = None
    else:
        print(f"✅ ML models directory exists at {ML_MODELS_FOLDER}")
        
        # Define file paths
        model_path = os.path.join(ML_MODELS_FOLDER, 'model.joblib')
        scaler_path = os.path.join(ML_MODELS_FOLDER, 'scaler.joblib')
        features_path = os.path.join(ML_MODELS_FOLDER, 'feature_columns.csv')
        
        # Check if all required files exist
        required_files = {
            'model.joblib': model_path,
            'scaler.joblib': scaler_path,
            'feature_columns.csv': features_path
        }
        
        missing_files = []
        for filename, filepath in required_files.items():
            if not os.path.exists(filepath):
                missing_files.append(filename)
                print(f"❌ Missing file: {filename} at {filepath}")
            else:
                print(f"✅ Found file: {filename} at {filepath}")
        
        if missing_files:
            print(f"🔥 CRITICAL ERROR: Missing required files: {missing_files}")
            app.model = None
            app.scaler = None
            app.feature_columns = None
        else:
            # Load each file with proper error handling
            try:
                print(f"Loading model from: {model_path}")
                app.model = joblib.load(model_path)
                print("✅ SUCCESS: Model loaded.")
            except Exception as e:
                print(f"❌ ERROR loading model: {e}")
                app.model = None

            try:
                print(f"Loading scaler from: {scaler_path}")
                app.scaler = joblib.load(scaler_path)
                print("✅ SUCCESS: Scaler loaded.")
            except Exception as e:
                print(f"❌ ERROR loading scaler: {e}")
                app.scaler = None

            try:
                print(f"Loading feature columns from: {features_path}")
                feature_df = pd.read_csv(features_path)
                if 'feature_name' in feature_df.columns:
                    app.feature_columns = feature_df['feature_name'].tolist()
                    print(f"✅ SUCCESS: Feature columns ({len(app.feature_columns)}) loaded.")
                else:
                    print("❌ ERROR: 'feature_name' column not found in feature_columns.csv")
                    print(f"Available columns: {list(feature_df.columns)}")
                    app.feature_columns = None
            except Exception as e:
                print(f"❌ ERROR loading feature columns: {e}")
                app.feature_columns = None

    # Print final status
    print("\n--- Model Loading Summary ---")
    print(f"Model loaded: {app.model is not None}")
    print(f"Scaler loaded: {app.scaler is not None}")
    print(f"Feature columns loaded: {app.feature_columns is not None}")
    if app.feature_columns:
        print(f"Number of features: {len(app.feature_columns)}")
    print("--- End Model Loading ---\n")

    # Register routes
    with app.app_context():
        from . import routes

    return app
