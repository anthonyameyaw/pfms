"""Farm production enters one pool; only storage sales recognize oil revenue."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from database.db import get_connection


def migrate_pooled_storage(conn):
    if not conn.in_transaction:
        conn.execute('BEGIN')
    conn.execute('CREATE TABLE IF NOT EXISTS pfms_migrations (name TEXT PRIMARY KEY)')
    if conn.execute("SELECT 1 FROM pfms_migrations WHERE name='pooled_storage_v1'").fetchone():
        return
    if 'processing_date' not in {row[1] for row in conn.execute('PRAGMA table_info(harvests)')}:
        conn.execute('ALTER TABLE harvests ADD COLUMN processing_date TEXT')
    if 'legacy_harvest_id' not in {row[1] for row in conn.execute('PRAGMA table_info(storage_transactions)')}:
        conn.execute('ALTER TABLE storage_transactions ADD COLUMN legacy_harvest_id INTEGER')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS storage_legacy_harvest ON storage_transactions(legacy_harvest_id) WHERE legacy_harvest_id IS NOT NULL')
    if 'harvest_id' not in {row[1] for row in conn.execute('PRAGMA table_info(transport_logs)')}:
        conn.execute('ALTER TABLE transport_logs ADD COLUMN harvest_id INTEGER REFERENCES harvests(id) ON DELETE CASCADE')
    conn.execute('''CREATE TABLE IF NOT EXISTS harvest_sales_archive (
        harvest_id INTEGER PRIMARY KEY, original_record TEXT NOT NULL,
        review_note TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0)''')
    for raw in conn.execute('SELECT * FROM harvests').fetchall():
        h=dict(raw)
        sold=h.get('gallons_sold') or 0; income=h.get('gallons_sold_income') or 0
        estimated=h.get('oil_income') or 0
        if sold or income or estimated:
            valid=sold>0 and income>0
            note=('Imported previously recorded sale; date retained from harvest and may need review.' if valid else
                  'Unconfirmed old income/valuation. No sale added; excluded from revenue. Please check original records.')
            conn.execute('INSERT INTO harvest_sales_archive VALUES(?,?,?,0)',(h['id'],json.dumps(h),note))
            if valid:
                conn.execute('''INSERT INTO storage_transactions
                    (date,transaction_type,gallons,price_per_gallon,total_amount,reason,notes,legacy_harvest_id)
                    VALUES(?,'Sale',?,?,?,?,?,?)''',
                    (h['date'],sold,h.get('gallons_sold_price') or income/sold,income,
                     'Imported recorded oil sale',note,h['id']))
        conn.execute('''UPDATE harvests SET husks_processed=CASE WHEN gallons_produced>0 THEN 1 ELSE 0 END,
            processing_date=NULL,
            gallons_sold=0,gallons_sold_price=0,gallons_sold_income=0,oil_income=0,price_per_gallon=0 WHERE id=?''',(h['id'],))
    # Link only unambiguous historical auto-transport entries. No amount changes.
    conn.execute('''UPDATE transport_logs SET harvest_id=(SELECT h.id FROM harvests h
        WHERE h.farm_id=transport_logs.farm_id AND h.date=transport_logs.date)
        WHERE notes LIKE '%harvest%' AND
        (SELECT COUNT(*) FROM harvests h WHERE h.farm_id=transport_logs.farm_id AND h.date=transport_logs.date)=1 AND
        (SELECT COUNT(*) FROM transport_logs t WHERE t.farm_id=transport_logs.farm_id AND t.date=transport_logs.date AND t.notes LIKE '%harvest%')=1''')
    conn.execute("INSERT INTO pfms_migrations VALUES('pooled_storage_v1')")


def number(form, name, default=0, integer=False):
    try:
        raw=form.get(name)
        value=Decimal(str(default) if raw is None or raw=='' else str(raw))
        if not value.is_finite() or value<0 or (integer and value!=value.to_integral_value()):
            raise ValueError()
        if not integer and value!=value.quantize(Decimal('.01')):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError(name.replace('_',' ').capitalize()+' must be a non-negative number'+(' without decimals.' if integer else ' with at most two decimal places.'))
    return int(value) if integer else float(value)


def valid_date(value):
    try:
        if date.fromisoformat(value).isoformat()!=value:raise ValueError()
    except (TypeError, ValueError):raise ValueError('Enter a valid date (YYYY-MM-DD).')
    return value


def validate_stock(conn):
    rows=conn.execute('''WITH movements AS (
        SELECT COALESCE(processing_date,date) AS day, gallons_produced AS quantity FROM harvests WHERE husks_processed=1
        UNION ALL SELECT date, CASE WHEN transaction_type='Purchase' THEN gallons ELSE -gallons END
            FROM storage_transactions WHERE transaction_type IN ('Purchase','Sale')
    ), daily AS (SELECT day,SUM(quantity) AS quantity FROM movements GROUP BY day)
    SELECT day,SUM(quantity) OVER (ORDER BY day) AS balance FROM daily ORDER BY day''').fetchall()
    for row in rows:
        if row['balance'] < -0.000001:
            raise ValueError('This change would make pooled stock negative on '+row['day']+'. Check production, purchase and sale dates first.')

    from database.oil_quality import balances
    balances(conn)

def save_harvest(form, harvest_id=None, activity_id=None):
    # Old open forms must not silently lose a sale during the workflow change.
    if any(number(form,k)>0 for k in ('gallons_sold','gallons_sold_income','price_per_gallon')):
        raise ValueError('Harvests now record production only. Refresh this form and record oil sales in Storage.')
    fid=number(form,'farm_id',integer=True);day=valid_date(form.get('date'))
    bunches=number(form,'bunches_harvested',integer=True)
    harvester=number(form,'harvester_pay',bunches*3);collector=number(form,'collector_pay')
    thresh=number(form,'threshing_cost')
    count=number(form,'num_collectors',integer=True)
    processed=form.get('husks_processed')=='1'
    gallons=number(form,'gallons_produced') if processed else 0
    if processed and gallons<=0:raise ValueError('Enter the gallons produced after processing.')
    process_day=valid_date(form.get('processing_date')) if processed and form.get('processing_date') else None
    if process_day and process_day<day:raise ValueError('Processing cannot be before the harvest date.')
    mode=form.get('transport_mode','')
    if mode not in ('','Pickup','Tricycle'):raise ValueError('Select a valid transport mode.')
    driver=number(form,'driver_pay') if mode=='Pickup' else 0
    fuel=number(form,'fuel_cost') if mode=='Pickup' else 0
    rent=number(form,'tricycle_rent') if mode=='Tricycle' else 0
    labour=round(harvester+collector,2);notes=form.get('notes','')
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM farms WHERE id=?',(fid,)).fetchone():raise ValueError('Select an existing farm.')
        old=conn.execute('SELECT * FROM harvests WHERE id=?',(harvest_id,)).fetchone() if harvest_id else None
        if harvest_id and not old:raise ValueError('Harvest not found.')
        duplicate=conn.execute('SELECT id FROM harvests WHERE farm_id=? AND date=? AND id!=?',
            (fid,day,harvest_id or -1)).fetchone()
        if duplicate:
            raise ValueError('A harvest already exists for this farm on this date. Edit the existing harvest instead.')
        if old:
            activity_id=old['activity_id']
            if conn.execute("SELECT 1 FROM transport_logs WHERE harvest_id IS NULL AND farm_id=? AND date=? AND notes LIKE '%harvest%'",(old['farm_id'],old['date'])).fetchone():
                raise ValueError('This harvest has ambiguous old transport records. Resolve their links before editing it.')
        elif activity_id:
            a=conn.execute('SELECT * FROM activities WHERE id=?',(activity_id,)).fetchone()
            if not a or a['activity_type']!='Harvesting':raise ValueError('Linked activity must be a harvest activity.')
            if conn.execute('SELECT 1 FROM harvests WHERE activity_id=?',(activity_id,)).fetchone():raise ValueError('This activity already has a harvest; edit that record instead.')
        if old and 'threshing_cost' not in form:
            thresh=old['threshing_cost'] or 0
        activity_values=(fid,day,'Harvesting',f'{bunches} bunches harvested',count,round(labour+thresh,2),'',0,notes)
        if activity_id:
            conn.execute('''UPDATE activities SET farm_id=?,date=?,activity_type=?,description=?,num_labourers=?,labour_cost=?,materials_used=?,materials_cost=?,notes=? WHERE id=?''',(*activity_values,activity_id))
        else:
            activity_id=conn.execute('''INSERT INTO activities(farm_id,date,activity_type,description,num_labourers,labour_cost,materials_used,materials_cost,notes) VALUES(?,?,?,?,?,?,?,?,?)''',activity_values).lastrowid
        fields=['farm_id','activity_id','date','bunches_harvested','num_labourers','num_collectors','harvester_pay','collector_pay','harvesting_cost','threshing_cost','husks_processed','gallons_produced','processing_date','transport_mode','driver_pay','fuel_cost','tricycle_rent','notes']
        values=[fid,activity_id,day,bunches,count,count,harvester,collector,labour,thresh,int(processed),gallons,process_day,mode,driver,fuel,rent,notes]
        if old:
            conn.execute('UPDATE harvests SET '+','.join(f+'=?' for f in fields)+' WHERE id=?',values+[harvest_id])
        else:
            harvest_id=conn.execute('INSERT INTO harvests('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',values).lastrowid
        conn.execute('DELETE FROM transport_logs WHERE harvest_id=?',(harvest_id,))
        if driver+fuel+rent>0:
            conn.execute('''INSERT INTO transport_logs(date,transport_type,farm_id,driver_pay,fuel_cost,rental_cost,notes,harvest_id)
                VALUES(?,?,?,?,?,?,?,?)''',(day,mode,fid,driver,fuel,rent,'Auto from harvest log',harvest_id))
        from database.processing_dates import sync_dates
        sync_dates(conn)
        saved=conn.execute('SELECT processing_date FROM harvests WHERE id=?',(harvest_id,)).fetchone()
        if processed and not saved['processing_date']:
            raise ValueError('No unique matching processing run was found. Enter the processing date or check the farm contribution at the plant.')
        validate_stock(conn)
        conn.commit()
        return harvest_id
    except Exception:
        conn.rollback();raise
    finally:conn.close()


def delete_harvest(harvest_id):
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT * FROM harvests WHERE id=?',(harvest_id,)).fetchone()
        if not row:raise ValueError('Harvest not found.')
        if conn.execute("SELECT 1 FROM transport_logs WHERE harvest_id IS NULL AND farm_id=? AND date=? AND notes LIKE '%harvest%'",(row['farm_id'],row['date'])).fetchone():
            raise ValueError('Resolve ambiguous old transport links before deleting this harvest.')
        conn.execute('DELETE FROM harvests WHERE id=?',(harvest_id,))
        if row['activity_id']:
            conn.execute('DELETE FROM activities WHERE id=?',(row['activity_id'],))
        validate_stock(conn);conn.commit()
    except Exception:
        conn.rollback();raise
    finally:conn.close()
