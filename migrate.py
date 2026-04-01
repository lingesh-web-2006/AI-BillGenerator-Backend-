import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "billing.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Checking for migrations...")
    
    # Add status column to bill table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE bill ADD COLUMN status TEXT NOT NULL DEFAULT 'UNPAID'")
        print("Added 'status' column to 'bill' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'status' column already exists.")
        else:
            print(f"Error adding column: {e}")

    # Create transaction_log table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id         INTEGER NOT NULL,
            amount          REAL    NOT NULL,
            payment_method  TEXT    NOT NULL,
            transaction_ref TEXT    UNIQUE,
            created_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (bill_id) REFERENCES bill(id)
        )
    """)
    print("Ensured 'transaction_log' table exists.")
    
    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
