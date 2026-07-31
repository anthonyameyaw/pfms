"""Pruning — batch tracking and 6-month cycle management."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, execute, get_all_farms, get_farm
from datetime import date, timedelta

pruning_bp = Blueprint('pruning', __name__)


@pruning_bp.route('/')
def index():
    farms = query("SELECT * FROM farms WHERE crop_type='Oil Palm' ORDER BY id")
    farm_statuses = []
    for farm in farms:
        cycle = query("""
            SELECT * FROM pruning_cycles
            WHERE farm_id=? ORDER BY id DESC LIMIT 1
        """, (farm['id'],), one=True)

        batches_this_cycle = []
        if cycle:
            batches_this_cycle = query("""
                SELECT * FROM pruning_batches
                WHERE cycle_id=? ORDER BY date DESC
            """, (cycle['id'],))

        farm_statuses.append({
            'farm'    : farm,
            'cycle'   : cycle,
            'batches' : batches_this_cycle,
        })

    return render_template('pruning/index.html', farm_statuses=farm_statuses)


@pruning_bp.route('/add-batch', methods=['GET', 'POST'])
def add_batch():
    farms       = query("SELECT * FROM farms WHERE crop_type='Oil Palm' ORDER BY id")
    farm_id     = request.args.get('farm_id', '')
    activity_id = request.args.get('activity_id', '')

    if request.method == 'POST':
        farm_id_post  = int(request.form['farm_id'])
        trees_pruned  = int(request.form.get('trees_pruned') or 0)
        batch_date    = request.form['date']

        farm = get_farm(farm_id_post)

        # Get or create active pruning cycle
        cycle = query("""
            SELECT * FROM pruning_cycles
            WHERE farm_id=? AND is_complete=0 ORDER BY id DESC LIMIT 1
        """, (farm_id_post,), one=True)

        if not cycle:
            cycle_id = execute("""
                INSERT INTO pruning_cycles (farm_id, cycle_start_date, total_trees_pruned)
                VALUES (?,?,0)
            """, (farm_id_post, batch_date))
        else:
            cycle_id = cycle['id']

        # Log the batch
        execute("""
            INSERT INTO pruning_batches
                (farm_id, activity_id, cycle_id, date, trees_pruned,
                 num_labourers, cost, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            farm_id_post,
            request.form.get('activity_id') or None,
            cycle_id,
            batch_date,
            trees_pruned,
            request.form.get('num_labourers') or 0,
            request.form.get('cost') or 0,
            request.form.get('notes',''),
        ))

        # Update cycle total
        execute("""
            UPDATE pruning_cycles
            SET total_trees_pruned = total_trees_pruned + ?
            WHERE id=?
        """, (trees_pruned, cycle_id))

        # Check if cycle is now complete
        updated_cycle = query(
            "SELECT * FROM pruning_cycles WHERE id=?", (cycle_id,), one=True
        )
        total_trees = farm['total_trees'] or 0

        if total_trees > 0 and updated_cycle['total_trees_pruned'] >= total_trees:
            next_due = (date.fromisoformat(batch_date) +
                        timedelta(days=183)).isoformat()
            execute("""
                UPDATE pruning_cycles
                SET is_complete=1, cycle_end_date=?, next_due_date=?
                WHERE id=?
            """, (batch_date, next_due, cycle_id))
            flash(f'Pruning cycle complete! Next cycle due by {next_due}.', 'success')
        else:
            flash('Pruning batch logged.', 'success')

        return redirect(url_for('pruning.index'))

    return render_template('pruning/add_batch.html',
        farms=farms, farm_id=farm_id, activity_id=activity_id)


@pruning_bp.route('/history/<int:farm_id>')
def history(farm_id):
    farm   = get_farm(farm_id)
    cycles = query("""
        SELECT * FROM pruning_cycles WHERE farm_id=? ORDER BY id DESC
    """, (farm_id,))

    cycle_data = []
    for c in cycles:
        batches = query("""
            SELECT * FROM pruning_batches WHERE cycle_id=? ORDER BY date
        """, (c['id'],))
        cycle_data.append({'cycle': c, 'batches': batches})

    return render_template('pruning/history.html',
        farm=farm, cycle_data=cycle_data)
