"""
Backfill existing pruning_batches into activities table.
Safe to run multiple times — checks for duplicates before inserting.
"""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# Get all pruning batches that have a labour cost
batches = conn.execute("""
    SELECT pb.id, pb.farm_id, pb.date, pb.trees_pruned,
           pb.num_labourers, pb.labour_cost, pb.notes,
           f.name AS farm_name
    FROM pruning_batches pb
    JOIN farms f ON f.id = pb.farm_id
    WHERE pb.labour_cost > 0
    ORDER BY pb.date
""").fetchall()

print(f"Found {len(batches)} pruning batches with labour cost > 0")

inserted = 0
skipped  = 0

for b in batches:
    # Check if an activity already exists for this farm/date/type with same cost
    existing = conn.execute("""
        SELECT id FROM activities
        WHERE farm_id = ?
          AND date = ?
          AND activity_type = 'Pruning'
          AND labour_cost = ?
          AND description LIKE '%' || ? || '%'
        LIMIT 1
    """, (b['farm_id'], b['date'], b['labour_cost'],
          str(b['trees_pruned']))).fetchone()

    if existing:
        skipped += 1
        print(f"  — SKIP  {b['date']} {b['farm_name']}: activity already exists (id={existing['id']})")
        continue

    # Insert into activities
    conn.execute("""
        INSERT INTO activities
            (farm_id, date, activity_type, description,
             num_labourers, labour_cost, materials_used, materials_cost, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        b['farm_id'],
        b['date'],
        'Pruning',
        f"Pruning batch — {b['trees_pruned']} trees (backfilled from pruning log)",
        b['num_labourers'] or 0,
        b['labour_cost'],
        '',
        0,
        b['notes'] or '',
    ))
    inserted += 1
    print(f"  ✅ INSERT {b['date']} {b['farm_name']}: {b['trees_pruned']} trees, "
          f"GHS {b['labour_cost']:.2f} labour")

conn.commit()
conn.close()

print(f"\nDone — {inserted} backfilled, {skipped} already existed.")
print("Pruning costs will now appear in farm P&L and Finances.")
