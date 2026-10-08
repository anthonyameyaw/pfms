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
    """Create or upgrade the database through tracked, atomic migrations."""
    from database.migrations import upgrade
    conn = get_connection()
    try:
        upgrade(conn, DB_PATH)
    finally:
        conn.close()


def query(sql, params=(), one=False):
    """Run a SELECT query and return results."""
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    """Run one write, rolling back on error and always closing the connection."""
    conn = get_connection()
    try:
        with conn:
            return conn.execute(sql, params).lastrowid
    finally:
        conn.close()


def execute_many(sql, params_list):
    """Run a batch atomically and always close the connection."""
    conn = get_connection()
    try:
        with conn:
            conn.executemany(sql, params_list)
    finally:
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
