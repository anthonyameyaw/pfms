
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'database', 'pfms.db'))

print("=== APRIL 2026 EXPENSES BREAKDOWN ===")
apr_start, apr_end = "2026-04-01", "2026-05-01"

a = conn.execute("SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE date>=? AND date<? AND activity_type!='Harvesting'",(apr_start,apr_end)).fetchone()[0]
print(f"Activity labour/materials: {a}")

h = conn.execute("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Harvesting cost: {h}")

t = conn.execute("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Transport: {t}")

e = conn.execute("SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Plant electricity+operator: {e}")

pe = conn.execute("SELECT COALESCE(SUM(amount),0) FROM plant_expenses WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Plant expenses: {pe}")

fe = conn.execute("SELECT COALESCE(SUM(amount),0) FROM farm_expenses WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Farm expenses table: {fe}")

print(f"TOTAL MONTHLY EXP: {a+h+t+e+pe}")

print()
print("=== APRIL INCOME ===")
i1 = conn.execute("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE date>=? AND date<? AND gallons_sold_income>0",(apr_start,apr_end)).fetchone()[0]
print(f"Harvest sales income: {i1}")
i2 = conn.execute("SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs WHERE date>=? AND date<?",(apr_start,apr_end)).fetchone()[0]
print(f"Plant income: {i2}")

print()
print("=== ALL-TIME COMPARISON ===")
at_inc = conn.execute("SELECT COALESCE(SUM(gallons_sold_income),0) FROM harvests WHERE gallons_sold_income>0").fetchone()[0]
at_plant = conn.execute("SELECT COALESCE(SUM(gross_revenue),0) FROM processing_runs").fetchone()[0]
print(f"All-time farm income: {at_inc}")
print(f"All-time plant income: {at_plant}")
print(f"All-time total income: {at_inc + at_plant}")

at_act = conn.execute("SELECT COALESCE(SUM(labour_cost+materials_cost),0) FROM activities WHERE activity_type!='Harvesting'").fetchone()[0]
at_h = conn.execute("SELECT COALESCE(SUM(harvesting_cost),0) FROM harvests").fetchone()[0]
at_t = conn.execute("SELECT COALESCE(SUM(total_cost),0) FROM transport_logs").fetchone()[0]
at_pe = conn.execute("SELECT COALESCE(SUM(electricity_cost+operator_pay),0) FROM processing_runs").fetchone()[0]
at_pexp = conn.execute("SELECT COALESCE(SUM(amount),0) FROM plant_expenses").fetchone()[0]
at_fexp = conn.execute("SELECT COALESCE(SUM(amount),0) FROM farm_expenses").fetchone()[0]

print(f"All-time activity labour: {at_act}")
print(f"All-time harvesting cost: {at_h}")
print(f"All-time transport: {at_t}")
print(f"All-time plant elec+op: {at_pe}")
print(f"All-time plant expenses: {at_pexp}")
print(f"All-time farm expenses table: {at_fexp}")
total_exp = at_act + at_h + at_t + at_pe + at_pexp
print(f"All-time total expenses: {total_exp}")
print(f"All-time net: {at_inc + at_plant - total_exp}")
conn.close()
