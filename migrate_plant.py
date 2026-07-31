"""Run once to rebuild processing_runs table with correct structure."""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)

print("Backing up existing data...")
try:
    rows = conn.execute("SELECT * FROM processing_runs").fetchall()
    print(f"  {len(rows)} existing run(s) — will need to be re-entered after migration")
except:
    rows = []

print("Rebuilding processing_runs table...")
conn.execute("DROP TABLE IF EXISTS processing_runs_old")
conn.execute("ALTER TABLE processing_runs RENAME TO processing_runs_old")
conn.execute("""
CREATE TABLE processing_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    date                        DATE NOT NULL,
    own_farms_litres            REAL DEFAULT 0,
    own_farms_gallons           REAL DEFAULT 0,
    own_farms_bunches           INTEGER DEFAULT 0,
    outside_farmers_litres      REAL DEFAULT 0,
    outside_farmers_gallons     REAL DEFAULT 0,
    outside_farmers_bunches     INTEGER DEFAULT 0,
    total_output_litres         REAL DEFAULT 0,
    total_output_gallons        REAL DEFAULT 0,
    gross_revenue               REAL DEFAULT 0,
    outside_farmer_fees         REAL DEFAULT 0,
    electricity_cost            REAL DEFAULT 0,
    net_revenue                 REAL DEFAULT 0,
    operator_pay                REAL DEFAULT 0,
    company_revenue             REAL DEFAULT 0,
    cash_collected              REAL DEFAULT 0,
    cash_outstanding            REAL DEFAULT 0,
    notes                       TEXT
)
""")
conn.execute("DROP TABLE IF EXISTS processing_runs_old")
conn.commit()
conn.close()
print("✅ Done. Processing runs table rebuilt with correct structure.")
if rows:
    print(f"\n⚠️  {len(rows)} old run(s) could not be migrated automatically.")
    print("   Please re-enter them using the new Log Processing Run form.")
