"""
Voice Command Routes - AI-powered voice command processing with Fuzzy Matching (PostgreSQL version)
"""

import os
import json
from groq import Groq
from flask import Blueprint, jsonify, request
from database import get_connection
from routes.bills import calculate_bill
from datetime import date
from fuzzywuzzy import process

voice_bp = Blueprint("voice", __name__)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = None

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    import warnings
    warnings.warn("GROQ_API_KEY is not set. Voice AI features will be disabled.")

SYSTEM_PROMPT = """You are an AI assistant for a Payroll & Employee Billing System.
Your job is to understand user commands and convert them into structured JSON actions.

---
🎯 IMPORTANT RULES:
1. Identify intent (action type).
2. Extract data (employee_name, month, bonus, etc.).
3. UNIVERSAL SCOPE: If user mentions "all employees", "everyone", or "entire company":
   - NEVER set "employee_name": "all employees".
   - Set "scope": "all" and "action": "generate_bulk_bills".
4. Return ONLY valid JSON (no explanation).
5. If unclear, return {"action": "unknown"}.
---

📌 SUPPORTED ACTIONS:
- generate_bill (single employee)
- generate_bulk_bills (scope: all)
- get_highest_salary
- get_lowest_attendance
- get_absent_list (min_absent_days)
- get_total_salary (month)
- get_avg_attendance
- get_total_deductions (month)
- get_bills_by_time (range/month)
- download_bill (employee_name)
- send_email (employee_name)

---
📊 EXAMPLES:
User: "Generate salary for everyone this month"
Response: {"action": "generate_bulk_bills", "scope": "all", "month": "2026-03"}

User: "Generate bill for Arun with 5000 bonus"
Response: {"action": "generate_bill", "employee_name": "Arun", "bonus": 5000}

User: "List employees with more than 3 absents"
Response: {"action": "get_absent_list", "min_absent_days": 3}
"""


def fuzzy_find_employee(name: str, company_id: int):
    """Find employee in a specific company using fuzzy matching."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM employee WHERE company_id = %s", (company_id,))
    employees = cur.fetchall()
    cur.close()
    conn.close()

    if not employees:
        return None

    name_map = {e["name"]: dict(e) for e in employees}
    names = list(name_map.keys())

    # Use fuzzywuzzy to find best match
    match_result = process.extractOne(name, names)
    if not match_result: return None
    match, score = match_result[0], match_result[1]

    if score >= 70:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM employee WHERE id = %s", (name_map[match]["id"],))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    
    return None


@voice_bp.route("/process", methods=["POST"])
def process_voice_command():
    data = request.get_json()
    voice_text = data.get("text", "").strip()
    company_id = data.get("company_id")

    if not voice_text or not company_id:
        return jsonify({"error": "text and company_id are required"}), 400

    # Fetch employee names for THIS company to give context to the AI
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM employee WHERE company_id = %s", (company_id,))
    emp_names = [row["name"] for row in cur.fetchall()]
    cur.close()
    conn.close()

    if not client:
        return jsonify({"error": "Voice AI features are currently disabled. Please contact the administrator to set the GROQ_API_KEY environment variable."}), 503

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + f"\n\nVALID EMPLOYEES: {', '.join(emp_names)}"},
                {"role": "user", "content": f'Today\'s date is {date.today()}. Parse this command: "{voice_text}"'}
            ],
            temperature=0.0,
            response_format={ "type": "json_object" }
        )
        parsed = json.loads(response.choices[0].message.content)
    except Exception as e:
        return jsonify({"error": f"AI Parsing failed: {str(e)}"}), 500

    action = parsed.get("action", "unknown")

    if action == "unknown":
        return jsonify({"error": "Command not understood", "parsed": parsed}), 400

    if action == "generate_bill":
        return handle_generate_bill(parsed, voice_text, company_id)
    elif action == "generate_bulk_bills":
        return handle_generate_bulk(parsed, voice_text, company_id)
    elif action.startswith("get_"):
        return handle_stats_query(action, parsed, voice_text, company_id)
    else:
        return jsonify({"message": f"Action '{action}' recognized but not yet fully implemented.", "parsed": parsed})


def handle_generate_bill(parsed, voice_text, company_id):
    name = parsed.get("employee_name")
    if not name:
        return jsonify({"error": "Employee name missing"}), 400

    emp = fuzzy_find_employee(name, company_id)
    if not emp:
        return jsonify({"error": f"Employee '{name}' not found in this company."}), 404

    bill_date = parsed.get("month", str(date.today()))
    if len(bill_date) == 7: bill_date += "-01"

    notes = parsed.get("notes", "")
    bonus = parsed.get("bonus", 0)

    bill_data = calculate_bill(emp, bill_date, notes)
    bill_data["net_amount"] += bonus
    bill_data["notes"] = f"{notes} (Includes bonus: {bonus})" if bonus else notes

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO bill (employee_id, company_id, employee_name, amount, working_days, present_days,
                              absent_days, deduction, notes, bill_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PAID')
            RETURNING id, generated_at
        """, (emp["id"], company_id, emp["name"], bill_data["net_amount"], bill_data["working_days"],
              bill_data["present_days"], bill_data["absent_days"], 
              bill_data["deduction"], bill_data["notes"], bill_date))
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
            "Voice Command Automation",
            f"VOICE-{bill_id}-{int(generated_at.timestamp())}"
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
        "parsed_command": parsed,
        "voice_text": voice_text,
        "type": "bill"
    }), 201


def handle_generate_bulk(parsed, voice_text, company_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employee WHERE company_id = %s", (company_id,))
    employees = cur.fetchall()
    
    results = []
    bill_date = parsed.get("month", str(date.today()))
    if len(bill_date) == 7: bill_date += "-01"
    
    bonus = parsed.get("bonus", 0)

    try:
        for emp in employees:
            bill_data = calculate_bill(dict(emp), bill_date, "")
            bill_data["net_amount"] += bonus
            
            cur.execute("""
                INSERT INTO bill (employee_id, company_id, employee_name, amount, working_days, present_days,
                                  absent_days, deduction, notes, bill_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PAID')
                RETURNING id, generated_at
            """, (emp["id"], company_id, emp["name"], bill_data["net_amount"], bill_data["working_days"],
                  bill_data["present_days"], bill_data["absent_days"], 
                  bill_data["deduction"], f"Bulk generation. Bonus: {bonus}", bill_date))
            
            res = cur.fetchone()
            bill_id = res["id"]
            generated_at = res["generated_at"]

            # --- Automatic Transaction Logging ---
            cur.execute("""
                INSERT INTO transaction_log (bill_id, amount, payment_method, transaction_ref)
                VALUES (%s, %s, %s, %s)
            """, (
                bill_id,
                bill_data["net_amount"],
                "Voice Bulk Automation",
                f"VOICE-BULK-{bill_id}-{int(generated_at.timestamp())}"
            ))

            results.append(bill_data)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    conn.close()

    return jsonify({
        "message": f"Successfully generated bills for {len(results)} employees.",
        "count": len(results),
        "type": "bulk",
        "parsed_command": parsed,
        "voice_text": voice_text
    })


def handle_stats_query(action, parsed, voice_text, company_id):
    conn = get_connection()
    cur = conn.cursor()
    data = None
    res_type = "stat"

    if action == "get_highest_salary":
        cur.execute("SELECT * FROM employee WHERE company_id = %s ORDER BY monthly_salary DESC LIMIT 1", (company_id,))
        row = cur.fetchone()
        data = dict(row) if row else None
    
    elif action == "get_lowest_attendance":
        cur.execute("SELECT * FROM employee WHERE company_id = %s ORDER BY (attendance_present * 1.0 / working_days) ASC LIMIT 1", (company_id,))
        row = cur.fetchone()
        data = dict(row) if row else None

    elif action == "get_absent_list":
        min_days = parsed.get("min_absent_days", 0)
        cur.execute("SELECT * FROM employee WHERE company_id = %s AND attendance_absent >= %s", (company_id, min_days))
        rows = cur.fetchall()
        data = [dict(r) for r in rows]
        res_type = "list"

    elif action == "get_total_salary":
        month = parsed.get("month", "")
        cur.execute("SELECT SUM(amount) as total FROM bill WHERE company_id = %s AND CAST(bill_date AS TEXT) LIKE %s", (company_id, f"{month}%",))
        row = cur.fetchone()
        data = {"total": float(row["total"] or 0), "month": month}

    cur.close()
    conn.close()

    return jsonify({
        "data": data,
        "type": res_type,
        "action": action,
        "parsed_command": parsed,
        "voice_text": voice_text
    })
