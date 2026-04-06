"""
Company Routes - CRUD operations for companies
"""

from flask import Blueprint, jsonify, request
from database import get_connection

companies_bp = Blueprint("companies", __name__)


def company_to_dict(row):
    return dict(row) if row else None


@companies_bp.route("/", methods=["GET"])
def get_all_companies():
    """Fetch all companies."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM company ORDER BY name ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([company_to_dict(r) for r in rows])


@companies_bp.route("/<int:co_id>", methods=["GET"])
def get_company(co_id):
    """Fetch a single company by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM company WHERE id = %s", (co_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Company not found"}), 404
    return jsonify(company_to_dict(row))


@companies_bp.route("/", methods=["POST"])
def create_company():
    """Add a new company."""
    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Company name is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO company (name, logo_url, address, gst_number, phone, template_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data["name"],
            data.get("logo_url", ""),
            data.get("address", ""),
            data.get("gst_number", ""),
            data.get("phone", ""),
            data.get("template_name", "Modern"),
        ))
        new_id = cur.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 400

    cur.execute("SELECT * FROM company WHERE id = %s", (new_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(company_to_dict(row)), 201


@companies_bp.route("/<int:co_id>", methods=["PUT"])
def update_company(co_id):
    """Update company details."""
    data = request.get_json()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM company WHERE id = %s", (co_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Company not found"}), 404

    try:
        cur.execute("""
            UPDATE company SET
                name = %s, logo_url = %s, address = %s, 
                gst_number = %s, phone = %s, template_name = %s
            WHERE id = %s
        """, (
            data.get("name"),
            data.get("logo_url"),
            data.get("address"),
            data.get("gst_number"),
            data.get("phone"),
            data.get("template_name"),
            co_id,
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 400

    cur.execute("SELECT * FROM company WHERE id = %s", (co_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(company_to_dict(row))


@companies_bp.route("/<int:co_id>", methods=["DELETE"])
def delete_company(co_id):
    """Delete a company."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM company WHERE id = %s", (co_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Company not found"}), 404

    cur.execute("DELETE FROM company WHERE id = %s", (co_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": f"Company {co_id} deleted successfully"})
