"""Keep pruning production records and their financial activities consistent."""
from datetime import date, timedelta
from database.db import get_connection
from database.harvest_workflow import number, valid_date


def save_batch(form):
    conn = get_connection()
    try:
        farm_id_post = number(form, 'farm_id', integer=True)
        trees_pruned = number(form, 'trees_pruned', integer=True)
        labourers = number(form, 'num_labourers', integer=True)
        cost = number(form, 'cost')
        batch_date = valid_date(form.get('date'))
        activity_id = form.get('activity_id') or None
        conn.execute('BEGIN IMMEDIATE')
        farm = conn.execute('SELECT * FROM farms WHERE id=?', (farm_id_post,)).fetchone()
        if not farm or farm['crop_type'] != 'Oil Palm':
            raise ValueError('Select an existing oil palm farm.')
        if activity_id:
            activity = conn.execute('SELECT * FROM activities WHERE id=?', (activity_id,)).fetchone()
            if not activity or activity['farm_id'] != farm_id_post or activity['activity_type'] != 'Pruning':
                raise ValueError('Select a pruning activity belonging to this farm.')
        if trees_pruned <= 0:
            raise ValueError('Enter a positive number of trees pruned.')
        if activity_id:
            if conn.execute('SELECT 1 FROM pruning_batches WHERE activity_id=?', (activity_id,)).fetchone():
                raise ValueError('This activity already has a pruning batch. Edit the existing activity instead.')
            materials = activity['materials_cost'] or 0
            if cost < materials:
                raise ValueError('Total batch cost cannot be below the activity materials cost.')
            conn.execute('UPDATE activities SET date=?,num_labourers=?,labour_cost=? WHERE id=?',
                (batch_date, labourers, round(cost-materials,2), activity_id))
        else:
            activity_id = conn.execute("""INSERT INTO activities
                (farm_id,date,activity_type,description,num_labourers,labour_cost,materials_cost,notes)
                VALUES (?,?,'Pruning',?,?,?,0,?)""", (farm_id_post,batch_date,
                f'{trees_pruned} trees pruned',labourers,cost,form.get('notes',''))).lastrowid
        cycle = conn.execute("""SELECT * FROM pruning_cycles
            WHERE farm_id=? AND is_complete=0 ORDER BY id DESC LIMIT 1""",
            (farm_id_post,)).fetchone()
        if cycle:
            cycle_id = cycle['id']
        else:
            cycle_id = conn.execute("""INSERT INTO pruning_cycles
                (farm_id, cycle_start_date, total_trees_pruned) VALUES (?,?,0)""",
                (farm_id_post, batch_date)).lastrowid
        conn.execute("""INSERT INTO pruning_batches
            (farm_id, activity_id, cycle_id, date, trees_pruned, num_labourers, cost, notes)
            VALUES (?,?,?,?,?,?,?,?)""", (farm_id_post, activity_id, cycle_id,
            batch_date, trees_pruned, labourers, cost, form.get('notes', '')))
        conn.execute("""UPDATE pruning_cycles SET total_trees_pruned=total_trees_pruned+?
            WHERE id=?""", (trees_pruned, cycle_id))
        total = conn.execute('SELECT total_trees_pruned FROM pruning_cycles WHERE id=?',
            (cycle_id,)).fetchone()['total_trees_pruned']
        next_due = None
        if (farm['total_trees'] or 0) > 0 and total >= farm['total_trees']:
            next_due = (date.fromisoformat(batch_date) + timedelta(days=183)).isoformat()
            conn.execute("""UPDATE pruning_cycles SET is_complete=1,
                cycle_end_date=?, next_due_date=? WHERE id=?""", (batch_date, next_due, cycle_id))
        conn.commit()
        return next_due
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def refresh_cycle(conn, cycle_id):
    cycle = conn.execute('SELECT c.*,f.total_trees FROM pruning_cycles c JOIN farms f ON f.id=c.farm_id WHERE c.id=?', (cycle_id,)).fetchone()
    totals = conn.execute('SELECT COUNT(*) n,COALESCE(SUM(trees_pruned),0) trees,MIN(date) first_day,MAX(date) last_day FROM pruning_batches WHERE cycle_id=?', (cycle_id,)).fetchone()
    if not totals['n']:
        conn.execute('DELETE FROM pruning_cycles WHERE id=?', (cycle_id,))
        return
    complete = bool((cycle['total_trees'] or 0)>0 and totals['trees']>=cycle['total_trees'])
    end = totals['last_day'] if complete else None
    due = (date.fromisoformat(end)+timedelta(days=183)).isoformat() if end else None
    conn.execute('UPDATE pruning_cycles SET total_trees_pruned=?,cycle_start_date=?,is_complete=?,cycle_end_date=?,next_due_date=? WHERE id=?',
        (totals['trees'],totals['first_day'],int(complete),end,due,cycle_id))


def change_linked_activity(activity_id, form=None):
    """Edit or delete a batch-linked activity together with its pruning records."""
    conn=get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        batches=conn.execute('SELECT * FROM pruning_batches WHERE activity_id=?',(activity_id,)).fetchall()
        if len(batches)!=1:
            raise ValueError('This pruning activity needs its batch links reviewed before changing it.')
        batch=batches[0]
        if form is None:
            conn.execute('DELETE FROM pruning_batches WHERE id=?',(batch['id'],))
            conn.execute('DELETE FROM activities WHERE id=?',(activity_id,))
        else:
            if form.get('activity_type')!='Pruning' or number(form,'farm_id',integer=True)!=batch['farm_id']:
                raise ValueError('A linked pruning activity must keep its farm and activity type. Its batch belongs to that farm’s pruning cycle.')
            day=valid_date(form.get('date'))
            labour=number(form,'labour_cost');materials=number(form,'materials_cost')
            workers=number(form,'num_labourers',integer=True)
            conn.execute('UPDATE activities SET date=?,description=?,num_labourers=?,labour_cost=?,materials_used=?,materials_cost=?,notes=? WHERE id=?',
                (day,form.get('description',''),workers,labour,form.get('materials_used',''),materials,form.get('notes',''),activity_id))
            conn.execute('UPDATE pruning_batches SET date=?,num_labourers=?,cost=?,notes=? WHERE id=?',
                (day,workers,round(labour+materials,2),form.get('notes',''),batch['id']))
        refresh_cycle(conn,batch['cycle_id'])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
