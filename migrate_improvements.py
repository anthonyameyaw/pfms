"""Run once to add new columns for the improvements."""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)

migrations = [
    ("ALTER TABLE storage_transactions ADD COLUMN farm_id INTEGER REFERENCES farms(id)",
     "storage_transactions.farm_id"),
    ("ALTER TABLE harvests ADD COLUMN gallons_sold REAL DEFAULT 0",
     "harvests.gallons_sold"),
]

print("Running migrations...")
for sql, name in migrations:
    try:
        conn.execute(sql)
        print(f"  ✅ Added: {name}")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"  — Already exists: {name}")
        else:
            print(f"  ⚠ {name}: {e}")

conn.commit()
conn.close()
print("\nDone.")
