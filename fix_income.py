
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'pfms.db'))

print("=== BEFORE CLEANUP ===")
total_before = conn.execute("SELECT COALESCE(SUM(quantity * unit_price),0) FROM farm_income").fetchone()[0]
print(f"farm_income total (quantity x unit_price): {total_before}")
count_before = conn.execute("SELECT COUNT(*) FROM farm_income").fetchone()[0]
print(f"farm_income row count: {count_before}")

# The farm_income table has corrupted data:
# - quantity = gallons sold (not quantity of bunches)
# - unit_price = TOTAL income (not price per gallon) -- so quantity * unit_price is wildly wrong
# - notes = income amount (the actual correct value)
# Solution: clear the entire farm_income table -- we will read income from harvests.gallons_sold_income instead
# First confirm harvests has the real data
print()
print("=== harvests.gallons_sold_income (SOURCE OF TRUTH) ===")
rows = conn.execute("""
    SELECT f.name, h.date, h.gallons_sold, h.gallons_sold_price, h.gallons_sold_income
    FROM harvests h JOIN farms f ON f.id = h.farm_id
    WHERE h.gallons_sold_income > 0
    ORDER BY f.id, h.date
""").fetchall()
for r in rows:
    print(r)

total_correct = conn.execute("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests").fetchone()[0]
print(f"\nCorrect all-time farm income: GHS {total_correct:,.2f}")

# Clear the corrupt farm_income table
conn.execute("DELETE FROM farm_income")
conn.commit()
print(f"\n=== CLEARED {count_before} corrupt farm_income rows ===")
print("Income will now be read directly from harvests.gallons_sold_income")
print("\nDone. Restart the app.")
conn.close()
