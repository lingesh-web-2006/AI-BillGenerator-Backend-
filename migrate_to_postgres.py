"""
Migration Utility - Move data from SQLite to PostgreSQL
"""

import sqlite3
import psycopg2
from database import get_connection, init_db

def migrate():
    print("🚀 Starting migration from SQLite to PostgreSQL...")
    
    # 1. Initialize PostgreSQL tables
    try:
        init_db()
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL. Have you filled in your .env file?\nError: {e}")
        return

    # 2. Connect to SQLite
    sqlite_conn = sqlite3.connect("billing.db")
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 3. Connect to PostgreSQL
    pg_conn = get_connection()
    pg_cur = pg_conn.cursor()

    tables = ["employee", "bill", "transaction_log"]

    for table in tables:
        print(f"📦 Migrating table: {table}...")
        
        # Clear existing data in PG (be careful!)
        pg_cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        
        # Fetch data from SQLite
        sqlite_cur.execute(f"SELECT * FROM {table}")
        rows = sqlite_cur.fetchall()
        
        if not rows:
            print(f"ℹ️ Table {table} is empty in SQLite.")
            continue

        # Prepare insert query
        columns = rows[0].keys()
        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join(columns)
        
        insert_query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        
        # Insert data into PG
        for row in rows:
            pg_cur.execute(insert_query, tuple(row))
        
        # Update sequence for SERIAL ID
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))")
        
        print(f"✅ Migrated {len(rows)} records for {table}.")

    pg_conn.commit()
    
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n🎉 Migration finished successfully!")

if __name__ == "__main__":
    migrate()
