#!/usr/bin/env python3
"""
Test Flask app - gradually adding components from full app.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Security Configuration
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

# Rate Limiter - Disabled
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],
    enabled=False
)

# Authentication Middleware
from flask import session, redirect, url_for, request

APP_PASSWORD = os.getenv('APP_PASSWORD', 'Aalen')

@app.before_request
def check_authentication():
    """Check if user is authenticated before allowing access."""
    public_routes = ['login', 'static', 'health']
    if request.endpoint in public_routes or session.get('authenticated'):
        return None
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login endpoint."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == APP_PASSWORD:
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return jsonify({"error": "Wrong password"}), 401
    return jsonify({"message": "Login page - use POST with password"})

@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.pop('authenticated', None)
    return redirect(url_for('login'))

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
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return jsonify({"message": "Test app is running", "authenticated": True})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4290))
    print(f"🚀 Test Flask App")
    print(f"📡 Server running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
