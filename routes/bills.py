"""
Bill Routes - Bill generation, retrieval, and management (PostgreSQL version)
"""

from flask import Blueprint, jsonify, request
from database import get_connection
from datetime import date

bills_bp = Blueprint("bills", __name__)


def calculate_bill(employee: dict, bill_date: str, notes: str = "") -> dict:
    """
    Calculate net salary based on attendance.
    """
    monthly_salary = employee["monthly_salary"]
    working_days   = employee["working_days"] or 30
    present_days   = employee["attendance_present"]
    absent_days    = employee["attendance_absent"]

    per_day        = monthly_salary / working_days
    deduction      = round(per_day * absent_days, 2)
    net_amount     = round(monthly_salary - deduction, 2)

    return {
        "employee_id":    employee["id"],
        "employee_name":  employee["name"],
        "designation":    employee["designation"],
        "email":          employee["email"],
        "monthly_salary": monthly_salary,
        "working_days":   working_days,
        "present_days":   present_days,
        "absent_days":    absent_days,
        "per_day_salary": round(per_day, 2),
        "deduction":      deduction,
        "net_amount":     net_amount,
        "bill_date":      bill_date,
        "notes":          notes,
    }


def bill_to_dict(row) -> dict:
    return dict(row) if row else None


@bills_bp.route("/generate", methods=["POST"])
def generate_bill():
    """
    Generate a bill for an employee.
    Expects JSON: { "employee_id": int, "company_id": int, "bill_date": "YYYY-MM-DD", "notes": "" }
    """
    data = request.get_json()
    emp_id     = data.get("employee_id")
    company_id = data.get("company_id")
    bill_date  = data.get("bill_date", str(date.today()))
    notes      = data.get("notes", "")

    if not emp_id or not company_id:
        return jsonify({"error": "employee_id and company_id are required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
    emp = cur.fetchone()
    if not emp:
        cur.close()
        conn.close()
        return jsonify({"error": "Employee not found"}), 404

    bill_data = calculate_bill(dict(emp), bill_date, notes)

    try:
        cur.execute("""
            INSERT INTO bill (employee_id, company_id, employee_name, amount, working_days, present_days,
                              absent_days, deduction, notes, bill_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PAID')
            RETURNING id, generated_at
        """, (
            bill_data["employee_id"],
            company_id,
            bill_data["employee_name"],
            bill_data["net_amount"],
            bill_data["working_days"],
            bill_data["present_days"],
            bill_data["absent_days"],
            bill_data["deduction"],
            notes,
            bill_date,
        ))
        result = cur.fetchone()
        bill_id = result["id"]
        generated_at = result["generated_at"]

        # --- Automatic Transaction Logging ---
        cur.execute("""
            INSERT INTO transaction_log (bill_id, amount, payment_method, transaction_ref)
            VALUES (%s, %s, %s, %s)
        """, (
            bill_id,
            bill_data["net_amount"],
            "System Automation",
            f"AUTO-{bill_id}-{int(generated_at.timestamp())}"
        ))

        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    conn.close()

    return jsonify({
        **bill_data,
        "bill_id": bill_id,
        "company_id": company_id,
        "generated_at": generated_at,
    }), 201


@bills_bp.route("/", methods=["GET"])
def get_all_bills():
    """Fetch all bills with employee details, optionally filtered by company."""
    company_id = request.args.get("company_id")
    conn = get_connection()
    cur = conn.cursor()
    
    query = """
        SELECT b.id, b.amount, b.working_days, b.present_days, b.absent_days,
               b.deduction, b.notes, b.bill_date, b.status, b.generated_at, b.company_id,
               e.id   AS employee_id,
               e.name AS employee_name,
               e.email,
               e.designation,
               e.monthly_salary
        FROM bill b
        JOIN employee e ON b.employee_id = e.id
    """
    params = []
    if company_id:
        query += " WHERE b.company_id = %s"
        params.append(company_id)
        
    query += " ORDER BY b.generated_at DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([bill_to_dict(r) for r in rows])


@bills_bp.route("/<int:bill_id>", methods=["GET"])
def get_bill(bill_id):
    """Fetch a single bill by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT b.*, e.name AS employee_name, e.email, e.designation, e.monthly_salary
        FROM bill b
        JOIN employee e ON b.employee_id = e.id
        WHERE b.id = %s
    """, (bill_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Bill not found"}), 404
    return jsonify(bill_to_dict(row))


@bills_bp.route("/employee/<int:emp_id>", methods=["GET"])
def get_employee_bills(emp_id):
    """Fetch all bills for a specific employee."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT b.*, e.name AS employee_name, e.email, e.designation, e.monthly_salary
        FROM bill b
        JOIN employee e ON b.employee_id = e.id
        WHERE b.employee_id = %s
        ORDER BY b.generated_at DESC
    """, (emp_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([bill_to_dict(r) for r in rows])


@bills_bp.route("/<int:bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    """Delete a single bill by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM bill WHERE id = %s", (bill_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Bill not found"}), 404

    cur.execute("DELETE FROM bill WHERE id = %s", (bill_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": f"Bill #{bill_id} deleted successfully"})


@bills_bp.route("/", methods=["DELETE"])
def clear_all_bills():
    """Delete all records from the bill table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM bill")
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "All bill history cleared successfully"})


@bills_bp.route("/pay/<int:bill_id>", methods=["POST"])
def pay_bill(bill_id):
    """
    Simulate a payment transaction.
    Atomically updates bill status and logs the transaction.
    """
    data = request.get_json()
    payment_method = data.get("payment_method", "Bank Transfer")
    transaction_ref = data.get("transaction_ref")

    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Fetch the bill to verify existence and amount
        cur.execute("SELECT amount, status FROM bill WHERE id = %s", (bill_id,))
        bill = cur.fetchone()
        
        if not bill:
            cur.close()
            conn.close()
            return jsonify({"error": "Bill not found"}), 404
        
        if bill["status"] == "PAID":
            cur.close()
            conn.close()
            return jsonify({"error": "Bill is already marked as PAID"}), 400

        # Update Bill Status
        cur.execute("UPDATE bill SET status = 'PAID' WHERE id = %s", (bill_id,))
        
        # Log the Transaction
        cur.execute("""
            INSERT INTO transaction_log (bill_id, amount, payment_method, transaction_ref)
            VALUES (%s, %s, %s, %s)
        """, (bill_id, bill["amount"], payment_method, transaction_ref))
        
        conn.commit()
        
        return jsonify({
            "message": f"Payment for Bill #{bill_id} processed successfully.",
            "status": "PAID",
            "transaction": {
                "bill_id": bill_id,
                "amount": bill["amount"],
                "payment_method": payment_method,
                "ref": transaction_ref
            }
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Transaction failed: {str(e)}"}), 500
    finally:
        cur.close()
        conn.close()
