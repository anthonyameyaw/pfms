"""Link unambiguous harvests to recorded farm contributions at the plant."""
def sync_dates(conn):
    harvests=conn.execute('SELECT * FROM harvests ORDER BY date,id').fetchall()
    for h in harvests:
        if h['processing_run_id']:
            run=conn.execute('''SELECT p.id,p.date FROM processing_runs p JOIN processing_run_farms f ON f.run_id=p.id
                WHERE p.id=? AND f.farm_id=? AND ABS(f.gallons_contributed-?)<0.000001 AND p.date>=?''',
                (h['processing_run_id'],h['farm_id'],h['gallons_produced'],h['date'])).fetchone()
            if run and h['husks_processed']:
                conn.execute('UPDATE harvests SET processing_date=? WHERE id=?',(run['date'],h['id']))
                continue
            conn.execute('UPDATE harvests SET processing_date=NULL,processing_run_id=NULL WHERE id=?',(h['id'],))
        elif h['processing_date']:
            continue  # Preserve dates entered independently by the owner.
        if not h['husks_processed'] or not h['gallons_produced']:continue
        rows=conn.execute('''SELECT p.id,p.date FROM processing_runs p JOIN processing_run_farms f ON f.run_id=p.id
            WHERE f.farm_id=? AND p.date>=? AND ABS(f.gallons_contributed-?)<0.000001
              AND NOT EXISTS(SELECT 1 FROM harvests n WHERE n.farm_id=? AND n.date>? AND n.date<=p.date)
              AND NOT EXISTS(SELECT 1 FROM harvests used WHERE used.farm_id=? AND used.processing_run_id=p.id AND used.id!=?)
            ORDER BY p.date,p.id''',(h['farm_id'],h['date'],h['gallons_produced'],h['farm_id'],h['date'],h['farm_id'],h['id'])).fetchall()
        if len(rows)==1:
            conn.execute('UPDATE harvests SET processing_date=?,processing_run_id=? WHERE id=?',(rows[0]['date'],rows[0]['id'],h['id']))


def migrate_dates(conn):
    if 'processing_run_id' not in {r[1] for r in conn.execute('PRAGMA table_info(harvests)')}:
        conn.execute('ALTER TABLE harvests ADD COLUMN processing_run_id INTEGER REFERENCES processing_runs(id) ON DELETE SET NULL')
    sync_dates(conn)
    from database.harvest_workflow import validate_stock
    validate_stock(conn)
