import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DB_URL")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "employee_billing")
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASS", "")

print("--- DIAGNOSTICS ---")
print(f"DB_URL exists: {bool(db_url)}")
print(f"DB_HOST: {db_host}")
print(f"DB_PORT: {db_port}")
print(f"DB_NAME: {db_name}")
print(f"DB_USER: {db_user}")

if db_url:
    print("\nTracing DB_URL connection...")
    try:
        conn = psycopg2.connect(db_url + ("&sslmode=require" if "?" in db_url else "?sslmode=require"))
        print("OK: URL connection success")
        conn.close()
    except Exception as e:
        print(f"FAIL: URL connection error: {e}")

print("\nTracing Parameter connection...")
try:
    # Use standard settings for local testing
    ssl_mode = "disable" if db_host in ["localhost", "127.0.0.1"] else "require"
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_pass,
        sslmode=ssl_mode
    )
    print("OK: Parameter connection success")
    conn.close()
except Exception as e:
    print(f"FAIL: Parameter connection error: {e}")
