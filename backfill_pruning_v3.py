"""Backfill pruning batches into activities — auto-detects column names."""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# First, discover actual column names
cols = [c[1] for c in conn.execute('PRAGMA table_info(pruning_batches)').fetchall()]
print(f"pruning_batches columns: {cols}")

# Find the cost column
cost_col = next((c for c in cols if 'cost' in c.lower() or 'labour' in c.lower() or 'labor' in c.lower()), None)
workers_col = next((c for c in cols if 'labour' in c.lower() or 'worker' in c.lower() or 'labou' in c.lower() or 'num_lab' in c.lower()), None)
trees_col = next((c for c in cols if 'tree' in c.lower() or 'pruned' in c.lower()), None)

print(f"Cost column:    {cost_col}")
print(f"Workers column: {workers_col}")
print(f"Trees column:   {trees_col}")

if not cost_col:
    print("\nERROR: Could not find cost column. All columns:", cols)
    conn.close()
    exit(1)

# Fetch all batches
batches = conn.execute(f"""
    SELECT pb.id, pb.farm_id, pb.date,
           pb.{trees_col}   AS trees_pruned,
           pb.{cost_col}    AS labour_cost,
           {'pb.' + workers_col + ' AS num_labourers,' if workers_col and workers_col != cost_col else '1 AS num_labourers,'}
           pb.notes,
           f.name AS farm_name
    FROM pruning_batches pb
    JOIN farms f ON f.id = pb.farm_id
    ORDER BY pb.farm_id, pb.date
""").fetchall()

print(f"\nFound {len(batches)} pruning batches:")
for b in batches:
    print(f"  {b['date']} | {b['farm_name']} | {b['trees_pruned']} trees | GHS {b['labour_cost']}")

# Delete previously backfilled
deleted = conn.execute("""
    DELETE FROM activities
    WHERE activity_type='Pruning'
      AND description LIKE '%backfilled from pruning%'
""").rowcount
print(f"\nCleared {deleted} old backfilled entries")

inserted = 0
skipped  = 0

for b in batches:
    cost = float(b['labour_cost'] or 0)
    if cost <= 0:
        print(f"  — SKIP {b['date']} {b['farm_name']}: no cost")
        skipped += 1
        continue

    # Check for existing manual pruning activity same date+farm
    existing = conn.execute("""
        SELECT id FROM activities
        WHERE farm_id=? AND date=? AND activity_type='Pruning'
          AND description NOT LIKE '%backfilled from pruning%'
    """, (b['farm_id'], b['date'])).fetchone()

    if existing:
        print(f"  — SKIP {b['date']} {b['farm_name']}: manual entry exists")
        skipped += 1
        continue

    conn.execute("""
        INSERT INTO activities
            (farm_id, date, activity_type, description,
             num_labourers, labour_cost, materials_used, materials_cost, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        b['farm_id'], b['date'], 'Pruning',
        f"Pruning — {b['trees_pruned']} trees (backfilled from pruning log)",
        b['num_labourers'] or 0,
        cost, '', 0,
        b['notes'] or '',
    ))
    inserted += 1
    print(f"  ✅ {b['date']} {b['farm_name']}: {b['trees_pruned']} trees, GHS {cost:.2f}")

conn.commit()

# Summary
r1 = conn.execute("SELECT COUNT(*), COALESCE(SUM(labour_cost),0) FROM activities WHERE activity_type='Pruning'").fetchone()
r2 = conn.execute(f"SELECT COUNT(*), COALESCE(SUM({cost_col}),0) FROM pruning_batches WHERE {cost_col}>0").fetchone()
print(f"\n{'='*55}")
print(f"Pruning batches total:     {r2[0]} entries, GHS {r2[1]:,.2f}")
print(f"Pruning activities total:  {r1[0]} entries, GHS {r1[1]:,.2f}")
print(f"Inserted: {inserted}  |  Skipped: {skipped}")
print("="*55)
conn.close()
