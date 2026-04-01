"""
Authentication Routes - Simple login for the billing system
"""

from flask import Blueprint, jsonify, request

auth_bp = Blueprint("auth", __name__)

# Hardcoded credentials as requested by user
USER_CREDENTIALS = {
    "username": "employee",
    "password": "employee123"
}

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username == USER_CREDENTIALS["username"] and password == USER_CREDENTIALS["password"]:
        # Return a simple mock token for the frontend to store
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "token": "auth_token_employee_123"
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Invalid username or password"
    }), 401
