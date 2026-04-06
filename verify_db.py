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

print("Current .env settings:")
print(f"DB_URL: {db_url}")
print(f"DB_NAME: {db_name}")

try:
    if db_url:
        print("\nAttempting connection via DB_URL...")
        conn = psycopg2.connect(db_url)
        print("Success! Connected via DB_URL.")
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            db, user = cur.fetchone()
            print(f"Connected to DB: {db} as User: {user}")
            cur.execute("SELECT COUNT(*) FROM employee")
            count = cur.fetchone()[0]
            print(f"Employee count: {count}")
        conn.close()
    else:
        print("\nNo DB_URL found, attempting via parameters...")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
        print("Success! Connected via parameters.")
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            db, user = cur.fetchone()
            print(f"Connected to DB: {db} as User: {user}")
        conn.close()
except Exception as e:
    print(f"FAILED to connect: {e}")
