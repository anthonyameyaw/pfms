"""Processing farm links: safe schema repair and transactional form support."""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from database.db import get_connection


def migrate_processing_farms(conn):
    """Repair the legacy renamed-table FK, preserving existing links and IDs."""
    columns = {r[1] for r in conn.execute('PRAGMA table_info(processing_run_farms)')}
    refs = list(conn.execute('PRAGMA foreign_key_list(processing_run_farms)'))
    if 'gallons_contributed' in columns and any(r[2] == 'processing_runs' for r in refs):
        return
    conn.execute('''CREATE TABLE processing_run_farms_repaired (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
        farm_id INTEGER REFERENCES farms(id) ON DELETE CASCADE,
        bunches_contributed INTEGER DEFAULT 0,
        gallons_contributed REAL CHECK(gallons_contributed >= 0)
    )''')
    gallons = 'gallons_contributed' if 'gallons_contributed' in columns else 'NULL'
    conn.execute(f'''INSERT INTO processing_run_farms_repaired
        SELECT id,run_id,farm_id,bunches_contributed,{gallons} FROM processing_run_farms''')
    conn.execute('DROP TABLE processing_run_farms')
    conn.execute('ALTER TABLE processing_run_farms_repaired RENAME TO processing_run_farms')


@contextmanager
def processing_transaction():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def parse_contributions(form, own_gallons, valid_farms):
    ids = form.getlist('contributing_farm_ids')
    bunches = form.getlist('contributing_bunches')
    gallons = form.getlist('contributing_gallons')
    # Old forms submitted before an upgrade may lack the new quantity field.
    if not gallons:
        gallons = [''] * len(ids)
    if len(ids) != len(bunches) or len(ids) != len(gallons):
        raise ValueError('Please review the contributing farm rows.')
    rows, seen = [], set()
    for fid, bunch, gal in zip(ids, bunches, gallons):
        if not fid and not bunch and not gal:
            continue
        try:
            farm_id = int(fid)
            count = int(bunch) if bunch else 0
            quantity = Decimal(gal) if gal else None
        except (ValueError, InvalidOperation):
            raise ValueError('Select a farm and enter valid quantities.')
        if farm_id not in valid_farms or farm_id in seen or count < 0:
            raise ValueError('Select each farm once and use non-negative bunch counts.')
        if quantity is not None and (not quantity.is_finite() or quantity <= 0 or quantity != quantity.quantize(Decimal('.01'))):
            raise ValueError('Gallons per farm must be positive, with at most two decimal places.')
        seen.add(farm_id)
        rows.append([farm_id, count, quantity])
    total = Decimal(str(own_gallons))
    if rows and total <= 0:
        raise ValueError('Farm selections require a positive own-farm oil quantity.')
    if len(rows) == 1 and rows[0][2] is None:
        rows[0][2] = total
    if any(r[2] is None for r in rows):
        raise ValueError('Enter the gallons from each farm when selecting multiple farms.')
    if rows and sum(r[2] for r in rows) != total:
        raise ValueError('Gallons assigned to farms must equal the own-farm total.')
    return [(fid, count, float(quantity)) for fid, count, quantity in rows]


def save_contributions(conn, run_id, rows):
    conn.execute('DELETE FROM processing_run_farms WHERE run_id=?', (run_id,))
    conn.executemany('''INSERT INTO processing_run_farms
        (run_id,farm_id,bunches_contributed,gallons_contributed) VALUES(?,?,?,?)''',
        [(run_id, *row) for row in rows])
