"""Run once to create investor tracking tables."""
import sqlite3, os
db = os.path.join(os.path.dirname(__file__), 'database', 'pfms.db')
conn = sqlite3.connect(db)

print("Creating investor tables...")

conn.execute('''
    CREATE TABLE IF NOT EXISTS investors (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        phone       TEXT,
        email       TEXT,
        location    TEXT,
        notes       TEXT,
        date_joined DATE
    )
''')
print("  ✅ investors")

conn.execute('''
    CREATE TABLE IF NOT EXISTS investments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        investor_id     INTEGER NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
        farm_id         INTEGER REFERENCES farms(id),
        date            DATE NOT NULL,
        amount          REAL NOT NULL DEFAULT 0,
        investment_type TEXT DEFAULT 'Cash',
        equity_pct      REAL DEFAULT 0,
        expected_return REAL DEFAULT 0,
        return_date     DATE,
        status          TEXT DEFAULT 'Active',
        notes           TEXT
    )
''')
print("  ✅ investments")

conn.execute('''
    CREATE TABLE IF NOT EXISTS investor_returns (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        investor_id   INTEGER NOT NULL REFERENCES investors(id),
        investment_id INTEGER REFERENCES investments(id),
        date          DATE NOT NULL,
        amount        REAL DEFAULT 0,
        notes         TEXT
    )
''')
print("  ✅ investor_returns")

conn.commit()
conn.close()
print("\nDone. Investor module is ready.")
