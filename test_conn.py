import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "employee_billing")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

print(f"Testing DB_URL: {DB_URL[:20]}...")

try:
    if DB_URL:
        dsn = DB_URL
        if "sslmode=" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn += f"{sep}sslmode=require"
        print(f"Trying connect with dsn: {dsn[:30]}...")
        conn = psycopg2.connect(dsn)
        print("SUCCESS via DB_URL")
        conn.close()
    else:
        print("No DB_URL found.")
except Exception as e:
    print(f"FAILED via DB_URL: {e}\n")

print(f"Testing via Parameters: host={DB_HOST}, user={DB_USER}, db={DB_NAME}")
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode="disable" if DB_HOST == "localhost" else "require"
    )
    print("SUCCESS via Parameters")
    conn.close()
except Exception as e:
    print(f"FAILED via Parameters: {e}")
