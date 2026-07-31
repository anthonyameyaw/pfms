"""Run once to add new harvest tracking columns."""
import sqlite3, os
db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
migrations = [
    ("ALTER TABLE harvests ADD COLUMN husks_processed INTEGER DEFAULT NULL", "harvests.husks_processed"),
    ("ALTER TABLE harvests ADD COLUMN gallons_sold_price REAL DEFAULT 0", "harvests.gallons_sold_price"),
    ("ALTER TABLE harvests ADD COLUMN gallons_sold_income REAL DEFAULT 0", "harvests.gallons_sold_income"),
]
print("Running migrations...")
for sql, name in migrations:
    try:
        conn.execute(sql); print(f"  ✅ {name}")
    except Exception as e:
        print(f"  — {name}: {'already exists' if 'duplicate' in str(e).lower() else e}")
conn.commit(); conn.close()
print("Done.")
