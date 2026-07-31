"""Backfill pruning batches into activities. Column is 'cost' not 'labour_cost'."""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# Confirm columns
cols = [c[1] for c in conn.execute('PRAGMA table_info(pruning_batches)').fetchall()]
print(f"Columns: {cols}")
# cost column is literally 'cost'

batches = conn.execute("""
    SELECT pb.id, pb.farm_id, pb.date,
           pb.trees_pruned, pb.num_labourers,
           pb.cost AS labour_cost,
           pb.notes, f.name AS farm_name
    FROM pruning_batches pb
    JOIN farms f ON f.id = pb.farm_id
    ORDER BY pb.farm_id, pb.date
""").fetchall()

print(f"\n{len(batches)} pruning batches found:")
for b in batches:
    print(f"  {b['date']} | {b['farm_name']} | {b['trees_pruned']} trees | GHS {b['labour_cost']}")

# Delete ALL backfilled pruning activities and re-insert cleanly
deleted = conn.execute("""
    DELETE FROM activities
    WHERE activity_type='Pruning'
      AND description LIKE '%backfilled from pruning%'
""").rowcount
print(f"\nDeleted {deleted} old backfilled entries")

# Also remove the wrongly-inserted GHS 1.00 entries from v3
wrong = conn.execute("""
    DELETE FROM activities
    WHERE activity_type='Pruning'
      AND labour_cost = 1.0
      AND description LIKE '%trees%'
""").rowcount
print(f"Deleted {wrong} wrongly-costed entries (GHS 1.00 from v3)")

inserted = 0
skipped  = 0

for b in batches:
    cost = float(b['labour_cost'] or 0)
    if cost <= 0:
        print(f"  — SKIP {b['date']} {b['farm_name']}: cost is 0")
        skipped += 1
        continue

    # Only skip if there's a manually entered pruning activity (not backfilled)
    # on the same date for the same farm with the same cost
    existing = conn.execute("""
        SELECT id FROM activities
        WHERE farm_id=? AND date=? AND activity_type='Pruning'
          AND ABS(labour_cost - ?) < 0.01
          AND description NOT LIKE '%backfilled from pruning%'
    """, (b['farm_id'], b['date'], cost)).fetchone()

    if existing:
        print(f"  — SKIP {b['date']} {b['farm_name']}: GHS {cost:.2f} already in activities (id={existing['id']})")
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

# Final verification
r_act = conn.execute("""
    SELECT COUNT(*) AS n, COALESCE(SUM(labour_cost),0) AS total
    FROM activities WHERE activity_type='Pruning'
""").fetchone()
r_bat = conn.execute("""
    SELECT COUNT(*) AS n, COALESCE(SUM(cost),0) AS total
    FROM pruning_batches WHERE cost>0
""").fetchone()

print(f"\n{'='*55}")
print(f"Pruning batches:   {r_bat['n']} entries, GHS {r_bat['total']:,.2f}")
print(f"Pruning activities:{r_act['n']} entries, GHS {r_act['total']:,.2f}")
print(f"Inserted: {inserted}  |  Skipped: {skipped}")
if abs(r_bat['total'] - r_act['total']) < 1:
    print("✅ Totals match — all pruning costs now in activities")
else:
    print(f"⚠ Difference: GHS {abs(r_bat['total'] - r_act['total']):.2f}")
print("="*55)
conn.close()
