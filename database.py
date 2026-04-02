"""
Database module - PostgreSQL setup, schema, and connection management
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Load environment variables
DB_URL = os.getenv("DB_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "employee_billing")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

def get_connection():
    """Return a PostgreSQL connection."""
    # Priority 1: External Connection String (for Render/Heroku)
    db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    
    if db_url:
        # Append sslmode if not present in the URL
        if "sslmode=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            # Default to 'require' for remote URLs unless it's localhost
            mode = "require" if "localhost" not in db_url and "127.0.0.1" not in db_url else "disable"
            db_url += f"{separator}sslmode={mode}"
        
        try:
            return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"[DB] Error connecting via DB_URL: {e}")
            # If URL fails, fall back to individual parameters below
    
    # Priority 2: Individual Parameters
    ssl_mode = os.getenv("DB_SSL", "require")
    if DB_HOST in ["localhost", "127.0.0.1", "::1"]:
        ssl_mode = "disable"

    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            sslmode=ssl_mode,
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print(f"[DB] Error connecting via parameters: {e}")
        raise e

def init_db():
    """Initialize PostgreSQL tables and seed sample employees."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Employees table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee (
            id                  SERIAL PRIMARY KEY,
            name                TEXT    NOT NULL,
            email               TEXT    NOT NULL UNIQUE,
            designation         TEXT    NOT NULL DEFAULT 'Employee',
            monthly_salary      REAL    NOT NULL,
            attendance_present  INTEGER NOT NULL DEFAULT 0,
            attendance_absent   INTEGER NOT NULL DEFAULT 0,
            working_days        INTEGER NOT NULL DEFAULT 30,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Bills table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill (
            id            SERIAL PRIMARY KEY,
            employee_id   INTEGER NOT NULL,
            amount        REAL    NOT NULL,
            working_days  INTEGER NOT NULL,
            present_days  INTEGER NOT NULL,
            absent_days   INTEGER NOT NULL,
            deduction     REAL    NOT NULL DEFAULT 0,
            notes         TEXT    DEFAULT '',
            employee_name TEXT    NOT NULL DEFAULT 'N/A',
            bill_date     DATE    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'PAID',
            generated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE CASCADE
        )
    """)

    # --- Ensure existing tables have the new column ---
    cursor.execute("ALTER TABLE bill ADD COLUMN IF NOT EXISTS employee_name TEXT NOT NULL DEFAULT 'N/A'")

    # --- Transaction Log table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_log (
            id              SERIAL PRIMARY KEY,
            bill_id         INTEGER NOT NULL,
            amount          REAL    NOT NULL,
            payment_method  TEXT    NOT NULL,
            transaction_ref TEXT    UNIQUE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bill_id) REFERENCES bill(id) ON DELETE CASCADE
        )
    """)

    # --- Seed sample employees if table is empty ---
    cursor.execute("SELECT COUNT(*) AS count FROM employee")
    if cursor.fetchone()["count"] == 0:
        sample_employees = [
            ("Arun Kumar",    "arun.kumar@company.com",    "Software Engineer",  55000, 26, 4, 30),
            ("Priya Sharma",  "priya.sharma@company.com",  "UI/UX Designer",     48000, 28, 2, 30),
            ("Ravi Verma",    "ravi.verma@company.com",    "Backend Developer",  62000, 25, 5, 30),
            ("Anita Nair",    "anita.nair@company.com",    "Project Manager",    75000, 30, 0, 30),
            ("Suresh Menon",  "suresh.menon@company.com",  "QA Engineer",        42000, 22, 8, 30),
            ("Deepa Pillai",  "deepa.pillai@company.com",  "DevOps Engineer",    58000, 27, 3, 30),
            ("Dinesh",  "dinesh@company.com",  "DevOps Engineer",    5000, 27, 3, 30),
        ]
        cursor.executemany("""
            INSERT INTO employee (name, email, designation, monthly_salary,
                                  attendance_present, attendance_absent, working_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, sample_employees)

    conn.commit()
    cursor.close()
    conn.close()
    print("[DB] PostgreSQL initialized successfully.")

if __name__ == "__main__":
    init_db()
