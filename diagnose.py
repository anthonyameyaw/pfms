
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'pfms.db'))

print("=== farm_income rows ===")
cols = [r[1] for r in conn.execute('PRAGMA table_info(farm_income)').fetchall()]
print("Columns:", cols)
rows = conn.execute('SELECT * FROM farm_income ORDER BY farm_id, date').fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(dict(zip(cols, r)))

print()
print("=== SUM per farm ===")
for farm_id in range(1, 7):
    total = conn.execute('SELECT COALESCE(SUM(total_amount),0) FROM farm_income WHERE farm_id=?', (farm_id,)).fetchone()[0]
    count = conn.execute('SELECT COUNT(*) FROM farm_income WHERE farm_id=?', (farm_id,)).fetchone()[0]
    if count > 0:
        print(f'Farm {farm_id}: {count} rows, total = {total}')

print()
print("=== harvests.gallons_sold_income per farm ===")
for farm_id in range(1, 7):
    total = conn.execute('SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE farm_id=?', (farm_id,)).fetchone()[0]
    count = conn.execute('SELECT COUNT(*) FROM harvests WHERE farm_id=?', (farm_id,)).fetchone()[0]
    if count > 0 or total > 0:
        print(f'Farm {farm_id}: {count} harvest rows, gallons_sold_income total = {total}')

conn.close()
