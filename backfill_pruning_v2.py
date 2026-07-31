"""
Backfill ALL pruning_batches into activities.
Wipes any existing backfilled pruning activities first to avoid duplicates,
then re-inserts from scratch from pruning_batches.
"""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# Step 1: Show what's in pruning_batches
batches = conn.execute("""
    SELECT pb.id, pb.farm_id, pb.date, pb.trees_pruned,
           pb.num_labourers, pb.labour_cost, pb.notes,
           f.name AS farm_name
    FROM pruning_batches pb
    JOIN farms f ON f.id = pb.farm_id
    ORDER BY pb.farm_id, pb.date
""").fetchall()

print(f"Pruning batches in database: {len(batches)}")
for b in batches:
    print(f"  {b['date']} | {b['farm_name']} | {b['trees_pruned']} trees | GHS {b['labour_cost']}")

# Step 2: Delete activities that were backfilled (description contains 'backfilled from pruning')
# AND delete any pruning activities that match a pruning batch exactly by date+farm+cost
# to avoid duplicates from the previous partial backfill

deleted = conn.execute("""
    DELETE FROM activities
    WHERE activity_type = 'Pruning'
      AND description LIKE '%backfilled from pruning%'
""").rowcount
print(f"\nDeleted {deleted} previously backfilled activities")

# Step 3: For each pruning batch, check if there's ALREADY a manually-entered
# pruning activity on the same date for the same farm (not backfilled)
# If yes, skip. If no, insert.

inserted = 0
skipped  = 0

for b in batches:
    if not b['labour_cost'] or b['labour_cost'] <= 0:
        print(f"  — SKIP {b['date']} {b['farm_name']}: no labour cost")
        skipped += 1
        continue

    # Check for existing non-backfilled pruning activity on same date/farm
    existing = conn.execute("""
        SELECT id, labour_cost FROM activities
        WHERE farm_id = ?
          AND date = ?
          AND activity_type = 'Pruning'
          AND description NOT LIKE '%backfilled from pruning%'
    """, (b['farm_id'], b['date'])).fetchone()

    if existing:
        print(f"  — SKIP {b['date']} {b['farm_name']}: manual activity exists (id={existing['id']}, GHS {existing['labour_cost']})")
        skipped += 1
        continue

    conn.execute("""
        INSERT INTO activities
            (farm_id, date, activity_type, description,
             num_labourers, labour_cost, materials_used, materials_cost, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        b['farm_id'],
        b['date'],
        'Pruning',
        f"Pruning — {b['trees_pruned']} trees (backfilled from pruning log)",
        b['num_labourers'] or 0,
        b['labour_cost'],
        '', 0,
        b['notes'] or '',
    ))
    inserted += 1
    print(f"  ✅ {b['date']} {b['farm_name']}: {b['trees_pruned']} trees, GHS {b['labour_cost']:.2f}")

conn.commit()

# Step 4: Verify
total_pruning_acts = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(labour_cost),0) FROM activities WHERE activity_type='Pruning'"
).fetchone()
total_pruning_batches = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(labour_cost),0) FROM pruning_batches WHERE labour_cost>0"
).fetchone()

print(f"\n{'='*50}")
print(f"Pruning batches:   {total_pruning_batches[0]} entries, GHS {total_pruning_batches[1]:,.2f} total")
print(f"Pruning activities:{total_pruning_acts[0]} entries, GHS {total_pruning_acts[1]:,.2f} total")
print(f"Inserted: {inserted} | Skipped: {skipped}")
print("="*50)
conn.close()
