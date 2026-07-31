"""Add fresh_gallons and soap_gallons columns to storage_transactions. Run once."""
import sqlite3, os
db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
cols = [c[1] for c in conn.execute('PRAGMA table_info(storage_transactions)').fetchall()]

for col, default in [('fresh_gallons', 0), ('soap_gallons', 0), ('farm_id', 'NULL')]:
    if col not in cols:
        null = 'DEFAULT NULL' if default == 'NULL' else f'DEFAULT {default}'
        conn.execute(f'ALTER TABLE storage_transactions ADD COLUMN {col} REAL {null}')
        print(f"✅ Added {col}")
    else:
        print(f"— {col} already exists")

# Also add farm_id to storage_transactions so per-farm storage works
conn.commit()
conn.close()
print("Done.")
