"""Pruning — batch tracking and 6-month cycle management."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import query, get_farm
from database.pruning_workflow import save_batch

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
        try:
            next_due = save_batch(request.form)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(request.url)
        if next_due:
            flash(f'Pruning cycle complete! Next cycle due by {next_due}.', 'success')
        else:
            flash('Pruning batch logged.', 'success')

        return redirect(url_for('pruning.index'))

    activity = query("SELECT * FROM activities WHERE id=? AND activity_type='Pruning'", (activity_id,), one=True) if activity_id else None
    if activity:
        farm_id = str(activity['farm_id'])
    return render_template('pruning/add_batch.html',
        farms=farms, farm_id=farm_id, activity_id=activity_id, activity=activity)


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
