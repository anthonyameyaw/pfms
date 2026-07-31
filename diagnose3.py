
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'pfms.db'))

print("=== HARVESTS DETAIL ===")
cols = [r[1] for r in conn.execute('PRAGMA table_info(harvests)').fetchall()]
rows = conn.execute("""
    SELECT h.date, f.name, h.bunches_harvested,
           h.harvester_pay, h.collector_pay, h.harvesting_cost,
           h.gallons_produced, h.gallons_sold, h.gallons_sold_income,
           h.driver_pay, h.fuel_cost, h.tricycle_rent
    FROM harvests h JOIN farms f ON f.id=h.farm_id
    ORDER BY h.date
""").fetchall()
headers = ['date','farm','bunches','harvester_pay','collector_pay','harvesting_cost',
           'gallons_prod','gallons_sold','sold_income','driver_pay','fuel','tricycle']
print(f"{'date':<12}{'farm':<22}{'bunches':>7}{'harv_pay':>10}{'coll_pay':>10}{'harv_cost':>10}{'gal_prod':>9}{'gal_sold':>9}{'sold_inc':>10}{'drv_pay':>8}{'fuel':>7}{'trike':>7}")
for r in rows:
    print(f"{str(r[0]):<12}{str(r[1]):<22}{str(r[2] or 0):>7}{str(r[3] or 0):>10}{str(r[4] or 0):>10}{str(r[5] or 0):>10}{str(r[6] or 0):>9}{str(r[7] or 0):>9}{str(r[8] or 0):>10}{str(r[9] or 0):>8}{str(r[10] or 0):>7}{str(r[11] or 0):>7}")

print()
print("=== TRANSPORT LOGS ===")
t_rows = conn.execute("""
    SELECT t.date, f.name, t.transport_type, t.driver_pay, t.fuel_cost, t.rental_cost, t.total_cost
    FROM transport_logs t LEFT JOIN farms f ON f.id=t.farm_id
    ORDER BY t.date
""").fetchall()
for r in t_rows:
    print(r)

conn.close()
