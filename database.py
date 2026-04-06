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
DB_PASS = os.getenv("DB_PASS", "Postgre")

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
            print(f"[DB] SUCCESS: Connected to Remote PostgreSQL via DB_URL ({db_url.split('@')[-1].split('/')[0]})")
            return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"[DB] WARNING: Remote connection failed: {e}")
            print(f"[DB] FALLBACK: Attempting local connection...")
            # If URL fails, fall back to individual parameters below
    
    # Priority 2: Individual Parameters
    ssl_mode = os.getenv("DB_SSL", "require")
    if DB_HOST in ["localhost", "127.0.0.1", "::1"]:
        ssl_mode = "disable"

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            sslmode=ssl_mode,
            cursor_factory=RealDictCursor
        )
        print(f"[DB] SUCCESS: Connected to Local PostgreSQL (Host: {DB_HOST}, DB: {DB_NAME})")
        return conn
    except Exception as e:
        print(f"[DB] Error connecting via parameters: {e}")
        raise e

def init_db():
    """Initialize PostgreSQL tables and seed sample data."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Companies table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company (
            id            SERIAL PRIMARY KEY,
            name          TEXT    NOT NULL,
            logo_url      TEXT    DEFAULT '',
            address       TEXT    DEFAULT '',
            gst_number    TEXT    DEFAULT '',
            phone         TEXT    DEFAULT '',
            template_name TEXT    NOT NULL DEFAULT 'Modern',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default company if none exists
    cursor.execute("SELECT COUNT(*) AS count FROM company")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("""
            INSERT INTO company (name, logo_url, address, gst_number, phone, template_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, ("vips Tech", "https://via.placeholder.com/150", "redhills chennai 52", "27AAAAA0000A1Z5", "+91 98765 43210", "Modern"))
        default_company_id = cursor.fetchone()["id"]
    else:
        # Update existing "Default Corp" if it exists
        cursor.execute("""
            UPDATE company 
            SET name = %s, address = %s 
            WHERE name = 'Default Corp' OR name = 'DEFAULT CORP'
        """, ("vips Tech", "redhills chennai 52"))
        
        cursor.execute("SELECT id FROM company LIMIT 1")
        default_company_id = cursor.fetchone()["id"]

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
            company_id          INTEGER REFERENCES company(id) ON DELETE SET NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ensure company_id column exists and has a default value for existing rows
    cursor.execute("ALTER TABLE employee ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES company(id) ON DELETE SET NULL")
    cursor.execute("UPDATE employee SET company_id = %s WHERE company_id IS NULL", (default_company_id,))

    # --- Bills table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill (
            id            SERIAL PRIMARY KEY,
            employee_id   INTEGER NOT NULL,
            company_id    INTEGER REFERENCES company(id) ON DELETE CASCADE,
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

    # Ensure company_id column exists and has a default value for existing rows
    cursor.execute("ALTER TABLE bill ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES company(id) ON DELETE CASCADE")
    cursor.execute("UPDATE bill SET company_id = %s WHERE company_id IS NULL", (default_company_id,))

    # Ensure existing bills have the employee_name column
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
            ("Arun Kumar",    "arun.kumar@company.com",    "Software Engineer",  55000, 26, 4, 30, default_company_id),
            ("Priya Sharma",  "priya.sharma@company.com",  "UI/UX Designer",     48000, 28, 2, 30, default_company_id),
            ("Ravi Verma",    "ravi.verma@company.com",    "Backend Developer",  62000, 25, 5, 30, default_company_id),
            ("Anita Nair",    "anita.nair@company.com",    "Project Manager",    75000, 30, 0, 30, default_company_id),
        ]
        cursor.executemany("""
            INSERT INTO employee (name, email, designation, monthly_salary,
                                  attendance_present, attendance_absent, working_days, company_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, sample_employees)

    conn.commit()
    cursor.close()
    conn.close()
    print("[DB] PostgreSQL initialized with Multi-Company support successfully.")

if __name__ == "__main__":
    init_db()
