"""
Employee Routes - CRUD operations for employees (PostgreSQL version)
"""

from flask import Blueprint, jsonify, request
from database import get_connection

employees_bp = Blueprint("employees", __name__)


def employee_to_dict(row):
    """Ensure row is a dict (consistent with RealDictCursor)."""
    return dict(row) if row else None


@employees_bp.route("/", methods=["GET"])
def get_all_employees():
    """Fetch all employees with their attendance details."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, email, designation, monthly_salary,
               attendance_present, attendance_absent, working_days, created_at
        FROM employee
        ORDER BY name ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([employee_to_dict(r) for r in rows])


@employees_bp.route("/<int:emp_id>", methods=["GET"])
def get_employee(emp_id):
    """Fetch a single employee by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM employee WHERE id = %s", (emp_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Employee not found"}), 404
    return jsonify(employee_to_dict(row))


@employees_bp.route("/", methods=["POST"])
def create_employee():
    """Add a new employee."""
    data = request.get_json()
    required = ["name", "email", "monthly_salary"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields: name, email, monthly_salary"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO employee (name, email, designation, monthly_salary,
                                  attendance_present, attendance_absent, working_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data["name"],
            data["email"],
            data.get("designation", "Employee"),
            data["monthly_salary"],
            data.get("attendance_present", 0),
            data.get("attendance_absent", 0),
            data.get("working_days", 30),
        ))
        new_id = cur.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 400

    cur.execute("SELECT * FROM employee WHERE id = %s", (new_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(employee_to_dict(row)), 201


@employees_bp.route("/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    """Update employee details."""
    data = request.get_json()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Employee not found"}), 404

    cur.execute("""
        UPDATE employee SET
            name               = %s,
            email              = %s,
            designation        = %s,
            monthly_salary     = %s,
            attendance_present = %s,
            attendance_absent  = %s,
            working_days       = %s
        WHERE id = %s
    """, (
        data.get("name", existing["name"]),
        data.get("email", existing["email"]),
        data.get("designation", existing["designation"]),
        data.get("monthly_salary", existing["monthly_salary"]),
        data.get("attendance_present", existing["attendance_present"]),
        data.get("attendance_absent", existing["attendance_absent"]),
        data.get("working_days", existing["working_days"]),
        emp_id,
    ))
    conn.commit()

    cur.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(employee_to_dict(row))


@employees_bp.route("/<int:emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    """Delete an employee record."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM employee WHERE id = %s", (emp_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Employee not found"}), 404

    cur.execute("DELETE FROM employee WHERE id = %s", (emp_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": f"Employee {emp_id} deleted successfully"})
