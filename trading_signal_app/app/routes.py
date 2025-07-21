# app/routes.py

from flask import current_app as app, jsonify, request
# ... other imports

@app.route('/')
def index():
    # ...

# --- ADD THIS ROUTE ---
@app.route('/api/health')
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "healthy"}), 200
# --- END OF ADDITION ---

@app.route('/assets')
def get_assets():
    # ...
