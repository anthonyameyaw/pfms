"""
Run this ONCE to add new columns to your existing database.
Usage: python3 migrate.py
"""
from database.db import execute, query

migrations = [
    # Harvest labour breakdown
    ("ALTER TABLE harvests ADD COLUMN harvester_pay REAL DEFAULT 0",     "harvests.harvester_pay"),
    ("ALTER TABLE harvests ADD COLUMN collector_pay REAL DEFAULT 0",     "harvests.collector_pay"),
    ("ALTER TABLE harvests ADD COLUMN num_collectors INTEGER DEFAULT 0", "harvests.num_collectors"),
    # Farm oil production & income
    ("ALTER TABLE harvests ADD COLUMN gallons_produced REAL DEFAULT 0",  "harvests.gallons_produced"),
    ("ALTER TABLE harvests ADD COLUMN price_per_gallon REAL DEFAULT 0",  "harvests.price_per_gallon"),
    ("ALTER TABLE harvests ADD COLUMN oil_income REAL DEFAULT 0",        "harvests.oil_income"),
    # Transport embedded in harvest
    ("ALTER TABLE harvests ADD COLUMN transport_mode TEXT DEFAULT NULL", "harvests.transport_mode"),
    ("ALTER TABLE harvests ADD COLUMN driver_pay REAL DEFAULT 0",        "harvests.driver_pay"),
    ("ALTER TABLE harvests ADD COLUMN fuel_cost REAL DEFAULT 0",         "harvests.fuel_cost"),
    ("ALTER TABLE harvests ADD COLUMN tricycle_rent REAL DEFAULT 0",     "harvests.tricycle_rent"),
    # Processing plant cash tracking
    ("ALTER TABLE processing_runs ADD COLUMN gallons_produced REAL DEFAULT 0",      "processing_runs.gallons_produced"),
    ("ALTER TABLE processing_runs ADD COLUMN cash_collected REAL DEFAULT 0",        "processing_runs.cash_collected"),
    ("ALTER TABLE processing_runs ADD COLUMN cash_outstanding REAL DEFAULT 0",      "processing_runs.cash_outstanding"),
    ("ALTER TABLE processing_runs ADD COLUMN outside_farmer_gallons REAL DEFAULT 0","processing_runs.outside_farmer_gallons"),
]

print("Running database migrations...")
for sql, name in migrations:
    try:
        execute(sql)
        print(f"  ✅ Added: {name}")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"  — Already exists: {name}")
        else:
            print(f"  ⚠ {name}: {e}")

print("\nMigration complete. You can delete this file now.")
