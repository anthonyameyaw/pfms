"""
PFMS — Database Helper
Handles SQLite connection, initialization, and common queries.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pfms.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_connection():
    """Return a database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database by running the schema SQL."""
    conn = get_connection()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[PFMS] Database initialized at: {DB_PATH}")


def query(sql, params=(), one=False):
    """Run a SELECT query and return results."""
    conn = get_connection()
    cur = conn.execute(sql, params)
    rv = cur.fetchone() if one else cur.fetchall()
    conn.close()
    return rv


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE and return the last row id."""
    conn = get_connection()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def execute_many(sql, params_list):
    """Run a batch INSERT/UPDATE."""
    conn = get_connection()
    conn.executemany(sql, params_list)
    conn.commit()
    conn.close()


# ─── Convenience helpers ───────────────────────────────────────────────────

def get_all_farms():
    return query("SELECT * FROM farms ORDER BY id")


def get_farm(farm_id):
    return query("SELECT * FROM farms WHERE id = ?", (farm_id,), one=True)


def get_active_farms():
    return query("SELECT * FROM farms WHERE status = 'Active' ORDER BY id")


def get_farm_name(farm_id):
    row = query("SELECT name FROM farms WHERE id = ?", (farm_id,), one=True)
    return row['name'] if row else 'Unknown'
