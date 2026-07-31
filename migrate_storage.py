"""Run once to add storage tables. Usage: python3 migrate_storage.py"""
from database.db import execute, query

print("Creating storage tables...")
try:
    execute("""
        CREATE TABLE IF NOT EXISTS storage (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date_updated     DATE NOT NULL,
            gallons_in_stock REAL DEFAULT 0,
            price_per_gallon REAL DEFAULT 0,
            total_value      REAL DEFAULT 0,
            notes            TEXT
        )
    """)
    print("  ✅ storage table ready")
except Exception as e:
    print(f"  — {e}")

try:
    execute("""
        CREATE TABLE IF NOT EXISTS storage_transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             DATE NOT NULL,
            transaction_type TEXT CHECK(transaction_type IN ('Addition','Removal','Revaluation')),
            gallons          REAL DEFAULT 0,
            price_per_gallon REAL DEFAULT 0,
            reason           TEXT,
            notes            TEXT
        )
    """)
    print("  ✅ storage_transactions table ready")
except Exception as e:
    print(f"  — {e}")

print("\nDone. You can delete this file.")
