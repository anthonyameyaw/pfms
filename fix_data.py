
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'pfms.db'))
conn.row_factory = sqlite3.Row

print("BEFORE cleanup:")
print(f"  Harvest rows: {conn.execute('SELECT COUNT(*) FROM harvests').fetchone()[0]}")
print(f"  Transport rows: {conn.execute('SELECT COUNT(*) FROM transport_logs').fetchone()[0]}")
print(f"  Harvesting cost total: {conn.execute('SELECT SUM(harvesting_cost) FROM harvests').fetchone()[0]}")
print(f"  Transport total: {conn.execute('SELECT SUM(total_cost) FROM transport_logs').fetchone()[0]}")

# ── Fix 1: Remove duplicate harvest rows ─────────────────────────────────────
# Keep the row with the highest id for each (farm_id, date) combination
# that has actual data (gallons_sold_income > 0 preferred, otherwise most complete)
print()
print("Removing duplicate harvest rows...")

# Find all (farm_id, date) groups with multiple rows
dups = conn.execute("""
    SELECT farm_id, date, COUNT(*) as cnt
    FROM harvests
    GROUP BY farm_id, date
    HAVING COUNT(*) > 1
""").fetchall()

removed = 0
for dup in dups:
    farm_id, date, cnt = dup['farm_id'], dup['date'], dup['cnt']
    rows = conn.execute("""
        SELECT id, gallons_sold_income, harvesting_cost, bunches_harvested
        FROM harvests WHERE farm_id=? AND date=?
        ORDER BY gallons_sold_income DESC, harvesting_cost DESC, id DESC
    """, (farm_id, date)).fetchall()
    # Keep the first (best) row, delete the rest
    keep_id = rows[0]['id']
    for row in rows[1:]:
        conn.execute("DELETE FROM harvests WHERE id=?", (row['id'],))
        removed += 1
        print(f"  Removed duplicate harvest id={row['id']} (farm_id={farm_id}, date={date})")

print(f"Removed {removed} duplicate harvest rows")

# ── Fix 2: Remove transport from expense calculation ─────────────────────────
# Transport is already in transport_logs — remove driver_pay/fuel/tricycle
# from harvests to avoid double-counting
# We zero them out in harvests since transport_logs is the canonical source
print()
print("Zeroing transport fields in harvests (already in transport_logs)...")
conn.execute("""
    UPDATE harvests SET driver_pay=0, fuel_cost=0, tricycle_rent=0
    WHERE driver_pay > 0 OR fuel_cost > 0 OR tricycle_rent > 0
""")
print(f"  Done — transport_logs remains the single source for transport costs")

# ── Fix 3: Remove Cashew Farm harvest (farm_id=1 has no oil palm) ─────────────
cashew_harvests = conn.execute("SELECT id FROM harvests WHERE farm_id=1").fetchall()
if cashew_harvests:
    conn.execute("DELETE FROM harvests WHERE farm_id=1")
    print(f"Removed {len(cashew_harvests)} Cashew Farm harvest rows (not oil palm)")

# ── Fix 4: Remove duplicate transport logs ────────────────────────────────────
print()
print("Removing duplicate transport logs...")
dup_t = conn.execute("""
    SELECT farm_id, date, transport_type, COUNT(*) as cnt
    FROM transport_logs
    GROUP BY farm_id, date, transport_type
    HAVING COUNT(*) > 1
""").fetchall()
removed_t = 0
for dup in dup_t:
    rows = conn.execute("""
        SELECT id FROM transport_logs
        WHERE farm_id=? AND date=? AND transport_type=?
        ORDER BY id DESC
    """, (dup['farm_id'], dup['date'], dup['transport_type'])).fetchall()
    for row in rows[1:]:
        conn.execute("DELETE FROM transport_logs WHERE id=?", (row['id'],))
        removed_t += 1
        print(f"  Removed duplicate transport id={row['id']}")
print(f"Removed {removed_t} duplicate transport rows")

conn.commit()

print()
print("AFTER cleanup:")
print(f"  Harvest rows: {conn.execute('SELECT COUNT(*) FROM harvests').fetchone()[0]}")
print(f"  Transport rows: {conn.execute('SELECT COUNT(*) FROM transport_logs').fetchone()[0]}")
print(f"  Harvesting cost total: {conn.execute('SELECT SUM(harvesting_cost) FROM harvests').fetchone()[0]}")
print(f"  Transport total: {conn.execute('SELECT SUM(total_cost) FROM transport_logs').fetchone()[0]}")

# Show corrected totals
at_inc = conn.execute("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE gallons_sold_income>0").fetchone()[0]
at_plant = conn.execute("SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs").fetchone()[0]
at_harv = conn.execute("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests").fetchone()[0]
at_trans = conn.execute("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs").fetchone()[0]
at_act = conn.execute("SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE activity_type!='Harvesting'").fetchone()[0]
at_plant_exp = conn.execute("SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs").fetchone()[0]
at_pexp = conn.execute("SELECT COALESCE(SUM(amount),0) FROM plant_expenses").fetchone()[0]
total_exp = at_harv + at_trans + at_act + at_plant_exp + at_pexp
total_inc = at_inc + at_plant

print()
print("=== CORRECTED FINANCIALS ===")
print(f"Farm income (sold gallons): GHS {at_inc:,.2f}")
print(f"Plant income: GHS {at_plant:,.2f}")
print(f"Total income: GHS {total_inc:,.2f}")
print(f"Harvesting labour: GHS {at_harv:,.2f}")
print(f"Transport: GHS {at_trans:,.2f}")
print(f"Activity labour/materials: GHS {at_act:,.2f}")
print(f"Plant electricity+operator: GHS {at_plant_exp:,.2f}")
print(f"Plant other expenses: GHS {at_pexp:,.2f}")
print(f"Total expenses: GHS {total_exp:,.2f}")
print(f"NET PROFIT: GHS {total_inc - total_exp:,.2f}")

conn.close()
print("\nDone. Restart the app.")
