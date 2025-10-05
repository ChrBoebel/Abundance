#!/usr/bin/env python3
"""
Minimal Flask test - no dependencies
"""
import os
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/')
def index():
    """Root endpoint."""
    return jsonify({"message": "App is running"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4290))
    print(f"🚀 Minimal Flask Test")
    print(f"📡 Server running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
