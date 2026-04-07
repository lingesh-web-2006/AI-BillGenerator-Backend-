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

SYSTEM_PROMPT = """\
You are an AI Billing Assistant.
You will receive a user's voice converted to text.
Your task is to extract the following details accurately, even if there are mistakes in spelling, pronunciation, or grammar:

1. Company Name
2. Employee Name (who is generating the bill)
3. Action (e.g., generate_bill, generate_bulk_bills, get_highest_salary, get_absent_list)

Rules:
- If the company does not exist in the database, return the company name anyway.
- Ignore irrelevant words like "will", "please", "create", etc.
- Return output only in JSON format.
- Always try to understand user intent correctly, even if words are pronounced slowly, fast, or with an accent.
- Format any spoken dates as "YYYY-MM" in a "month" property.
- Provide a brief confirmation message in a "message" property.

Example Input: "Generate Lingesh bill by Rajesh"
Example Output:
{{
  "company": "Lingesh Mobiles",
  "employee": "Rajesh",
  "action": "generate_bill",
  "message": "Generating bill for Rajesh at Lingesh Mobiles."
}}

Example Input: "Star Electronics bill Rajesh podu"
Example Output:
{{
  "company": "Star Electronics",
  "employee": "Rajesh",
  "action": "generate_bill",
  "message": "Generating bill for Rajesh at Star Electronics."
}}

Active Company Roster (for reference): {emp_names}
Registered Entities: {all_companies}

Return output in same structured JSON format every time.
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

    # Use fuzzywuzzy to find best match (WRatio partial string matching)
    match_result = process.extractOne(name, names)
    if not match_result: return None
    match, score = match_result[0], match_result[1]

    # Lowered threshold to 55 to be more forgiving of "squished" words (e.g. Lingeshwill -> Lingesh)
    if score >= 55:
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
    raw_text = data.get("text", "")
    company_id = data.get("company_id")

    # Resilience: Ensure raw_text is a string
    if isinstance(raw_text, dict):
        # Fallback if frontend sends nested object
        voice_text = raw_text.get("text", "").strip()
        if not company_id: company_id = raw_text.get("company_id")
    elif isinstance(raw_text, str):
        voice_text = raw_text.strip()
    else:
        voice_text = str(raw_text).strip()

    if not voice_text or not company_id:
        return jsonify({"error": "text and company_id are required"}), 400

    # Fetch current company name
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM company WHERE id = %s", (company_id,))
    co_row = cur.fetchone()
    company_name = co_row["name"] if co_row else "this company"

    # Fetch ALL company names for suggestibility
    cur.execute("SELECT name FROM company")
    all_companies = [r["name"] for r in cur.fetchall()]

    # Fetch employee names for THIS company
    cur.execute("SELECT name FROM employee WHERE company_id = %s", (company_id,))
    emp_names = [row["name"] for row in cur.fetchall()]
    cur.close()
    conn.close()

    if not client:
        return jsonify({"message": "The Voice AI is currently offline. Please set the GROQ_API_KEY environment variable in your Render dashboard and redeploy."}), 503

    try:
        prompt = SYSTEM_PROMPT.format(
            all_companies=", ".join(all_companies) if all_companies else "None registered",
            emp_names=", ".join(emp_names) if emp_names else "No employees found"
        )
    except KeyError as e:
        return jsonify({"error": f"Prompt template error: {e}"}), 500

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f'Today: {date.today()}. Active Company: {company_name}. User says: "{voice_text}"'}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"The AI returned an unexpected format. Please try rephrasing your command."}), 500
    except Exception as e:
        return jsonify({"error": f"AI service error: {str(e)}"}), 500

    action = parsed.get("action", "unknown")
    ai_message = parsed.get("message", "I've understood your command and I'm processing it now.")

    if action == "unknown":
        return jsonify({
            "message": ai_message, 
            "error": "I wasn't able to map that to a specific action. Could you try rephrasing?",
            "parsed": parsed
        }), 400

    if action == "generate_bill":
        return handle_generate_bill(parsed, voice_text, company_id, ai_message)
    elif action == "generate_bulk_bills":
        return handle_generate_bulk(parsed, voice_text, company_id, ai_message)
    elif action.startswith("get_"):
        return handle_stats_query(action, parsed, voice_text, company_id, ai_message)
    else:
        return jsonify({"message": f"Action '{action}' recognized but not yet fully implemented.", "parsed": parsed})


def handle_generate_bill(parsed, voice_text, company_id, ai_message):
    name = parsed.get("employee_name") or parsed.get("employee")
    if not name:
        return jsonify({"error": "Employee name missing"}), 400

    emp = fuzzy_find_employee(name, company_id)
    if not emp:
        return jsonify({"error": f"Employee '{name}' not found in this company."}), 404

    bill_date = parsed.get("month", str(date.today()))
    if len(bill_date) == 7 and "-" in bill_date: 
        bill_date += "-01"
    elif len(bill_date) != 10 or "-" not in bill_date:
        # Fallback if AI fails to return YYYY-MM or YYYY-MM-DD
        bill_date = str(date.today())

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
        "message": ai_message,
        "bill_id": bill_id,
        "company_id": company_id,
        "generated_at": generated_at,
        "parsed_command": parsed,
        "voice_text": voice_text,
        "type": "bill"
    }), 201


def handle_generate_bulk(parsed, voice_text, company_id, ai_message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employee WHERE company_id = %s", (company_id,))
    employees = cur.fetchall()
    
    results = []
    bill_date = parsed.get("month", str(date.today()))
    if len(bill_date) == 7 and "-" in bill_date: 
        bill_date += "-01"
    elif len(bill_date) != 10 or "-" not in bill_date:
        bill_date = str(date.today())
    
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
        "message": ai_message,
        "count": len(results),
        "type": "bulk",
        "parsed_command": parsed,
        "voice_text": voice_text
    })


def handle_stats_query(action, parsed, voice_text, company_id, ai_message):
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
        "message": ai_message,
        "type": res_type,
        "action": action,
        "parsed_command": parsed,
        "voice_text": voice_text
    })
