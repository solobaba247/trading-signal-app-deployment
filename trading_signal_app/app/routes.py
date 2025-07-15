# app/routes.py

from flask import current_app as app, jsonify, request
from .ml_logic import fetch_yfinance_data, get_model_prediction
import asyncio

@app.route('/')
def index():
    return jsonify({
        "message": "Trading ML API is running",
        "model_loaded": app.model is not None,
        "scaler_loaded": app.scaler is not None,
        "features_loaded": app.feature_columns is not None,
        "feature_count": len(app.feature_columns) if app.feature_columns else 0
    })

@app.route('/assets')
def get_assets():
    """Returns all available assets grouped by category."""
    return jsonify(app.ASSET_CLASSES)

@app.route('/predict/<symbol>')
def predict(symbol):
    """Generate prediction for a specific symbol."""
    
    # Check if models are loaded
    if not all([app.model, app.scaler, app.feature_columns]):
        return jsonify({
            "error": "ML models not properly loaded",
            "model_loaded": app.model is not None,
            "scaler_loaded": app.scaler is not None,
            "features_loaded": app.feature_columns is not None
        }), 500
    
    # Get timeframe from query parameters (default to 1h)
    timeframe = request.args.get('timeframe', '1h')
    
    try:
        # Fetch data
        data = fetch_yfinance_data(symbol, period='90d', interval=timeframe)
        
        if data is None:
            return jsonify({
                "error": f"Could not fetch data for symbol {symbol}",
                "symbol": symbol
            }), 400
        
        # Generate prediction
        prediction = get_model_prediction(data, app.model, app.scaler, app.feature_columns)
        
        # Add symbol to response
        prediction['symbol'] = symbol
        prediction['timeframe'] = timeframe
        
        return jsonify(prediction)
        
    except Exception as e:
        return jsonify({
            "error": f"Prediction failed: {str(e)}",
            "symbol": symbol
        }), 500

@app.route('/predict/batch', methods=['POST'])
def predict_batch():
    """Generate predictions for multiple symbols."""
    
    if not all([app.model, app.scaler, app.feature_columns]):
        return jsonify({
            "error": "ML models not properly loaded"
        }), 500
    
    data = request.get_json()
    if not data or 'symbols' not in data:
        return jsonify({
            "error": "Please provide 'symbols' list in request body"
        }), 400
    
    symbols = data['symbols']
    timeframe = data.get('timeframe', '1h')
    
    results = {}
    
    for symbol in symbols:
        try:
            market_data = fetch_yfinance_data(symbol, period='90d', interval=timeframe)
            if market_data is not None:
                prediction = get_model_prediction(market_data, app.model, app.scaler, app.feature_columns)
                prediction['symbol'] = symbol
                prediction['timeframe'] = timeframe
                results[symbol] = prediction
            else:
                results[symbol] = {
                    "error": f"Could not fetch data for {symbol}",
                    "symbol": symbol
                }
        except Exception as e:
            results[symbol] = {
                "error": f"Prediction failed: {str(e)}",
                "symbol": symbol
            }
    
    return jsonify(results)
