"""
Employee Billing System - Flask Backend
Main application entry point
"""

import os
from dotenv import load_dotenv

# Load environment variables before importing routes
load_dotenv()

from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.employees import employees_bp
from routes.bills import bills_bp
from routes.voice import voice_bp
from routes.auth import auth_bp

def create_app():
    app = Flask(__name__)
    
    # Enable CORS for the entire application
    # This configuration specifically white-lists your Netlify domain and common methods/headers
    CORS(app, resources={r"/api/*": {
        "origins": ["https://aibillgeneratorapp.netlify.app", "http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }})

    # Initialize database
    init_db()

    # Register blueprints
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    app.register_blueprint(bills_bp, url_prefix="/api/bills")
    app.register_blueprint(voice_bp, url_prefix="/api/voice")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Employee Billing System is running"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
