"""Add threshing_cost column to harvests table. Run once."""
import sqlite3, os
db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)

# Check if column already exists
cols = [c[1] for c in conn.execute('PRAGMA table_info(harvests)').fetchall()]
if 'threshing_cost' not in cols:
    conn.execute('ALTER TABLE harvests ADD COLUMN threshing_cost REAL DEFAULT 0')
    conn.commit()
    print("✅ threshing_cost column added to harvests")
else:
    print("— threshing_cost already exists")

conn.close()
